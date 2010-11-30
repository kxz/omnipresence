from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, NavigableString
from ConfigParser import SafeConfigParser
import datetime
import re

# Common IRC formatting control codes
# <http://forum.egghelp.org/viewtopic.php?p=94834>
# <http://www.mirc.com/help/colors.html>
#
# \x02: Bold
# \x03: Color (optionally followed by fg,bg each from 0 or 00 to 99)
# \x0F: Normal (default formatting)
# \x16: Reverse video (sometimes rendered as italics)
# \x1F: Underline
CONTROL_CODES = re.compile(r'(\x02|\x03([0-9]?[0-9](,[0-9]?[0-9])?)?)|\x0F|\x16|\x1F')

HTML_HEX_REFS = re.compile(r'&#x([0-9a-fA-F]+);')


class OmnipresenceConfigParser(SafeConfigParser):
    """An extension of ConfigParser with Omnipresence-specific methods."""
    # Option names need to be parsed case-sensitively, as they are used to 
    # determine things like modules to import.
    optionxform = str

    def getdefault(self, section, option, default):
        """Get the value of the specified option in the specified section, or 
        return the given default if this option does not exist."""
        if self.has_option(section, option):
            return self.get(section, option)

        return default

    def getspacelist(self, *args, **kwargs):
        """Get the value of the specified option converted to a list, split 
        on whitespace."""
        return self.get(*args, **kwargs).split()


def ago(then):
    """Given a datetime object, return a string giving an approximate relative 
    time, such as "5 days ago"."""
    delta = datetime.datetime.now() - then
    
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

def canonicalize(name):
    """Convert an IRC name to its "canonical" lowercase representation."""
    return name.lower().replace('[',  '{').replace(']',  '}') \
                       .replace('\\', '|').replace('^',  '~')

def decode_html_entities(s):
    """Convert HTML entities in a string to their Unicode character 
    equivalents."""
    s = BeautifulStoneSoup(s,
                           convertEntities=BeautifulStoneSoup.HTML_ENTITIES) \
                          .contents[0]
    # BeautifulStoneSoup doesn't parse hexadecimal character references
    s = HTML_HEX_REFS.sub(lambda x: unichr(int(x.group(1), 16)), s)
    return s

def remove_control_codes(s):
    """Remove IRC formatting control codes from a string."""
    return CONTROL_CODES.sub('', s)

def textify_html(soup):
    """Convert a BeautifulSoup element's contents to plain text."""
    result = u''
    
    for k in soup.contents:
        if isinstance(k, NavigableString):
            result += decode_html_entities(k)
        elif hasattr(k, 'name'):  # is another soup element
            if k.name == u'sup':
                result += u'^'
            
            result += textify_html(k)
    
    return result
