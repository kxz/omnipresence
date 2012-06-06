from twisted.trial import unittest

import omnipresence.ircutil as ircutil


class CanonicalizationTestCase(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(ircutil.canonicalize('#foo', 'ascii'),
                         ircutil.canonicalize('#foo', 'ascii'))
        self.assertEqual(ircutil.canonicalize('#foo', 'ascii'),
                         ircutil.canonicalize('#FOO', 'ascii'))
        self.assertEqual(ircutil.canonicalize('#FOO', 'ascii'),
                         ircutil.canonicalize('#foo', 'ascii'))
        self.assertEqual(ircutil.canonicalize('#FOO', 'ascii'),
                         ircutil.canonicalize('#FOO', 'ascii'))
        self.assertNotEqual(ircutil.canonicalize('nick[tag]', 'ascii'),
                            ircutil.canonicalize('nick{tag}', 'ascii'))
        self.assertNotEqual(ircutil.canonicalize('foo|bar', 'ascii'),
                            ircutil.canonicalize('foo\\bar', 'ascii'))
        self.assertNotEqual(ircutil.canonicalize('hello~', 'ascii'),
                            ircutil.canonicalize('hello^', 'ascii'))
        self.assertNotEqual(ircutil.canonicalize('#foo', 'ascii'),
                            ircutil.canonicalize('#bar', 'ascii'))

    def test_rfc1459(self):
        self.assertEqual(ircutil.canonicalize('#foo', 'rfc1459'),
                         ircutil.canonicalize('#foo', 'rfc1459'))
        self.assertEqual(ircutil.canonicalize('#foo', 'rfc1459'),
                         ircutil.canonicalize('#FOO', 'rfc1459'))
        self.assertEqual(ircutil.canonicalize('#FOO', 'rfc1459'),
                         ircutil.canonicalize('#foo', 'rfc1459'))
        self.assertEqual(ircutil.canonicalize('#FOO', 'rfc1459'),
                         ircutil.canonicalize('#FOO', 'rfc1459'))
        self.assertEqual(ircutil.canonicalize('nick[tag]', 'rfc1459'),
                         ircutil.canonicalize('nick{tag}', 'rfc1459'))
        self.assertEqual(ircutil.canonicalize('foo|bar', 'rfc1459'),
                         ircutil.canonicalize('foo\\bar', 'rfc1459'))
        self.assertEqual(ircutil.canonicalize('hello~', 'rfc1459'),
                         ircutil.canonicalize('hello^', 'rfc1459'))
        self.assertNotEqual(ircutil.canonicalize('#foo', 'rfc1459'),
                            ircutil.canonicalize('#bar', 'rfc1459'))

    def test_strict_rfc1459(self):
        self.assertEqual(ircutil.canonicalize('#foo', 'strict-rfc1459'),
                         ircutil.canonicalize('#foo', 'strict-rfc1459'))
        self.assertEqual(ircutil.canonicalize('#foo', 'strict-rfc1459'),
                         ircutil.canonicalize('#FOO', 'strict-rfc1459'))
        self.assertEqual(ircutil.canonicalize('#FOO', 'strict-rfc1459'),
                         ircutil.canonicalize('#foo', 'strict-rfc1459'))
        self.assertEqual(ircutil.canonicalize('#FOO', 'strict-rfc1459'),
                         ircutil.canonicalize('#FOO', 'strict-rfc1459'))
        self.assertEqual(ircutil.canonicalize('nick[tag]', 'strict-rfc1459'),
                         ircutil.canonicalize('nick{tag}', 'strict-rfc1459'))
        self.assertEqual(ircutil.canonicalize('foo|bar', 'strict-rfc1459'),
                         ircutil.canonicalize('foo\\bar', 'strict-rfc1459'))
        self.assertNotEqual(ircutil.canonicalize('hello~', 'strict-rfc1459'),
                            ircutil.canonicalize('hello^', 'strict-rfc1459'))
        self.assertNotEqual(ircutil.canonicalize('#foo', 'strict-rfc1459'),
                            ircutil.canonicalize('#bar', 'strict-rfc1459'))


class HostmaskTestCase(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(ircutil.parse_hostmask('nick!user@host'),
                         ('nick', 'user', 'host'))
        self.assertEqual(ircutil.parse_hostmask('nick!user'),
                         ('nick', 'user', None))
        self.assertEqual(ircutil.parse_hostmask('nick'),
                         ('nick', None, None))
        self.assertEqual(ircutil.parse_hostmask('parse@as.nick'),
                         ('parse@as.nick', None, None))
