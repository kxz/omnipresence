# -*- test-case-name: omnipresence.test.test_humanize
"""Functions for presenting data in human-readable forms."""


from datetime import datetime, timedelta
import re


def ago(then, now=None):
    """Given a `~datetime.datetime` object, return an English string
    giving an approximate relative time, such as "5 days ago"."""
    if not now:  # then when?
        now = datetime.now()
    delta = now - then
    if delta.days == 0:
        if delta.seconds < 10:
            return 'just now'
        if delta.seconds < 60:
            return '{} seconds ago'.format(delta.seconds)
        if delta.seconds < 120:
            return 'a minute ago'
        if delta.seconds < 3600:
            return '{} minutes ago'.format(delta.seconds / 60)
        if delta.seconds < 7200:
            return 'an hour ago'
        return '{} hours ago'.format(delta.seconds / 3600)
    if delta.days == 1:
        return 'yesterday'
    if delta.days < 7:
        return '{} days ago'.format(delta.days)
    if delta.days < 14:
        return 'a week ago'
    return '{} weeks ago'.format(delta.days / 7)


def andify(seq, two_comma=False):
    """Join the elements of a sequence and return a string of the form
    "*x* and *y*" for a two-element list, or "*x*, *y*, and *z*" for
    three or more elements.  If *two_comma* is True, insert a comma
    before "and" even if the list is only two elements long ("*x*, and
    *y*")."""
    if len(seq) > 2:
        return ', '.join(seq[:-2] + [', and '.join(seq[-2:])])
    if two_comma:
        return ', and '.join(seq)
    return ' and '.join(seq)


DURATION_RE = re.compile(
    r'^(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$',
    re.IGNORECASE)
DURATION_GROUPS = ['weeks', 'days', 'hours', 'minutes', 'seconds']


def duration_to_timedelta(duration):
    """Convert a duration string of the form "_w_d_h_m_s" into a
    `~datetime.timedelta` object."""
    match = DURATION_RE.match(duration)
    if match is None:
        return timedelta()
    kwargs = dict(((DURATION_GROUPS[i], int(value, 10))
                   for (i, value) in enumerate(match.groups('0'))))
    return timedelta(**kwargs)


def readable_duration(duration):
    """Convert a duration string of the form "_w_d_h_m_s" to a plain
    English representation such as "2 weeks, 5 days, and 20 hours"."""
    match = DURATION_RE.match(duration)
    if match is None:
        return 'instant'
    components = []
    for i, value in enumerate(match.groups()):
        if not value:
            continue
        unit = DURATION_GROUPS[i]
        value = int(value, 10)
        if value == 1:
            # Thankfully, all of these words are simple plurals.
            if components:
                # Add the value: "2 weeks, 1 day, 3 hours".
                component = '1 {}'.format(unit[:-1])
            else:
                # Skip the value: "past day" instead of "past 1 day".
                component = unit[:-1]
        else:
            component = '{} {}'.format(value, unit)
        components.append(component)
    return andify(components)
