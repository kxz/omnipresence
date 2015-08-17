"""Unit tests for IRC case mappings."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial.unittest import TestCase

from ..case_mapping import CaseMapping, KNOWN_CASE_MAPPINGS, CaseMappedDict


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


class EqualityTester(object):
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value

    def __ne__(self, other):
        return self.value


class CaseMappingTestCase(TestCase):
    def test_hash(self):
        self.assertEqual(hash(CaseMapping('a', 'b')),
                         hash(CaseMapping('a', 'b')))
        self.assertNotEqual(hash(CaseMapping('a', 'b')),
                            hash(CaseMapping('a', 'c')))

    def test_equality(self):
        self.assertEqual(CaseMapping('a', 'b'), CaseMapping('a', 'b'))
        self.assertNotEqual(CaseMapping('a', 'b'), CaseMapping('a', 'c'))
        self.assertTrue(CaseMapping('a', 'b') == EqualityTester(True))
        self.assertFalse(CaseMapping('a', 'b') == EqualityTester(False))
        self.assertTrue(CaseMapping('a', 'b') != EqualityTester(True))
        self.assertFalse(CaseMapping('a', 'b') != EqualityTester(False))

    def test_equates(self):
        for (a, b), equal_KNOWN_case_mappings in EXPECTED.iteritems():
            for name in KNOWN_CASE_MAPPINGS:
                case_mapping = CaseMapping.by_name(name)
                self.assertIs(case_mapping.equates(a, b),
                              name in equal_KNOWN_case_mappings)

    def test_upper_equates(self):
        for (a, b), equal_KNOWN_case_mappings in EXPECTED.iteritems():
            for name in KNOWN_CASE_MAPPINGS:
                case_mapping = CaseMapping.by_name(name)
                self.assertIs(
                    case_mapping.upper(a) == case_mapping.upper(b),
                    name in equal_KNOWN_case_mappings)

    def test_unrecognized_name(self):
        self.assertRaises(ValueError, CaseMapping.by_name, 'spam')


class CaseMappedDictTestCase(TestCase):
    def test_lookup(self):
        for (a, b), equal_KNOWN_case_mappings in EXPECTED.iteritems():
            for name in KNOWN_CASE_MAPPINGS:
                d = CaseMappedDict(case_mapping=name)
                d[a] = 1
                if name in equal_KNOWN_case_mappings:
                    self.assertEqual(d.get(b), 1)
                else:
                    self.assertIsNone(d.get(b))

    def test_nonstring_keys(self):
        d = CaseMappedDict()
        d[9001] = 1
        self.assertEqual(d[9001], 1)
