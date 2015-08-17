"""Unit tests for IRC hostmask handling."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from ..case_mapping import case_mapping_by_name
from ..hostmask import Hostmask, mask_as_regex as mar


class HostmaskTestCase(unittest.TestCase):
    def test_from_string(self):
        self.assertEqual(Hostmask.from_string('nick!user@host'),
                         Hostmask('nick', 'user', 'host'))
        self.assertEqual(Hostmask.from_string('nick@host'),
                         Hostmask('nick', None, 'host'))
        self.assertEqual(Hostmask.from_string('nick!user'),
                         Hostmask('nick', 'user', None))
        self.assertEqual(Hostmask.from_string('nick'),
                         Hostmask('nick', None, None))

    def test_str(self):
        self.assertEqual(str(Hostmask('nick', 'user', 'host')),
                         'nick!user@host')
        self.assertEqual(str(Hostmask('nick', None, 'host')),
                         'nick@host')
        self.assertEqual(str(Hostmask('nick', 'user', None)),
                         'nick!user')
        self.assertEqual(str(Hostmask('nick', None, None)),
                         'nick')

    def test_mask_as_regex(self):
        self.assertEqual(mar('*.test').pattern, r'\A.*\.test\Z')
        self.assertEqual(mar('nick?').pattern, r'\Anick.\Z')
        self.assertEqual(mar(r'nick\*').pattern, r'\Anick\*\Z')
        self.assertEqual(mar(r'ni\ck').pattern, r'\Ani\\ck\Z')

    def test_matches(self):
        self.assertTrue(Hostmask('nick', 'user', 'host').matches(
            Hostmask('nick', 'user', 'host')))
        self.assertTrue(
            Hostmask('nick', 'user', 'host').matches('nick!user@host'))
        self.assertTrue(
            Hostmask('nick', None, None).matches('nick!user@host'))
        self.assertFalse(
            Hostmask('nick', 'user', 'host').matches('other_nick'))
        self.assertTrue(
            Hostmask('nick', 'user', 'host').matches('nick!*@*'))
        self.assertTrue(
            Hostmask('nick', 'user', 'host.test').matches('*!*@*.test'))
        self.assertTrue(
            Hostmask('nick', 'user', 'test').matches('*!*@*test'))
        self.assertTrue(
            Hostmask('nick1', None, None).matches('nick?'))
        self.assertTrue(
            Hostmask('nick*', None, None).matches(r'nick\*'))
        self.assertFalse(
            Hostmask('nick1', None, None).matches(r'nick\*'))
        self.assertFalse(
            Hostmask('nick', None, None).matches('ni\\ck'))

    def test_case_insensitive_matches(self):
        rfc1459 = case_mapping_by_name('rfc1459')
        self.assertFalse(
            Hostmask('NICK', 'USER', 'HOST').matches('nick!user@host'))
        self.assertTrue(
            Hostmask('NICK', 'USER', 'HOST').matches('nick!user@host', rfc1459))
        self.assertTrue(
            Hostmask('nick', 'USER', 'HOST').matches('nick!user@host'))
        self.assertTrue(
            Hostmask('nick[a]', 'user', 'host').matches('nick{a}!user@host',
                                                        rfc1459))

    def test_has_wildcard(self):
        self.assertFalse(Hostmask('nick', 'user', 'host').has_wildcard)
        self.assertTrue(Hostmask('nick', None, None).has_wildcard)
        self.assertTrue(Hostmask('nick*', 'user', 'host').has_wildcard)
        self.assertFalse(Hostmask(r'nick\*', 'user', 'host').has_wildcard)
