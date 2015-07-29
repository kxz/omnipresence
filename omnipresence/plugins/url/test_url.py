"""Unit tests for the url event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import Deferred, succeed
from twisted.python.failure import Failure
from twisted.trial import unittest
from twisted.web.client import ResponseDone
from twisted.web.test.test_agent import (AgentTestsMixin,
                                         FakeReactorAndConnectMixin)

from . import (extract_urls, TruncatingReadBodyProtocol,
               BlacklistingAgent, BlacklistedHost)


class ExtractURLsTestCase(unittest.TestCase):
    # Most test cases are adapted from Django's urlize tests.

    def _assert_urls(self, text, urls):
        return list(extract_urls(text)) == urls

    def test_http(self):
        self._assert_urls('http://example.com', ['http://example.com'])
        self._assert_urls('http://example.com/', ['http://example.com/'])

    def test_https(self):
        self._assert_urls('https://example.com', ['https://example.com'])

    def test_split_chars(self):
        # Quotes (single and double) and angle brackets shouldn't be
        # considered part of URLs.
        self._assert_urls('http://example.com"abc', ['http://example.com'])
        self._assert_urls("http://example.com'abc", ['http://example.com'])
        self._assert_urls('http://example.com<abc', ['http://example.com'])
        self._assert_urls('http://example.com>abc', ['http://example.com'])

    def test_word_with_dot(self):
        self._assert_urls('some.organization', [])

    def test_parentheses(self):
        self._assert_urls('http://example.com/a_(b)',
                          ['http://example.com/a_(b)'])
        self._assert_urls('(http://example.com/a_(b))',
                          ['http://example.com/a_(b)'])
        self._assert_urls('(see http://example.com/a_(b))',
                          ['http://example.com/a_(b)'])

    def test_malformed(self):
        self._assert_urls('http:///example.com', [])
        self._assert_urls('http://.example.com', [])
        self._assert_urls('http://@example.com', [])

    def test_uppercase(self):
        self._assert_urls('HTTPS://example.com/', ['HTTPS://example.com/'])

    def test_trailing_period(self):
        self._assert_urls('(Go to http://example.com/a.)',
                          ['http://example.com/a'])

    def test_ipv4(self):
        self._assert_urls('http://10.0.0.1/foo', ['http://10.0.0.1/foo'])

    def test_ipv6(self):
        self._assert_urls('http://[2001:db8:cafe::2]/foo',
                          ['http://[2001:db8:cafe::2]/foo'])

    def test_catastrophic_backtracking(self):
        """Test that we don't crash on URLs that cause catastrophic
        backtracking on the Daring Fireball regex."""
        self._assert_urls(
            'http://i.ebayimg.com/00/s/MTAwOFgxMDI0/$(KGrHqYOKo0E6fEy4,lqBOt,yzoor!~~60_12.JPG',
            ['http://i.ebayimg.com/00/s/MTAwOFgxMDI0/$(KGrHqYOKo0E6fEy4,lqBOt,yzoor!~~60_12.JPG'])


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
