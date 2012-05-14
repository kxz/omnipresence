# -*- coding: utf-8 -*-
import cgi
import re
import socket
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import struct
import sys
import urllib
import urlparse

from twisted.internet import defer, error, protocol, reactor, threads
from twisted.names.client import lookupAddress
from twisted.plugin import getPlugins, pluginPackagePaths, IPlugin
from twisted.python import failure, log
from zope.interface import implements, Interface, Attribute

from omnipresence import plugins, web
from omnipresence.iomnipresence import IHandler


# Make twisted.plugin.getPlugins() look for plug-ins in this module.
__path__.extend(pluginPackagePaths(__name__))
__all__ = []


"""The maximum number of bytes the fetcher will download for a single
title fetch request."""
MAX_DOWNLOAD_SIZE = 65536

#
# Utility methods
#

def add_si_prefix(number, unit, plural_unit=None):
    """Returns a string containing an approximate representation of the
    given number and unit, using a decimal SI prefix.  *number* is
    assumed to be a positive integer. If *plural_unit* is not specified,
    it defaults to *unit* with an "s" appended."""
    if not plural_unit:
        plural_unit = unit + 's'
    
    if number == 1:
        return '{0:n} {1}'.format(number, unit)
    
    prefix = ''
    for prefix in ('', 'kilo', 'mega', 'giga', 'tera',
                   'exa', 'peta', 'zetta', 'yotta'):
        if number < 1000:
            break
        
        number /= 1000.0

    if prefix:
        return '{0:.3n} {1}{2}'.format(number, prefix, plural_unit)

    return '{0:n} {1}'.format(number, plural_unit)

# Based on django.utils.html.urlize from the Django project.
TRAILING_PUNCTUATION = ['.', ',', ':', ';']
WRAPPING_PUNCTUATION = [('(', ')'), ('<', '>')]

word_split_re = re.compile(r'(\s+)')
simple_url_re = re.compile(r'^https?://\w', re.IGNORECASE)
simple_url_2_re = re.compile(r'^www\.|^(?!http)\w[^@]+\.(com|edu|gov|int|mil|net|org)$', re.IGNORECASE)

def extract_urls(text):
    """Extracts URL-like strings from *text* and returns them as a list."""
    urls = []
    words = word_split_re.split(text)
    for i, word in enumerate(words):
        match = None
        if '.' in word or ':' in word:
            # Deal with punctuation.
            lead, middle, trail = '', word, ''
            for punctuation in TRAILING_PUNCTUATION:
                if middle.endswith(punctuation):
                    middle = middle[:-len(punctuation)]
                    trail = punctuation + trail
            for opening, closing in WRAPPING_PUNCTUATION:
                if middle.startswith(opening):
                    middle = middle[len(opening):]
                    lead = lead + opening
                # Keep parentheses at the end only if they're balanced.
                if (middle.endswith(closing)
                    and middle.count(closing) == middle.count(opening) + 1):
                    middle = middle[:-len(closing)]
                    trail = closing + trail

            # Make URL we want to point to.
            url = None
            if simple_url_re.match(middle):
                url = middle
            elif simple_url_2_re.match(middle):
                url = 'http://%s' % middle

            # Add to our list of URLs.
            if url:
                urls.append(url)
    return urls

def is_private_host(hostname):
    """Check if the given host corresponds to a private network, as
    specified by RFC 1918.  Only supports IPv4."""
    addr = socket.gethostbyname(hostname)
    addr = struct.unpack('!I', socket.inet_aton(addr))[0]
    if ((addr >> 24 == 0x00  )   # 0.0.0.0/8
     or (addr >> 24 == 0x0A  )   # 10.0.0.0/8
     or (addr >> 24 == 0x7F  )   # 127.0.0.0/8
     or (addr >> 16 == 0xA9DE)   # 169.254.0.0/16
     or (addr >> 20 == 0xAC1 )   # 172.16.0.0/12
     or (addr >> 16 == 0xC0A8)): # 192.168.0.0/16
        return True
    return False

#
# Plugin interfaces
#

class ITitleProcessor(Interface):
    """
    Finds the title of a given Web document.
    """

    supported_content_types = Attribute("""
        @type supported_content_types: C{list} of C{str}
        @ivar supported_content_types: The MIME content types that this 
        title processor supports.
        """)

    def process(self, headers, content):
        """
        Finds the title of the document specified by C{headers} and 
        C{content}.

        @type headers: C{dict}
        @param headers: A dictionary of HTTP response headers, as 
        returned by the request() method of an httplib2.Http object.

        @type content: C{str}
        @param content: The body of the HTTP response.

        @rtype: C{str}
        @return: The title of the given document.
        """

