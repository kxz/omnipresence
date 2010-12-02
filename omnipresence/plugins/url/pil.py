import StringIO

from PIL import Image
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence.plugins.url import ITitleProcessor

class PILTitleProcessor(object):
    implements(IPlugin, ITitleProcessor)

    supported_content_types = ['image/png', 'image/gif', 'image/jpeg']

    def process(self, headers, content):
        pbuffer = Image.open(StringIO.StringIO(content))
        width, height = pbuffer.size
        format = pbuffer.format
        return (u'%s image (%d x %d pixels, %d bytes)'
                  % (format, width, height, len(content)))

p = PILTitleProcessor()
