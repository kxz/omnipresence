# -*- test-case-name: omnipresence.test.test_case_mapping -*-
"""Operations on IRC case mappings."""


from string import maketrans, ascii_lowercase, ascii_uppercase

from twisted.python.util import InsensitiveDict


KNOWN_CASE_MAPPINGS = {
    'ascii':          (ascii_lowercase,           ascii_uppercase),
    'rfc1459':        (ascii_lowercase + r'|{}~', ascii_uppercase + r'\[]^'),
    'strict-rfc1459': (ascii_lowercase + r'|{}',  ascii_uppercase + r'\[]')}


class CaseMapping(object):
    """Provides convenience methods for bidirectional string translation
    given a mapping of characters from *lower* to *upper*."""

    def __init__(self, lower, upper):
        self.lower_trans = maketrans(upper, lower)
        self.upper_trans = maketrans(lower, upper)

    @classmethod
    def by_name(cls, name):
        """Return an IRC case mapping given the *name* used in the
        ``CASEMAPPING`` parameter of a ``RPL_ISUPPORT`` IRC message
        (numeric 005).  The following mapping names are recognized:

        .. describe:: ascii

           Treats the letters *A-Z* as uppercase versions of the letters
           *a-z*.

        .. describe:: strict-rfc1459

           Extends the ``ascii`` case mapping to further treat *{}|* as
           the lowercase versions of *\\[\\]\\\\*.  This matches the
           rules specified in :rfc:`1459#section-2.2`.

        .. describe:: rfc1459

           Extends the ``strict-rfc1459`` case mapping to further treat
           *~* as the lowercase version of *^*.  This corresponds to
           most servers' actual implementation of the RFC 1459 rules.

        `ValueError` is raised on an unrecognized mapping name.
        """
        if name in KNOWN_CASE_MAPPINGS:
            return cls(*KNOWN_CASE_MAPPINGS[name])
        raise ValueError('unrecognized case mapping "{}"'.format(name))

    def __hash__(self):
        # Translation tables are just strings, which are hashable.
        return hash(self.lower_trans)

    def __eq__(self, other):
        if isinstance(other, CaseMapping):
            return self.lower_trans == other.lower_trans
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal

    def equates(self, one, two):
        """Return a boolean value indicating whether *a* and *b* are
        equal under this case mapping."""
        return (one.translate(self.lower_trans) ==
                two.translate(self.lower_trans))

    def lower(self, string):
        """Return a copy of *string* with uppercase characters converted
        to lowercase according to this case mapping."""
        return string.translate(self.lower_trans)

    def upper(self, string):
        """Return a copy of *string* with lowercase characters converted
        to uppercase according to this case mapping."""
        return string.translate(self.upper_trans)


class CaseMappedDict(InsensitiveDict):
    """A dictionary whose keys are treated case-insensitively according
    to a `.CaseMapping` or mapping name string (as given to `.by_name`)
    provided on instantiation."""

    def __init__(self, initial=None, case_mapping=None):
        if case_mapping is None:
            case_mapping = CaseMapping.by_name('rfc1459')
        elif isinstance(case_mapping, basestring):
            case_mapping = CaseMapping.by_name(case_mapping)
        self.case_mapping = case_mapping
        InsensitiveDict.__init__(self, initial, preserve=1)

    def _lowerOrReturn(self, key):
        """Return a lowercase version of *key* according to the case
        mapping in effect for this object."""
        # Why would anyone use this for non-string keys?  Whatever.
        if isinstance(key, basestring):
            return self.case_mapping.lower(key)
        return key
