# -*- coding: utf-8 -*-
import cgi
import re
import socket
import struct
import urllib
import urlparse

from httplib2 import ServerNotFoundError
from twisted.internet import defer, threads
from twisted.plugin import getPlugins, pluginPackagePaths, IPlugin
from twisted.python import failure, log
from zope.interface import implements, Interface, Attribute

from omnipresence import plugins
from omnipresence.iomnipresence import IHandler


# Make twisted.plugin.getPlugins() look for plug-ins in this module.
__path__.extend(pluginPackagePaths(__name__))
__all__ = []


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
WRAPPING_PUNCTUATION = [('(', ')'), ('<', '>'), ('&lt;', '&gt;')]

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
        self.ignore_list = self.factory.config.getspacelist('url',
                                                            'ignore_messages_from')
        for title_processor in getPlugins(ITitleProcessor, plugins.url):
            for content_type in title_processor.supported_content_types:
                self.title_processors[content_type] = title_processor
   
    def reply_with_titles(self, results, bot, prefix, channel):
        for i, result in enumerate(results):
            success, response = result
            
            title = u'No title found.'
            
            if success:
                hostname, headers, content = response
                ctype, cparams = cgi.parse_header(headers.get('content-type',
                                                              'Unknown'))

                if ctype in self.title_processors:
                    title = self.title_processors[ctype].process(headers,
                                                                 content)
                else:
                    title = u'%s document' % ctype
                    if 'content-length' in headers:
                        try:
                            content_length = int(headers['content-length'], 10)
                        except ValueError:
                            # Couldn't parse the content-length string.
                            pass
                        else:
                            title += (u' (%s)' % add_si_prefix(content_length,
                                                               'byte'))

                hostname_tag = hostname
                
                # When a redirect lands us at a different hostname than the one
                # in the URL, append the new hostname to the tag.
                if 'content-location' in headers:
                    content_hostname = urlparse.urlparse(headers['content-location']).hostname
                    if (content_hostname is not None and
                        hostname != content_hostname):
                        hostname_tag = u'%s \u2192 %s' % (hostname,
                                                          content_hostname)

                title = u'[%s] %s' % (hostname_tag, title)
            else:
                if not isinstance(response.value, ServerNotFoundError):
                    log.err(response,
                            'Encountered an error in URL processing.')
                
                title = (u'Error: \x02%s\x02.'
                           % response.getErrorMessage())
            
            if len(title) >= 140:
                title = title[:64] + u'...' + title[-64:]
            
            if len(results) > 1:
                message = u'URL (%d/%d): %s' % (i + 1, len(results), title)
            else:
                message = u'URL: %s' % title
            
            bot.reply(None, channel, message.encode(self.factory.encoding))
    
    def get_url(self, url):
        hostname = urlparse.urlparse(url).hostname
        
        if hostname is None:
            log.msg('Could not extract hostname for URL %s; failing.' % url)
            raise ServerNotFoundError('Unable to find the server at %s'
                                       % hostname)
        
        # Check to make sure that the hostname doesn't correspond to a 
        # private IP.  This only supports IPv4 addresses.
        try:
            addr = socket.gethostbyname(hostname)
        except socket.gaierror:
            # The hostname doesn't resolve to anything.
            raise ServerNotFoundError('Unable to find the server at %s'
                                       % hostname)
        
        addr = struct.unpack('!I', socket.inet_aton(addr))[0]
        if ((addr >> 24 == 0x00  )   # 0.0.0.0/8
         or (addr >> 24 == 0x0A  )   # 10.0.0.0/8
         or (addr >> 24 == 0x7F  )   # 127.0.0.0/8
         or (addr >> 16 == 0xA9DE)   # 169.254.0.0/16
         or (addr >> 20 == 0xAC1 )   # 172.16.0.0/12
         or (addr >> 16 == 0xC0A8)): # 192.168.0.0/16
            # This hostname resolves to a private IP address.  Pretend 
            # we don't know anything about it.
            raise ServerNotFoundError('Unable to find the server at %s'
                                       % hostname)
        
        # The provided URL is confirmed to not be on a private network.  
        # First, probe the content type of the target document with a 
        # HEAD request, and see if it's one for which we support title 
        # snarfing.  If so, make a GET request and return its results 
        # instead.  If not, just return the results of the HEAD request, 
        # as we have no use for the content.
        headers, content = self.factory.get_http(url, method='HEAD', defer=False)
        ctype, cparams = cgi.parse_header(headers.get('content-type', ''))

        if ctype in self.title_processors:
            headers, content = self.factory.get_http(url, defer=False)

        return (hostname, headers, content)
    
    def privmsg(self, bot, prefix, channel, message):
        nick = prefix.split('!', 1)[0]
        
        if nick in self.ignore_list:
            return
        
        urls = extract_urls(message)
        fetchers = []
        
        for url in urls:
            log.msg('Saw URL %s from %s in channel %s.'
                    % (url, prefix, channel))
            
            # Strip the fragment portion of the URL, if present.
            (url, frag) = urlparse.urldefrag(url)

            # Look for "crawlable" AJAX URLs with fragments that begin
            # with "#!", and transform them to use "_escaped_fragment_".
            #
            # <http://code.google.com/web/ajaxcrawling/>
            if frag.startswith('!'):
                url += ('&' if '?' in url else '?' +
                        '_escaped_fragment_=' + urllib.quote(frag[1:]))
            
            # The number of blocking calls required for this makes 
            # working with Deferreds a nightmare, so we just defer the 
            # entire thing to a thread here instead.
            fetchers.append(threads.deferToThread(self.get_url, url))
        
        l = defer.DeferredList(fetchers, consumeErrors=True)
        l.addBoth(self.reply_with_titles, bot, prefix, channel)
        return l
    
    action = privmsg


url = URLTitleFetcher()
