"""Unit tests for IRC case mappings."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial.unittest import TestCase

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


class EqualityTester(object):
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value

    def __ne__(self, other):
        return self.value


class CaseMappingTestCase(TestCase):
    def test_hash(self):
        self.assertEqual(hash(mapping.CaseMapping('a', 'b')),
                         hash(mapping.CaseMapping('a', 'b')))
        self.assertNotEqual(hash(mapping.CaseMapping('a', 'b')),
                            hash(mapping.CaseMapping('a', 'c')))

    def test_equality(self):
        self.assertEqual(mapping.CaseMapping('a', 'b'),
                         mapping.CaseMapping('a', 'b'))
        self.assertNotEqual(mapping.CaseMapping('a', 'b'),
                            mapping.CaseMapping('a', 'c'))
        self.assertTrue(mapping.CaseMapping('a', 'b') ==
                        EqualityTester(True))
        self.assertFalse(mapping.CaseMapping('a', 'b') ==
                         EqualityTester(False))
        self.assertTrue(mapping.CaseMapping('a', 'b') !=
                        EqualityTester(True))
        self.assertFalse(mapping.CaseMapping('a', 'b') !=
                         EqualityTester(False))

    def test_equates(self):
        for (a, b), equal_case_mappings in EXPECTED.iteritems():
            for name in mapping.CASE_MAPPINGS:
                case_mapping = mapping.by_name(name)
                self.assertIs(case_mapping.equates(a, b),
                              name in equal_case_mappings)

    def test_upper_equates(self):
        for (a, b), equal_case_mappings in EXPECTED.iteritems():
            for name in mapping.CASE_MAPPINGS:
                case_mapping = mapping.by_name(name)
                self.assertIs(
                    case_mapping.upper(a) == case_mapping.upper(b),
                    name in equal_case_mappings)

    def test_unrecognized_name(self):
        self.assertRaises(ValueError, mapping.by_name, 'spam')


class CaseMappedDictTestCase(TestCase):
    def test_no_mapping(self):
        self.assertIs(mapping.CaseMappedDict().case_mapping,
                      mapping.CASE_MAPPINGS['rfc1459'])

    def test_lookup(self):
        for (a, b), equal_case_mappings in EXPECTED.iteritems():
            for name in mapping.CASE_MAPPINGS:
                d = mapping.CaseMappedDict(case_mapping=name)
                d[a] = 1
                if name in equal_case_mappings:
                    self.assertEqual(d.get(b), 1)
                else:
                    self.assertIsNone(d.get(b))

    def test_nonstring_keys(self):
        d = mapping.CaseMappedDict()
        d[9001] = 1
        self.assertEqual(d[9001], 1)
