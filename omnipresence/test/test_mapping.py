"""Unit tests for IRC case mappings."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from .. import mapping


EXPECTED = {
    # Strings to compare        # Equal under...
    ('#foo', '#foo'):           ('ascii', 'strict-rfc1459', 'rfc1459'),
    ('#foo', '#FOO'):           ('ascii', 'strict-rfc1459', 'rfc1459'),
    ('#FOO', '#FOO'):           ('ascii', 'strict-rfc1459', 'rfc1459'),
    ('nick[tag]', 'nick{tag}'): ('strict-rfc1459', 'rfc1459'),
    ('foo|bar', 'foo\\bar'):    ('strict-rfc1459', 'rfc1459'),
    ('hello~', 'hello^'):       ('rfc1459'),
    ('#foo', '#bar'):           tuple()
}


class CaseMappingTestCase(unittest.TestCase):
    def test_equality(self):
        for (a, b), equal_case_mappings in EXPECTED.iteritems():
            for name in mapping.CASE_MAPPINGS:
                case_mapping = mapping.by_name(name)
                self.assertIs(case_mapping.equates(a, b),
                              name in equal_case_mappings)


class CaseMappedDictTestCase(unittest.TestCase):
    def test_lookup(self):
        for (a, b), equal_case_mappings in EXPECTED.iteritems():
            for name in mapping.CASE_MAPPINGS:
                d = mapping.CaseMappedDict(case_mapping=mapping.by_name(name))
                d[a] = 1
                if name in equal_case_mappings:
                    self.assertEqual(d.get(b), 1)
                else:
                    self.assertIsNone(d.get(b))
