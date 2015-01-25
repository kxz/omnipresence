"""Wrappers for Twisted's HTTP request machinery."""


try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import sys

from twisted.internet import defer, protocol, reactor
from twisted.python import failure
from twisted.web.client import (Agent, ContentDecoderAgent,
                                RedirectAgent, GzipDecoder,
                                ResponseFailed)
from twisted.web.http_headers import Headers

from ..connection import VERSION_NUM


USER_AGENT = ('Omnipresence/{0} (+bot; '
              'https://bitbucket.org/kxz/omnipresence)' \
               .format(VERSION_NUM))
"""The default HTTP user agent."""


class BufferSizeExceededError(Exception):
    def __init__(self, actual_size, buffer_size):
        self.actual_size = actual_size
        self.buffer_size = buffer_size

    def __str__(self):
        return 'tried to read {0} bytes into {1}-byte buffer'.format(
            self.actual_size,
            self.buffer_size
            )


class ResponseBuffer(protocol.Protocol):
    def __init__(self, response, finished, max_bytes=sys.maxsize):
        self.buffer = StringIO.StringIO()
        self.response = response
        self.finished = finished
        self.remaining = self.max_bytes = max_bytes

    def dataReceived(self, bytes):
        if self.remaining - len(bytes) < 0:
            self.transport.loseConnection()
            self.buffer.close()
            failure_ = failure.Failure(BufferSizeExceededError(
                self.max_bytes - self.remaining + len(bytes),
                self.max_bytes
                ))
            self.finished.errback(ResponseFailed([failure_], self.response))
            return

        self.buffer.write(bytes)
        self.remaining -= len(bytes)

    def connectionLost(self, reason):
        self.finished.callback(self.buffer.getvalue())


agent = ContentDecoderAgent(RedirectAgent(Agent(reactor)),
                            [('gzip', GzipDecoder)])


def transform_response(response, **kwargs):
    """Return an httplib2-style ``(headers, content)`` tuple from the
    given Twisted Web response."""
    headers = dict((k, v[0]) for k, v in response.headers.getAllRawHeaders())
    # Add the ultimately requested URL as a custom X-header.
    headers['X-Omni-Location'] = response.request.absoluteURI
    # Calling deliverBody causes the response's Content-Length header to
    # be overwritten with how much of the body was actually delivered.
    # In some cases, the original value is needed, so we store it in a
    # custom X-header field.
    headers['X-Omni-Length'] = str(response.length)
    d = defer.Deferred()
    response.deliverBody(ResponseBuffer(response, d, **kwargs))
    d.addCallback(lambda content: (headers, content))
    return d


def request(*args, **kwargs):
    """Make an HTTP request, and return a Deferred that will yield an
    httplib2-style ``(headers, content)`` tuple to its callback.

    Arguments are as for a request to a typical Twisted Web agent, with
    the addition of one keyword argument, *max_bytes*, that specifies
    the maximum number of bytes to fetch from the desired resource.  If
    no ``User-Agent`` header is specified, one is added before making
    the request.

    Two custom headers are returned in the response, in addition to any
    set by the HTTP server:  ``X-Omni-Location`` contains the final
    location of the request resource after following all redirects, and
    ``X-Omni-Length`` contains the original value of the response's
    ``Content-Length`` header, which Twisted may overwrite if the actual
    response exceeds *max_bytes* in size."""
    kwargs.setdefault('headers', Headers())
    if not kwargs['headers'].hasHeader('User-Agent'):
        kwargs['headers'].addRawHeader('User-Agent', USER_AGENT)

    transform_kwargs = {}
    if 'max_bytes' in kwargs:
        transform_kwargs['max_bytes'] = kwargs.pop('max_bytes')

    d = agent.request(*args, **kwargs)
    d.addCallback(transform_response, **transform_kwargs)
    return d
