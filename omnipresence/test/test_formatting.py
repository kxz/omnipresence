"""Unit tests for message formatting handling."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from ..message.formatting import remove_formatting, unclosed_formatting


class FormattingRemovalTestCase(unittest.TestCase):
    def _test(self, original, removed):
        self.assertEqual(remove_formatting(original), removed)

    def test_unformatted(self):
        self._test('lorem ipsum', 'lorem ipsum')

    def test_color_pair(self):
        self._test('dolor \x032,12sit', 'dolor sit')

    def test_color_reset(self):
        self._test('lorem \x03ipsum', 'lorem ipsum')

    def test_complex_formatting(self):
        self._test('\x02a\x0Fm\x033et', 'amet')


class UnclosedFormattingTestCase(unittest.TestCase):
    def _test(self, string, unclosed):
        self.assertEqual(unclosed_formatting(string), frozenset(unclosed))

    def test_unformatted(self):
        self._test('lorem ipsum', [])

    def test_color_pair(self):
        self._test('dolor \x032,12sit', ['\x032,12'])

    def test_color_reset(self):
        self._test('lorem \x03ipsum', [])

    def test_complex_formatting(self):
        self._test('\x02a\x0F\x1Fm\x033et', ['\x1F', '\x033'])
