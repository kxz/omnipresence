from twisted.trial import unittest

import omnipresence.ircutil as ircutil


class CanonicalizationTestCase(unittest.TestCase):
    expected = {
        # Strings to compare        # Equal under...
        ('#foo', '#foo'):           ('ascii', 'strict-rfc1459', 'rfc1459'),
        ('#foo', '#FOO'):           ('ascii', 'strict-rfc1459', 'rfc1459'),
        ('#FOO', '#FOO'):           ('ascii', 'strict-rfc1459', 'rfc1459'),
        ('nick[tag]', 'nick{tag}'): ('strict-rfc1459', 'rfc1459'),
        ('foo|bar', 'foo\\bar'):    ('strict-rfc1459', 'rfc1459'),
        ('hello~', 'hello^'):       ('rfc1459'),
        ('#foo', '#bar'):           tuple()
    }

    def test_canonicalization(self):
        for (a, b), equal_casemappings in self.expected.iteritems():
            for casemapping in ('ascii', 'strict-rfc1459', 'rfc1459'):
                ca = ircutil.canonicalize(a, casemapping)
                cb = ircutil.canonicalize(b, casemapping)
                if casemapping in equal_casemappings:
                    self.assertEqual(ca, cb)
                else:
                    self.assertNotEqual(ca, cb)


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
