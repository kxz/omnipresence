import StringIO

from PIL import Image
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence.plugins.url import add_si_prefix, ITitleProcessor

class PILTitleProcessor(object):
    implements(IPlugin, ITitleProcessor)

    supported_content_types = ['image/png', 'image/gif', 'image/jpeg']

    def process(self, headers, content):
        pbuffer = Image.open(StringIO.StringIO(content))
        width, height = pbuffer.size
        format = pbuffer.format
        return u'{0} image ({1:n} \u00d7 {2:n} pixels, {3})'.format(
            format, width, height, add_si_prefix(len(content), 'byte')
            )

p = PILTitleProcessor()
