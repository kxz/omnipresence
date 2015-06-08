"""Title processor for media files using PyAV."""


from __future__ import absolute_import, division
import tempfile

import av
from twisted.plugin import IPlugin
from zope.interface import implements

from ..url import add_si_prefix, ITitleProcessor
from ...util import andify


class AVTitleProcessor(object):
    implements(IPlugin, ITitleProcessor)
    supported_content_types = ['audio/mpeg', 'video/mp4',
                               'video/webm', 'video/x-matroska']

    def process(self, headers, content):
        with tempfile.NamedTemporaryFile() as f:
            f.write(content)
            try:
                container = av.open(f.name)
            except av.AVError:
                return None
            clength = headers.get('X-Omni-Length')
            if clength:
                try:
                    clength = int(clength, 10)
                except ValueError:
                    # Couldn't parse the content-length string.
                    clength = None
            return u'{} file containing {} ({} seconds{})'.format(
                container.format.long_name,
                andify([s.long_name + ' ' + s.type
                        for s in container.streams]),
                int(round(container.duration / av.time_base)),
                (u', ' + add_si_prefix(clength, 'byte')) if clength else u'')


default = AVTitleProcessor()
