"""General utility functions used within Omnipresence."""
import datetime

from twisted.words.protocols import irc


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

# <http://stackoverflow.com/questions/1809531/-/1820949>
def truncate_unicode(s, char_limit, byte_limit, encoding='utf-8'):
    """Truncate a Unicode string so that it fits both within the
    specified character limit and, when encoded in the given encoding,
    the specified byte limit.  Return the truncated string as a byte
    string."""
    encoded = s[:char_limit].encode(encoding)[:byte_limit]
    return encoded.decode(encoding, 'ignore').encode(encoding)
