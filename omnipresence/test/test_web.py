from bs4 import BeautifulSoup
from twisted.internet.defer import succeed
from twisted.trial import unittest
from twisted.web.test.test_agent import (AgentTestsMixin,
                                         FakeReactorAndConnectMixin)

from omnipresence.web import BlacklistingAgent, BlacklistedHost, textify_html


def dummy_resolve(hostname):
    return succeed('127.0.0.1' if hostname == 'localhost' else '8.8.8.8')


class BlacklistingAgentTestCase(unittest.TestCase,
                                FakeReactorAndConnectMixin, AgentTestsMixin):
    # <https://twistedmatrix.com/trac/ticket/4024>... one wishes.
    #
    # Based in part on `twisted.web.test.test_agent.RedirectAgentTests`.

    sample_hosts = ('localhost', '0.0.0.0', '10.0.0.1', '127.0.0.1',
                    '169.254.0.1', '172.16.0.1', '192.168.0.1')

    def makeAgent(self):
        return BlacklistingAgent(self.buildAgentForWrapperTest(self.reactor),
                                 resolve=dummy_resolve)

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


class HTMLTestCase(unittest.TestCase):
    def _textify_equal(self, a, b, format_output=True):
        self.assertEqual(textify_html(a, format_output), b)
        # str and BeautifulSoup should yield the same results
        self.assertEqual(textify_html(BeautifulSoup(a), format_output), b)

    def test_textify_string(self):
        self._textify_equal('hello', 'hello')
        self._textify_equal('<b>hello</b>', '\x02hello\x02')
        self._textify_equal('<b>hello</b>', 'hello', False)
        self._textify_equal('<b>he<i>llo</b>', '\x02he\x16llo\x16\x02')
        self._textify_equal('<b>he<i>   l  l o </b>',
                            '\x02he\x16 l l o \x16\x02')
        self._textify_equal('<b>he<i>   l  l o </b>', 'he l l o', False)
        self._textify_equal('<em>10<sup>16</sup></em>', '\x1610^16\x16')
        self._textify_equal('<h1>lorem <sub>ipsum</sub></h1>', 'lorem _ipsum')
        self._textify_equal('5.66<b> (22)</b>', '5.66\x02 (22)\x02')
        self._textify_equal('5.66<b> (22)</b>', '5.66 (22)', False)
        self._textify_equal('<em>lorem <cite>ipsum dolor</cite></em>',
                            '\x16lorem \x16ipsum dolor\x16\x16')

    def test_textify_tag(self):
        soup = BeautifulSoup('<a><b>hello</b></a>')
        self.assertEqual(textify_html(soup.a, format_output=False), 'hello')
