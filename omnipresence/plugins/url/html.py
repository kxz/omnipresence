import cgi

from BeautifulSoup import BeautifulSoup, SoupStrainer
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import util
from omnipresence.plugins.url import ITitleProcessor

class HTMLTitleProcessor(object):
    implements(IPlugin, ITitleProcessor)

    supported_content_types = ['text/html', 'application/xhtml+xml']

    def process(self, headers, content):
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

h = HTMLTitleProcessor()
