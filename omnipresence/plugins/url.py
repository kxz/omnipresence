import cgi
import re
import socket
import StringIO
import struct
import urllib
import urlparse

from BeautifulSoup import BeautifulSoup, SoupStrainer
from httplib2 import ServerNotFoundError
from PIL import Image
from twisted.internet import defer, threads
from twisted.plugin import IPlugin
from twisted.python import failure, log
from zope.interface import implements

from omnipresence import util
from omnipresence.iomnipresence import IHandler

URL_PATTERN = re.compile(r"""\b((https?://|www[.])[^\s()<>]+(?:\([\w\d]+\)|(?:[^-!"#$%&'()*+,./:;<=>?@[\\\]^_`{|}~\s]|/)))""")

def get_html_title(headers, content):
    soup_kwargs = {'parseOnlyThese': SoupStrainer('title')}
    
    # If the HTTP "Content-Type" header specifies an 
    # encoding, try to use it to decode the document.
    ctype, cparams = cgi.parse_header(headers.get('content-type', ''))
    if 'charset' in cparams:
        soup_kwargs['fromEncoding'] = cparams['charset']
    
    soup = BeautifulSoup(content, **soup_kwargs)

    title = u'No title found.'
    
    if soup.title:
        title = soup.title.string.extract()
        title = util.decode_html_entities(title)
        title = u'\x02%s\x02' % u' '.join(title.split()).strip()

    return title

def get_text_title(headers, content):
    return u'\x02%s\x02' % content.split('\n', 1)[0]

def get_image_title(headers, content):
    pbuffer = Image.open(StringIO.StringIO(content))
    width, height = pbuffer.size
    format = pbuffer.format
    return (u'%s image (%d x %d pixels, %d bytes)'
              % (format, width, height, len(content)))

TITLE_PROCESSORS = {'text/html': get_html_title,
                    'application/xhtml+xml': get_html_title,
                    'text/plain': get_text_title,
                    'image/png': get_image_title,
                    'image/gif': get_image_title,
                    'image/jpeg': get_image_title }


class URLTitleFetcher(object):
    """
    Reply to messages containing URLs with an appropriate title (the 
    contents of the <title> element for HTML pages, the first line for 
    plain text documents, and so forth.)
    """
    implements(IPlugin, IHandler)
    name = 'url'

    
    def registered(self):
        self.ignore_list = self.factory.config.getspacelist('url',
                                                            'ignore_messages_from')
   
    def reply_with_titles(self, results, bot, user, channel):
        for i, result in enumerate(results):
            success, response = result
            
            title = u'No title found.'
            
            if success:
                headers, content = response
                ctype, cparams = cgi.parse_header(headers.get('content-type',
                                                              'Unknown'))

                if ctype in TITLE_PROCESSORS:
                    title = TITLE_PROCESSORS[ctype](headers, content)
                else:
                    content_length = ((' (%s bytes)'
                                        % headers['content-length'])
                                      if 'content-length' in headers
                                      else '')
                    title = (u'%s document%s' % (ctype, content_length))
                
                if 'content-location' in headers:
                    title = (u'[%s] %s'
                               % (urlparse.urlparse(headers['content-location']).hostname,
                                  title))
            else:
                if not isinstance(response.value, ServerNotFoundError):
                    log.err(response,
                            'Encountered an error in URL processing.')
                
                title = (u'Error: \x02%s\x02.'
                           % response.getErrorMessage())
            
            if len(title) >= 140:
                title = title[:64] + u'...' + title[-64:]
            
            if len(results) > 1:
                bot.msg(channel, '\x0314URL (%d/%d): %s'
                                  % (i + 1, len(results),
                                     title.encode(self.factory.encoding)))
            else:
                bot.msg(channel, '\x0314URL: %s'
                                  % title.encode(self.factory.encoding))
    
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

        if ctype in TITLE_PROCESSORS:
            return self.factory.get_http(url, defer=False)

        return (headers, content)
    
    def privmsg(self, bot, user, channel, message):
        nick = user.split('!', 1)[0]
        
        if nick in self.ignore_list:
            return
        
        urls = URL_PATTERN.findall(message)
        fetchers = []
        
        for match in urls:
            url = match[0]
            log.msg('Saw URL %s from %s in channel %s.'
                    % (url, user, channel))
            
            # Add "http://" to URLs that were only matched through 
            # starting with "www." and lack a protocol.
            if match[1] == 'www.':
                url = 'http://' + url
            
            # Strip the fragment portion of the URL, if present.
            url = url.split('#', 1)[0]
            
            # The number of blocking calls required for this makes 
            # working with Deferreds a nightmare, so we just defer the 
            # entire thing to a thread here instead.
            fetchers.append(threads.deferToThread(self.get_url, url))
        
        l = defer.DeferredList(fetchers, consumeErrors=True)
        l.addBoth(self.reply_with_titles, bot, user, channel)
        return l
    
    action = privmsg


url = URLTitleFetcher()
