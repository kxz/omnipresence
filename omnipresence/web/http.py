# -*- test-case-name: omnipresence.test.test_http
"""Wrappers for Twisted's HTTP request machinery."""


import json

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web.client import (Agent, ContentDecoderAgent, RedirectAgent,
                                GzipDecoder, _ReadBodyProtocol)

from .. import __version__, __source__


#: The default HTTP user agent.
USER_AGENT = 'Omnipresence/{} (+bot; {})'.format(__version__, __source__)


#: A Twisted Web `Agent` with reasonable settings for most requests.
#: Use this if you need to make a request inside a plugin.
default_agent = ContentDecoderAgent(RedirectAgent(Agent(reactor)),
                                    [('gzip', GzipDecoder)])


#
# JSON response helpers
#

class JSONBodyProtocol(_ReadBodyProtocol):
    """A protocol that returns a Python object deserialized from JSON
    data sent to it."""

    def __init__(self, status, message, deferred):
        _ReadBodyProtocol.__init__(self, status, message, deferred)
        self.deferred.addCallback(json.loads)


def read_json_body(response):
    """Return a `Deferred` yielding a Python object deserialized from
    the Twisted Web *response* containing JSON data in its body."""
    finished = Deferred()
    response.deliverBody(JSONBodyProtocol(
        response.code, response.phrase, finished))
    return finished
