"""Wrappers for Twisted's HTTP request machinery."""


import sys
from urlparse import urlparse

import ipaddress
from twisted.internet import defer, reactor
from twisted.web.client import (
    IAgent, Agent, ContentDecoderAgent, RedirectAgent, GzipDecoder,
    _ReadBodyProtocol, PartialDownloadError)
from twisted.web.http_headers import Headers
from zope.interface import implements

from .. import __version__, __source__


#: The default HTTP user agent.
USER_AGENT = 'Omnipresence/{} (+bot; {})'.format(__version__, __source__)


class TruncatingReadBodyProtocol(_ReadBodyProtocol):
    """A protocol that collects data sent to it up to a maximum of
    *max_bytes*, then discards the rest."""

    def __init__(self, status, message, deferred, max_bytes=None):
        _ReadBodyProtocol.__init__(self, status, message, deferred)
        self.remaining = self.max_bytes = (max_bytes or sys.maxsize)

    def dataReceived(self, data):
        if self.remaining > 0:
            to_buffer = data[:self.remaining]
            _ReadBodyProtocol.dataReceived(self, to_buffer)
            self.remaining -= len(to_buffer)


class BlacklistedHost(Exception):
    def __init__(self, hostname, ip):
        self.hostname = hostname
        self.ip = ip

    def __str__(self):
        return 'host {} corresponds to blacklisted IP {}'.format(
            self.hostname, self.ip)


class BlacklistingAgent(object):
    """An `~twisted.web.client.Agent` wrapper that forbids requests to
    loopback, private, and internal IP addresses."""
    implements(IAgent)

    def __init__(self, agent, resolve=None):
        self.agent = agent
        self.resolve = resolve or reactor.resolve

    @defer.inlineCallbacks
    def request(self, method, uri, headers=None, bodyProducer=None):
        hostname = urlparse(uri).hostname
        ip_str = yield self.resolve(hostname)
        # `ipaddress` takes a Unicode string and I don't really care to
        # handle `UnicodeDecodeError` separately.
        ip = ipaddress.ip_address(ip_str.decode('ascii', 'replace'))
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise BlacklistedHost(hostname, ip)
        response = yield self.agent.request(method, uri, headers, bodyProducer)
        defer.returnValue(response)


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
