"""Unit tests for HTTP machinery."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import Deferred, succeed
from twisted.python.failure import Failure
from twisted.trial import unittest
from twisted.web.client import ResponseDone
from twisted.web.test.test_agent import (AgentTestsMixin,
                                         FakeReactorAndConnectMixin)

from ..web.http import (TruncatingReadBodyProtocol, BlacklistingAgent,
                        BlacklistedHost)


class TruncatingReadBodyProtocolTestCase(unittest.TestCase):
    def _assert_delivery(self, data, expected):
        finished = Deferred()
        protocol = TruncatingReadBodyProtocol(200, 'OK', finished, 8)
        finished.addCallback(self.assertEqual, expected)
        protocol.dataReceived(data)
        protocol.connectionLost(Failure(ResponseDone()))
        return finished

    def test_complete(self):
        return self._assert_delivery('#' * 8, '#' * 8)

    def test_truncated(self):
        return self._assert_delivery('#' * 16, '#' * 8)


class BlacklistingAgentTestCase(unittest.TestCase,
                                FakeReactorAndConnectMixin, AgentTestsMixin):
    # <https://twistedmatrix.com/trac/ticket/4024>... one wishes.
    #
    # Based in part on `twisted.web.test.test_agent.RedirectAgentTests`.

    sample_hosts = ('localhost', '0.0.0.0', '10.0.0.1', '127.0.0.1',
                    '169.254.0.1', '172.16.0.1', '192.168.0.1')

    @staticmethod
    def resolve(hostname):
        if hostname == 'localhost':
            return succeed('127.0.0.1')
        elif hostname == 'foo.test':
            return succeed('8.8.8.8')
        return succeed(hostname)

    def makeAgent(self):
        return BlacklistingAgent(self.buildAgentForWrapperTest(self.reactor),
                                 resolve=self.resolve)

    def setUp(self):
        self.reactor = self.Reactor()
        self.agent = self.makeAgent()

    def test_no_blacklist(self):
        self.agent.request('GET', 'http://foo.test/')

    def _assert_blacklist(self, method, uri):
        d = self.agent.request(method, uri)
        f = self.failureResultOf(d, BlacklistedHost)

    def test_blacklist(self):
        for protocol in ('http', 'https'):
            for host in self.sample_hosts:
                uri = '{}://{}/'.format(protocol, host)
                for method in ('GET', 'POST'):
                    self._assert_blacklist(method, uri)
