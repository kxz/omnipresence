"""General utility functions used within Omnipresence."""
import datetime
import re

from twisted.words.protocols import irc


DURATION_RE = re.compile(r'^(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$',
                         re.IGNORECASE | re.VERBOSE)

DURATION_GROUPS = ['weeks', 'days', 'hours', 'minutes', 'seconds']

def ago(then, now=None):
    """Given a datetime object, return a string giving an approximate relative
    time, such as "5 days ago"."""
    if not now:
        now = datetime.datetime.now()

    delta = now - then

    if delta.days == 0:
        if delta.seconds < 10:
            return "just now"
        elif delta.seconds < 60:
            return "%d seconds ago" % (delta.seconds)
        elif delta.seconds < 120:
            return "a minute ago"
        elif delta.seconds < 3600:
            return "%d minutes ago" % (delta.seconds / 60)
        elif delta.seconds < 7200:
            return "an hour ago"
        else:
            return "%d hours ago" % (delta.seconds / 3600)
    elif delta.days == 1:
        return "yesterday"
    elif delta.days < 7:
        return "%d days ago" % (delta.days)
    elif delta.days < 14:
        return "a week ago"
    else:
        return "%d weeks ago" % (delta.days / 7)

def andify(seq, two_comma=False):
    """Given a list, join its elements and return a string of the form
    "*x* and *y*" for a two-element list, or "*x*, *y*, and *z*" for
    three or more elements.  If *two_comma* is True, insert a comma
    before "and" even if the list is only two elements long ("*x*, and
    *y*")."""
    if len(seq) > 2:
        return ', '.join(seq[:-2] + [', and '.join(seq[-2:])])

    if two_comma:
        return ', and '.join(seq)

    return ' and '.join(seq)

def duration_to_timedelta(duration):
    """Convert a duration of the form "?w?d?h?m?s" into a
    :py:class:`datetime.timedelta` object, where individual components
    are optional."""
    match = DURATION_RE.match(duration)

    if match:
        kwargs = dict(((DURATION_GROUPS[i], int(value, 10))
                       for (i, value) in enumerate(match.groups('0'))))
        return datetime.timedelta(**kwargs)

    return datetime.timedelta(0)

def readable_duration(duration):
    """Convert a duration of the form "?w?d?h?m?s" to a readable string
    representation of the form "2 weeks, 5 days, and 20 hours"."""
    match = DURATION_RE.match(duration)

    if match:
        components = []
        for (i, value) in enumerate(match.groups()):
            if value:
                unit = DURATION_GROUPS[i]
                value = int(value, 10)

                if value == 1:
                    # Thankfully, all of these words are simple plurals.
                    components.append(unit[:-1])
                else:
                    components.append('%d %s' % (value, unit))

        return andify(components)

    return 'instant'

# <http://stackoverflow.com/questions/1809531/-/1820949>
def truncate_unicode(s, char_limit, byte_limit, encoding='utf-8'):
    """Truncate a Unicode string so that it fits both within the
    specified character limit and, when encoded in the given encoding,
    the specified byte limit.  Return the truncated string as a byte
    string."""
    encoded = s[:char_limit].encode(encoding)[:byte_limit]
    return encoded.decode(encoding, 'ignore').encode(encoding)
