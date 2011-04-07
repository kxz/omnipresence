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


# With acknowledgement to John Gruber.
# <http://daringfireball.net/2010/07/improved_regex_for_matching_urls>
URL_PATTERN = re.compile(ur"""
\b
(                                       # Capture 0: Entire matched URL
  (                                     # Capture 1: STARTS WITH
    https?://                           # http or https protocol
    |                                   #   or
    www\d{0,3}[.]                       # "www.", "www1." ... "www999."
    |                                   #   or
    [a-z0-9.\-]+[.][a-z]{2,4}/          # domain-ish string followed by a slash
  )
  (?:                                   # FOLLOWED BY ONE OR MORE
    [^\s()<>]+                          # run of non-space, non-()<>
    |                                   #   or
    \(([^\s()<>]+|(\([^\s()<>]+\)))*\)  # balanced parens, up to 2 levels
  )+
  (?:                                   # ENDS WITH
    \(([^\s()<>]+|(\([^\s()<>]+\)))*\)  # balanced parens, up to 2 levels
    |                                   #   or
    [^\s`!()\[\]{};:'".,<>?«»“”‘’]      # not space or one of these punct chars
  )
)
""", re.IGNORECASE | re.VERBOSE)


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
                    content_length = ((' (%s bytes)'
                                        % headers['content-length'])
                                      if 'content-length' in headers
                                      else '')
                    title = (u'%s document%s' % (ctype, content_length))

                hostname_tag = hostname
                
                # When a redirect lands us at a different hostname than the one
                # in the URL, append the new hostname to the tag.
                if 'content-location' in headers:
                    content_hostname = urlparse.urlparse(headers['content-location']).hostname
                    if (content_hostname is not None and
                        hostname != content_hostname):
                        hostname_tag = u'%s -> %s' % (hostname,
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
        
        urls = URL_PATTERN.findall(message)
        fetchers = []
        
        for match in urls:
            url = match[0]
            log.msg('Saw URL %s from %s in channel %s.'
                    % (url, prefix, channel))
            
            # Add "http://" to URLs that were only matched through 
            # starting with "www." and lack a protocol.
            if match[1] not in ('http://', 'https://'):
                url = 'http://' + url
            
            # Strip the fragment portion of the URL, if present.
            (url, tag) = urllib.splittag(url)
            
            # The number of blocking calls required for this makes 
            # working with Deferreds a nightmare, so we just defer the 
            # entire thing to a thread here instead.
            fetchers.append(threads.deferToThread(self.get_url, url))
        
        l = defer.DeferredList(fetchers, consumeErrors=True)
        l.addBoth(self.reply_with_titles, bot, prefix, channel)
        return l
    
    action = privmsg


url = URLTitleFetcher()
