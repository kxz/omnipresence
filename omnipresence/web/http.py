"""Wrappers for Twisted's HTTP request machinery."""


from twisted.internet import defer, reactor
from twisted.web.client import (Agent, ContentDecoderAgent, RedirectAgent,
                                GzipDecoder, PartialDownloadError)
from twisted.web.http_headers import Headers

from .. import __version__, __source__


#: The default HTTP user agent.
USER_AGENT = 'Omnipresence/{} (+bot; {})'.format(__version__, __source__)


default_agent = ContentDecoderAgent(RedirectAgent(Agent(reactor)),
                                    [('gzip', GzipDecoder)])


@defer.inlineCallbacks
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
    max_bytes = kwargs.pop('max_bytes', None)
    agent = kwargs.pop('agent', None) or default_agent
    response = yield agent.request(*args, **kwargs)
    headers = dict((k, v[0]) for k, v in response.headers.getAllRawHeaders())
    # Add the ultimately requested URL as a custom X-header.
    headers['X-Omni-Location'] = response.request.absoluteURI
    # Calling deliverBody causes the response's Content-Length header to
    # be overwritten with how much of the body was actually delivered.
    # In some cases, the original value is needed, so we store it in a
    # custom X-header field.
    headers['X-Omni-Length'] = str(response.length)
    d = defer.Deferred()
    response.deliverBody(TruncatingReadBodyProtocol(
        response.code, response.phrase, d, max_bytes=max_bytes))
    try:
        content = yield d
    except PartialDownloadError as e:
        content = e.response
    defer.returnValue((headers, content))
