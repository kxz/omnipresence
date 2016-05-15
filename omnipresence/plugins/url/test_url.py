# -*- coding: utf-8
"""Unit tests for the url event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from mock import Mock, call
from twisted.internet.defer import succeed
from twisted.trial.unittest import TestCase

from . import extract_iris, Default
from ...test.helpers import ConnectionTestMixin, OutgoingPlugin


class ExtractIRIsTestCase(TestCase):
    # Most test cases are adapted from Django's urlize tests.

    def assert_iris(self, text, iris):
        self.assertEqual(list(extract_iris(text)), iris)

    def test_http(self):
        self.assert_iris(u'http://example.com', [u'http://example.com'])
        self.assert_iris(u'http://example.com/', [u'http://example.com/'])

    def test_https(self):
        self.assert_iris(u'https://example.com', [u'https://example.com'])

    def test_split_chars(self):
        """Test that quotation marks and angle brackets aren't
        considered part of IRIs."""
        self.assert_iris(u'http://example.com"abc', [u'http://example.com'])
        self.assert_iris(u"http://example.com'abc", [u'http://example.com'])
        self.assert_iris(u'http://example.com<abc', [u'http://example.com'])
        self.assert_iris(u'http://example.com>abc', [u'http://example.com'])

    def test_word_with_dot(self):
        self.assert_iris(u'some.organization', [])

    def test_parentheses(self):
        self.assert_iris(u'http://example.com/a_(b)',
                         [u'http://example.com/a_(b)'])
        self.assert_iris(u'(http://example.com/a_(b))',
                         [u'http://example.com/a_(b)'])
        self.assert_iris(u'(see http://example.com/a_(b))',
                         [u'http://example.com/a_(b)'])

    def test_malformed(self):
        self.assert_iris(u'http:///example.com', [])
        self.assert_iris(u'http://.example.com', [])
        self.assert_iris(u'http://@example.com', [])

    def test_uppercase(self):
        self.assert_iris(u'HTTPS://example.com/', [u'HTTPS://example.com/'])

    def test_trailing_period(self):
        self.assert_iris(u'(Go to http://example.com/a.)',
                         [u'http://example.com/a'])

    def test_ipv4(self):
        self.assert_iris(u'http://10.0.0.1/foo', [u'http://10.0.0.1/foo'])

    def test_ipv6(self):
        self.assert_iris(u'http://[2001:db8:cafe::2]/foo',
                         [u'http://[2001:db8:cafe::2]/foo'])

    def test_catastrophic_backtracking(self):
        """Test that IRIs that cause catastrophic backtracking on the
        Daring Fireball regex don't crash the extractor."""
        self.assert_iris(
            u'http://i.ebayimg.com/00/s/MTAwOFgxMDI0/$(KGrHqYOKo0E6fEy4,lqBOt,yzoor!~~60_12.JPG',
            [u'http://i.ebayimg.com/00/s/MTAwOFgxMDI0/$(KGrHqYOKo0E6fEy4,lqBOt,yzoor!~~60_12.JPG'])

    def test_unicode_iris(self):
        self.assert_iris(
            u'このサイトがすごい！ http://ドメイン名例.test/',
            [u'http://ドメイン名例.test/'])


class URLTestCase(ConnectionTestMixin, TestCase):
    def setUp(self):
        super(URLTestCase, self).setUp()
        self.plugin = self.connection.settings.enable(Default.name, [])
        self.fetch_title = Mock(return_value=succeed('title'))
        self.plugin.fetcher.fetch_title = self.fetch_title
        self.outgoing = self.connection.settings.enable(
            OutgoingPlugin.name, [])

    def test_simple(self):
        self.receive('PRIVMSG {} :http://www.example.com/'
                     .format(self.connection.nickname))
        self.fetch_title.assert_called_with(
            u'http://www.example.com/',
            hostname_tag=True, friendly_errors=True)
        self.assertEqual(self.outgoing.last_seen.content, 'title')

    def test_multiple_iris(self):
        self.receive('PRIVMSG {} :http://foo.test/ http://bar.test/'
                     .format(self.connection.nickname))
        self.fetch_title.assert_has_calls([
            call(u'http://foo.test/', hostname_tag=True, friendly_errors=True),
            call(u'http://bar.test/', hostname_tag=True, friendly_errors=True),
            ])
        self.assertEqual(self.outgoing.last_seen.content, 'title')
