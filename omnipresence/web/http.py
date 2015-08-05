"""Wrappers for Twisted's HTTP request machinery."""


from twisted.internet import defer, reactor
from twisted.web.client import (Agent, ContentDecoderAgent,
                                RedirectAgent, GzipDecoder)

from .. import __version__, __source__


#: The default HTTP user agent.
USER_AGENT = 'Omnipresence/{} (+bot; {})'.format(__version__, __source__)


default_agent = ContentDecoderAgent(RedirectAgent(Agent(reactor)),
                                    [('gzip', GzipDecoder)])
