"""Unit tests for HTML conversions."""
# pylint: disable=missing-docstring,too-few-public-methods


from __future__ import unicode_literals

from twisted.trial import unittest

from ....web.html import parse, textify


class HTMLTestCase(unittest.TestCase):
    def assert_textify(self, a, b, format_output=True):
        self.assertEqual(textify(a, format_output), b)
        # str and BeautifulSoup should yield the same results.
        self.assertEqual(textify(parse(a), format_output), b)

    def test_simple(self):
        self.assert_textify('hello', 'hello')

    def test_bold_italic(self):
        self.assert_textify('<b>hello</b>', '\x02hello\x02')
        self.assert_textify('<b>hello</b>', 'hello', False)
        self.assert_textify('<b>he<i>llo</b>', '\x02he\x16llo\x16\x02')

    def test_sup_sub(self):
        self.assert_textify('<em>10<sup>16</sup></em>', '\x1610^16\x16')
        self.assert_textify('<h1>lorem <sub>ipsum</sub></h1>', 'lorem _ipsum')

    def test_whitespace(self):
        self.assert_textify('<b>he<i>   l  l o </b>',
                            '\x02he\x16 l l o \x16\x02')
        self.assert_textify('<b>he<i>   l  l o </b>', 'he l l o', False)
        self.assert_textify('5.66<b> (22)</b>', '5.66\x02 (22)\x02')
        self.assert_textify('5.66<b> (22)</b>', '5.66 (22)', False)
        self.assert_textify('<em>lorem <cite>ipsum dolor</cite></em>',
                            '\x16lorem \x16ipsum dolor\x16\x16')

    def test_trailing_content(self):
        self.assert_textify('lorem <i><b>ipsum</b> dolor </i>sit amet',
                            'lorem \x16\x02ipsum\x02 dolor \x16sit amet')
        self.assert_textify('lorem <i><b>ipsum</b> dolor </i>sit amet',
                            'lorem ipsum dolor sit amet', False)

    def test_textify_tag(self):
        soup = parse('<a><b>hello</b></a>')
        self.assertEqual(textify(soup.a, format_output=False), 'hello')
