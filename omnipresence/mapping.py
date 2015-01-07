# -*- test-case-name: omnipresence.test.test_mapping -*-
"""Operations on IRC case mappings."""


import string


class CaseMapping(object):
    """Provides convenience methods for bidirectional string translation
    given a mapping of characters from *lower* to *upper*."""

    def __init__(self, lower, upper):
        self.lower_trans = string.maketrans(upper, lower)
        self.upper_trans = string.maketrans(lower, upper)

    def equates(self, a, b):
        """Return a boolean value indicating whether *a* and *b* are
        equal under this case mapping."""
        return a.translate(self.lower_trans) == b.translate(self.lower_trans)

    def lower(self, s):
        """Return a copy of *s* with uppercase characters converted to
        lowercase according to this case mapping."""
        return s.translate(self.lower_trans)

    def upper(self, s):
        """Return a copy of *s* with lowercase characters converted to
        uppercase according to this case mapping."""
        return s.translate(self.upper_trans)


CASE_MAPPINGS = {
    'ascii':          CaseMapping(string.ascii_lowercase,
                                  string.ascii_uppercase),
    'rfc1459':        CaseMapping(string.ascii_lowercase + r'|{}~',
                                  string.ascii_uppercase + r'\[]^'),
    'strict-rfc1459': CaseMapping(string.ascii_lowercase + r'|{}',
                                  string.ascii_uppercase + r'\[]'),
}


def by_name(name):
    """Given the *name* of an IRC case mapping, as commonly specified by
    the value of the ``CASEMAPPING`` parameter in ``RPL_ISUPPORT``
    messages (numeric 005), return a :py:class:`.CaseMapping` object
    that implements that mapping.  The following mapping names are
    recognized:

    * ``'ascii'`` treats the letters *A-Z* as uppercase versions of the
      letters *a-z*.
    * ``'strict-rfc1459'`` uses the ``'ascii'`` case mappings, further
      treating *{}|* as the lowercase versions of *\\[\\]\\\\*.  This
      matches the rules specified in :rfc:`1459#section-2.2`.
    * ``'rfc1459'`` uses the ``'strict-rfc1459'`` case mappings, further
      treating *~* as the lowercase version of *^*.  This corresponds to
      most servers' actual implementation of the RFC 1459 rules.

    :py:class:`ValueError` is raised on an unrecognized mapping name.
    """
    if name in CASE_MAPPINGS:
        return CASE_MAPPINGS[name]
    raise ValueError('unrecognized case mapping "{0}"'.format(name))
