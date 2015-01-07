# -*- test-case-name: omnipresence.test.test_hostmask -*-
"""Operations on IRC hostmasks."""


from collections import namedtuple
import itertools
import re


def _mask_as_regex(mask):
    """Return a regex object corresponding to the IRC hostmask pattern
    string *mask*."""
    pattern = ''
    backslash = False  # was the last character a backslash?
    for c in mask:
        if backslash:
            # The RFC doesn't state this explicitly, but the provided
            # BNF syntax defines the backslash as an escape character
            # only when it precedes a wildcard; otherwise, it's just a
            # backslash.  I don't really see this coming up much in
            # practice, since the characters '*', '?', and '\' don't
            # ever come up in real hostmasks, but it's best to follow
            # the rules as closely as possible.
            #
            # Technically, we parse incorrectly on masks like '\\*',
            # which should match a single backslash followed by an
            # asterisk, not two backslashes followed by any sequence of
            # characters, but someone who comes up with a mask like that
            # doesn't deserve to use this function.
            if c == '*' or c == '?':
                pattern += '\\' + c
            else:
                pattern += '\\\\' + re.escape(c)
            backslash = False
        else:
            if c == '\\':
                backslash = True
            elif c == '*':
                pattern += '.*'
            elif c == '?':
                pattern += '.'
            else:
                pattern += re.escape(c)
    # Anchoring the regex with '\A' and '\Z' ensures that the pattern
    # matches the entire string, not just a portion.
    return re.compile(r'\A' + pattern + r'\Z')


class Hostmask(namedtuple('Hostmask', ('nick', 'user', 'host'))):
    """Represents an IRC hostmask (sometimes called a message prefix) of
    the form ``nick!user@host``.  The *user* and *host* attributes are
    optional, and default to ``None`` if not present."""

    @classmethod
    def from_string(cls, string):
        """Return a new :py:class:`~.Hostmask` object parsed from
        *string*, according to the definition of ``<prefix>`` in
        :rfc:`1459#section-2.3.1`."""
        rest, _, host = string.partition('@')
        nick, _, user = rest.partition('!')
        return cls(nick, user or None, host or None)

    def matches(self, other, case_mapping=None):
        """Check whether this hostmask matches the pattern in *other*,
        which can be a :py:class:`.Hostmask` object or a string in the
        form ``"nick!user@host"``, according to the wildcard expansion
        rules in :rfc:`2812#section-2.5`.  A :py:class:`.CaseMapping`
        object may optionally be provided, in which case nicks are
        compared case-insensitively according to the mapping's rules;
        otherwise, nick comparisons are fully case-sensitive.  Users and
        hosts are always compared case-insensitively, using normal ASCII
        case folding rules.

        Briefly, ``*`` and ``?`` wildcards match zero or more and
        exactly one non-delimiter character, respectively; a backslash
        can be used to escape these special characters.  Components that
        equal ``None`` are assumed to match all possible values for that
        component.
        """
        me = self
        if isinstance(other, str):
            other = Hostmask.from_string(other)
        me, other = map(
            lambda x: x._replace(
                nick=case_mapping.lower(x.nick) if case_mapping else x.nick,
                user=x.user.lower() if x.user else None,
                host=x.host.lower() if x.host else None),
            (me, other))
        for mine, theirs in itertools.izip(me, other):
            if mine is None or theirs is None:
                continue
            if not _mask_as_regex(theirs).match(mine):
                return False
        return True

    def __str__(self):
        return '%s%s%s' % (self.nick,
                           ('!' + self.user) if self.user else '',
                           ('@' + self.host) if self.host else '')