#
# Actual handler plugin
#

class URLTitleFetcher(object):
    """
    Reply to messages containing URLs with an appropriate title (the 
    contents of the <title> element for HTML pages, the first line for 
    plain text documents, and so forth.)
    """
    implements(IPlugin, IHandler)
    name = 'url'

    title_processors = {}
    
    def registered(self):
        self.ignore_list = self.factory.config.getspacelist(
                             'url', 'ignore_messages_from')
        for title_processor in getPlugins(ITitleProcessor, plugins.url):
            for content_type in title_processor.supported_content_types:
                self.title_processors[content_type] = title_processor
    
    def privmsg(self, bot, prefix, channel, message):
        nick = prefix.split('!', 1)[0]
        
        if nick in self.ignore_list:
            return
        
        # Everything in here is Unicode.
        message = message.decode(self.factory.encoding, 'ignore')
        
        urls = extract_urls(message)
        fetchers = []
        
        for url in urls:
            log.msg('Saw URL %s from %s in channel %s.'
                    % (url.encode('utf8'), prefix, channel))
            
            # Strip the fragment portion of the URL, if present.
            url, frag = urlparse.urldefrag(url)

            # Look for "crawlable" AJAX URLs with fragments that begin
            # with "#!", and transform them to use "_escaped_fragment_".
            #
            # <http://code.google.com/web/ajaxcrawling/>
            if frag.startswith('!'):
                url += (u'&' if u'?' in url else u'?' +
                        u'_escaped_fragment_=' +
                        urllib.quote(frag[1:].encode('utf8')))
            
            # Basic hostname sanity checks.
            hostname = urlparse.urlparse(url).hostname
            if hostname is None:
                log.msg('Could not extract hostname from URL {0}; ignoring.' \
                         .format(url.encode('utf8')))
                continue
            
            # Twisted Names is full of headaches.  socket is easier.
            d = threads.deferToThread(is_private_host, hostname.encode('utf8'))
            d.addCallback(self.request, url)
            d.addCallback(self.process_content)
            d.addCallback(self.make_reply, hostname)
            d.addErrback(self.make_error_reply, hostname)
            fetchers.append(d)
        
        l = defer.DeferredList(fetchers)
        l.addCallback(self.reply, bot, prefix, channel)
        return l
    
    action = privmsg
    
    def request(self, is_private_ip, url):
        if is_private_ip:
            # Pretend that the given host just doesn't exist.
            raise error.TimeoutError()
        return web.request('GET', url.encode('utf8'),
                           max_bytes=MAX_DOWNLOAD_SIZE)
    
    def process_content(self, (headers, content)):
        ctype, cparams = cgi.parse_header(headers.get('Content-Type'))
        if ctype in self.title_processors:
            title_processor = self.title_processors[ctype]
            d = threads.deferToThread(title_processor.process, headers, content)
            d.addCallback(lambda title: (title, headers.get('X-Omni-Location')))
            return d
        
        title = u'{0} document'.format(ctype or u'Unknown')
        clength = headers.get('X-Omni-Length')
        if clength:
            try:
                clength = int(clength, 10)
            except ValueError:
                # Couldn't parse the content-length string.
                pass
            else:
                title += (u' ({0})'.format(add_si_prefix(clength, 'byte')))
        return (title, headers.get('X-Omni-Location'))
    
    def make_reply(self, (title, location), hostname):
        hostname_tag = hostname
        if location:
            content_hostname = urlparse.urlparse(location).hostname
            if content_hostname is not None and hostname != content_hostname:
                hostname_tag = u'%s \u2192 %s' % (hostname, content_hostname)
        return u'[{0}] {1}'.format(hostname_tag, title)
    
    def make_error_reply(self, failure, hostname):
        log.err(failure, 'Encountered an error in URL processing.')
        return u'[{0}] Error: {1:s}'.format(hostname, failure.value)
    
    def reply(self, results, bot, prefix, channel):
        for i, result in enumerate(results):
            success, value = result
            
            if success:
                title = value
            else:
                # This should only happen if make_reply() bombs.
                log.err(value, 'Encountered an error in URL processing.')
                title = u'Error: \x02{0:s}\x02.'.format(value.value)
            
            if len(title) >= 140:
                title = u'{0}…{1}'.format(title[:64], title[-64:])
            
            if len(results) > 1:
                message = u'URL ({0}/{1}): {2}'.format(i + 1, len(results), title)
            else:
                message = u'URL: {0}'.format(title)
            
            bot.reply(None, channel, message.encode(self.factory.encoding))


url = URLTitleFetcher()
