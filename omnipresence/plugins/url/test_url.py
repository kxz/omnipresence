# -*- coding: utf-8 -*-
"""Unit tests for the url event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from __future__ import unicode_literals
from twisted.trial import unittest

from . import extract_urls


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
