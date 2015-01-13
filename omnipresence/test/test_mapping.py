"""Unit tests for IRC case mappings."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from .. import mapping


class CaseMappingTestCase(unittest.TestCase):
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

    def test_equality(self):
        for (a, b), equal_case_mappings in self.expected.iteritems():
            for name in ('ascii', 'strict-rfc1459', 'rfc1459'):
                case_mapping = mapping.by_name(name)
                self.assertIs(case_mapping.equates(a, b),
                              name in equal_case_mappings)
