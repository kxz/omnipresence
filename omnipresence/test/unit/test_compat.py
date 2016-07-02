"""Tests for Python 3 compatibility shims."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial.unittest import TestCase

from ...compat import length_hint


class LengthHintTestCase(TestCase):
    # From CPython's Lib/test/test_py.

    def test_length_hint(self):
        class X(object):
            def __init__(self, value):
                self.value = value

            def __length_hint__(self):
                if type(self.value) is type:
                    raise self.value
                else:
                    return self.value

        self.assertEqual(length_hint([], 2), 0)
        self.assertEqual(length_hint(iter([1, 2, 3])), 3)

        self.assertEqual(length_hint(X(2)), 2)
        self.assertEqual(length_hint(X(NotImplemented), 4), 4)
        self.assertEqual(length_hint(X(TypeError), 12), 12)
        with self.assertRaises(TypeError):
            length_hint(X("abc"))
        with self.assertRaises(ValueError):
            length_hint(X(-2))
        with self.assertRaises(LookupError):
            length_hint(X(LookupError))
