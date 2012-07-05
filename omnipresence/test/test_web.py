from __future__ import unicode_literals

from bs4 import BeautifulSoup
from twisted.trial import unittest

import omnipresence.web as web


class HTMLTestCase(unittest.TestCase):
    def _textify_equal(self, a, b, format_output=True):
        self.assertEqual(web.textify_html(a, format_output), b)
        # str and BeautifulSoup should yield the same results
        self.assertEqual(web.textify_html(BeautifulSoup(a), format_output), b)

    def test_textify_string(self):
        self._textify_equal('hello', 'hello')
        self._textify_equal('<b>hello</b>', '\x02hello\x02')
        self._textify_equal('<b>hello</b>', 'hello', False)
        self._textify_equal('<b>he<i>llo</b>', '\x02he\x16llo\x16\x02')
        self._textify_equal('<b>he<i>   l  l o </b>', '\x02he\x16 l l o \x16\x02')
        self._textify_equal('<b>he<i>   l  l o </b>', 'he l l o', False)
        self._textify_equal('<em>10<sup>16</sup></em>', '\x1610^16\x16')
        self._textify_equal('<h1>lorem <sub>ipsum</sub></h1>', 'lorem _ipsum')
        self._textify_equal('5.66<b> (22)</b>', '5.66\x02 (22)\x02')
        self._textify_equal('5.66<b> (22)</b>', '5.66 (22)', False)
        self._textify_equal('<em>lorem <cite>ipsum dolor</cite></em>',
                            '\x16lorem \x16ipsum dolor\x16\x16')

    def test_textify_tag(self):
        soup = BeautifulSoup('<a><b>hello</b></a>')
        self.assertEqual(web.textify_html(soup.a, format_output=False), 'hello')
