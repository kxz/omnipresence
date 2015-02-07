# -*- test-case-name: omnipresence.test.test_mapping -*-
"""Operations on IRC case mappings."""


from string import maketrans, ascii_lowercase, ascii_uppercase

from twisted.python.util import InsensitiveDict


class CaseMapping(object):
    """Provides convenience methods for bidirectional string translation
    given a mapping of characters from *lower* to *upper*."""

    def __init__(self, lower, upper):
        self.lower_trans = maketrans(upper, lower)
        self.upper_trans = maketrans(lower, upper)

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


CASE_MAPPINGS = {
    'ascii':          CaseMapping(ascii_lowercase,
                                  ascii_uppercase),
    'rfc1459':        CaseMapping(ascii_lowercase + r'|{}~',
                                  ascii_uppercase + r'\[]^'),
    'strict-rfc1459': CaseMapping(ascii_lowercase + r'|{}',
                                  ascii_uppercase + r'\[]'),
}


def by_name(name):
    """Given the *name* of an IRC case mapping, as commonly specified by
    the value of the ``CASEMAPPING`` parameter in ``RPL_ISUPPORT``
    messages (numeric 005), return a `.CaseMapping` object that
    implements that mapping.  The following mapping names are
    recognized:

    .. describe:: ascii

       Treats the letters *A-Z* as uppercase versions of the letters
       *a-z*.

    .. describe:: strict-rfc1459

       Extends the ``ascii`` case mapping to further treat *{}|* as the
       lowercase versions of *\\[\\]\\\\*.  This matches the rules
       specified in :rfc:`1459#section-2.2`.


    .. describe:: rfc1459

       Extends the ``strict-rfc1459`` case mapping to further treat *~*
       as the lowercase version of *^*.  This corresponds to most
       servers' actual implementation of the RFC 1459 rules.

    `~exceptions.ValueError` is raised on an unrecognized mapping name.
    """
    if name in CASE_MAPPINGS:
        return CASE_MAPPINGS[name]
    raise ValueError('unrecognized case mapping "{0}"'.format(name))


class CaseMappedDict(InsensitiveDict):
    """A dictionary whose keys are treated case-insensitively according
    to a `.CaseMapping` or mapping name string (as given to `.by_name`)
    provided on instantiation."""

    def __init__(self, initial=None, case_mapping=None):
        if case_mapping is None:
            case_mapping = CASE_MAPPINGS['rfc1459']
        elif isinstance(case_mapping, basestring):
            case_mapping = by_name(case_mapping)
        self.case_mapping = case_mapping
        InsensitiveDict.__init__(self, initial, preserve=1)

    def _lowerOrReturn(self, key):
        """Return a lowercase version of *key* according to the case
        mapping in effect for this object."""
        # Why would anyone use this for non-string keys?  Whatever.
        if isinstance(key, basestring):
            return self.case_mapping.lower(key)
        return key
