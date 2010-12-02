from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence.plugins.url import ITitleProcessor

class PlainTextTitleProcessor(object):
    implements(IPlugin, ITitleProcessor)

    supported_content_types = ['text/plain']

    def process(self, headers, content):
        return u'\x02%s\x02' % content.split('\n', 1)[0]

p = PlainTextTitleProcessor()
