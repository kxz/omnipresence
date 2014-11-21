import cgi

from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence.plugins.url import ITitleProcessor


DEFAULT_ENCODING = 'utf-8'


class PlainTextTitleProcessor(object):
    implements(IPlugin, ITitleProcessor)

    supported_content_types = ['text/plain']

    def process(self, headers, content):
        # If the HTTP "Content-Type" header specifies an encoding, try
        # to use it to decode the document.
        ctype, cparams = cgi.parse_header(headers.get('Content-Type', ''))
        encoding = cparams.get('charset', DEFAULT_ENCODING)
        try:
            decoded = content.decode(encoding, 'replace')
        except LookupError:
            decoded = content.decode(DEFAULT_ENCODING, 'replace')
        return u'\x02%s\x02' % decoded.splitlines()[0]


p = PlainTextTitleProcessor()
