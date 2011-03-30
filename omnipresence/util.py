"""General utility functions used within Omnipresence."""
import datetime
import re

from twisted.words.protocols import irc


DURATION_RE = re.compile("""^(?:(?P<weeks>\d+)w)?
                             (?:(?P<days>\d+)d)?
                             (?:(?P<hours>\d+)h)?
                             (?:(?P<minutes>\d+)m)?
                             (?:(?P<seconds>\d+)s)?$""", re.VERBOSE)

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
    """Given a list, join its elements to form a list of the form "x 
    and y" or "x, y, and z".  If "two_comma" is True, return "x, and y" 
    for lists that are two elements long."""
    if len(seq) > 2:
        return ', '.join(seq[:-2] + [', and '.join(seq[-2:])])
    
    if two_comma:
        return ', and '.join(seq)
    
    return ' and '.join(seq)

def duration_to_timedelta(duration):
    """Convert a duration of the form "?w?d?h?m?s" into a timedelta
    object, where individual components are optional."""
    match = DURATION_RE.match(duration)

    if match:
        kwargs = match.groupdict('0')
        kwargs = dict(((key, int(value, 10))
                       for (key, value) in kwargs.iteritems()))
        return datetime.timedelta(**kwargs)
    
    return datetime.timedelta(0)
