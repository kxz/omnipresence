# -*- test-case-name: omnipresence.test.test_http
"""Wrappers for Twisted's HTTP request machinery."""


import json

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web.iweb import IAgent
from twisted.web.client import (Agent, ContentDecoderAgent, RedirectAgent,
                                GzipDecoder, _ReadBodyProtocol)
from twisted.web.http_headers import Headers
from zope.interface import implementer

from .. import __version__, __source__


@implementer(IAgent)
class IdentifyingAgent(object):
    """An `Agent` wrapper that adds a default user agent string to the
    outgoing request."""

    #: The default HTTP user agent.
    user_agent = 'Omnipresence/{} (+bot; {})'.format(__version__, __source__)

    def __init__(self, agent):
        self.agent = agent

    def request(self, method, uri, headers=None, bodyProducer=None):
        if headers is None:
            headers = Headers()
        else:
            headers = headers.copy()
        if not headers.hasHeader('user-agent'):
            headers.addRawHeader('user-agent', self.user_agent)
        return self.agent.request(method, uri, headers, bodyProducer)


#: A Twisted Web `Agent` with reasonable settings for most requests.
#: Use this if you need to make a request inside a plugin.
default_agent = IdentifyingAgent(
    ContentDecoderAgent(RedirectAgent(Agent(reactor)),
                        [('gzip', GzipDecoder)]))


#
# JSON response helpers
#

class JSONBodyProtocol(_ReadBodyProtocol, object):
    """A protocol that returns a Python object deserialized from JSON
    data sent to it."""

    def __init__(self, status, message, deferred):
        super(JSONBodyProtocol, self).__init__(status, message, deferred)
        self.deferred.addCallback(json.loads)


def read_json_body(response):
    """Return a `Deferred` yielding a Python object deserialized from
    the Twisted Web *response* containing JSON data in its body."""
    finished = Deferred()
    response.deliverBody(JSONBodyProtocol(
        response.code, response.phrase, finished))
    return finished
