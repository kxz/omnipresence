# -*- test-case-name: omnipresence.test.test_ircutil -*-
"""IRC-specific utility functions."""
import re
import string

# Common IRC formatting control codes
# <http://forum.egghelp.org/viewtopic.php?p=94834>
# <http://www.mirc.com/help/colors.html>
CONTROL_CODES = re.compile(r"""
(
  \x02              # Bold
  |
  \x03(             # Color
    [0-9]?[0-9](    # Optional foreground number (from 0 or 00 to 99)
      ,[0-9]?[0-9]  # Optional background number (from 0 or 00 to 99)
    )?
  )?
  |
  \x0F              # Normal (revert to default formatting)
  |
  \x16              # Reverse video (sometimes rendered as italics)
  |
  \x1F              # Underline
)
""", re.VERBOSE)

# Case mappings for canonicalize()
TRANS_ASCII = string.maketrans(string.ascii_uppercase + r'\[]~',
                               string.ascii_lowercase + r'|{}^')
TRANS_RFC1459 = string.maketrans(string.ascii_uppercase + r'\[]~',
                                 string.ascii_lowercase + r'|{}^')


def canonicalize(name, casemapping='rfc1459'):
    """Convert an IRC name to its "canonical" lowercase representation.
    The *casemapping* parameter determines the case folding rules used
    to perform the conversion:

    * ``'ascii'`` treats the letters *A-Z* as uppercase versions of the
      letters *a-z*.
    * ``'strict-rfc1459'`` uses the ``'ascii'`` case mappings, further
      treating *{}|* as the lowercase versions of *[]\*.
    * ``'rfc1459'`` uses the ``'strict-rfc1459'`` case mappings, further
      treating *~* as the lowercase version of *^*.

    The default value is ``'rfc1459'``.  If the value of *casemapping*
    is not one of the above values, it is treated as the default."""
    name = name.lower()
    if casemapping == 'ascii':
        return name
    name = name.replace('[',  '{').replace(']',  '}').replace('\\', '|')
    if casemapping == 'strict-rfc1459':
        return name
    return name.replace('^',  '~')

def mode_string(set, modes, args):
    """Given the arguments "set", "modes", and "args" as passed to
    IRCClient.modeChanged by Twisted, return a reasonable string
    representation of the form +cov nick1 nick2."""
    # Call "filter" on args; otherwise, in cases where a mode takes
    # no arguments, None will appear in the args tuple, causing the
    # string join to blow up.
    args = filter(None, args)
    return (('+' if set else '-') +
            modes + (' ' + ' '.join(args) if args else ''))

def parse_hostmask(hostmask):
    """Turn a hostmask in the form *nick!user@host* into a 3-tuple
    ``(nick, user, host)``, with ``None`` appearing in place of any
    components not present in the original hostmask."""
    nick, _, rest = hostmask.partition('!')
    user, _, host = rest.partition('@')
    return (nick, user or None, host or None)

def remove_control_codes(s):
    """Remove IRC formatting control codes from a string."""
    return CONTROL_CODES.sub('', s)

def unclosed_formatting_codes(s):
    """Return a list of the unclosed IRC formatting codes in a string."""
    fg = bg = ''
    bold = reverse = underline = False
    # ^O resets everything, so we split on it and only operate on the
    # portion of the string that is beyond the rightmost occurrence.
    for match in CONTROL_CODES.finditer(s.rsplit('\x0F')[-1]):
        code = match.group(0)
        if code.startswith('\x03'):
            # Foreground and background colors can be set separately as
            # long as at least one is specified.
            if code[1:]:
                new_fg, _, new_bg = code[1:].partition(',')
                fg = new_fg or fg
                bg = new_bg or bg
            # Nothing was specified; reset the whole thing.
            else:
                fg = bg = ''
        elif code == '\x02':
            bold = not bold
        elif code == '\x16':
            reverse = not reverse
        elif code == '\x1F':
            underline = not underline
    # Thankfully, we don't have to keep track of proper nesting.
    open_codes = []
    if fg or bg:
        open_codes.append('\x03%s,%s' % (fg, bg))
    if bold:
        open_codes.append('\x02')
    if reverse:
        open_codes.append('\x16')
    if underline:
        open_codes.append('\x1F')
    return open_codes

def close_formatting_codes(s):
    """Return the given string with all open formatting codes closed."""
    open_codes = unclosed_formatting_codes(s)
    for i in xrange(len(open_codes)):
        if open_codes[i].startswith('\x03'):
            open_codes[i] = '\x03'
    return s + ''.join(open_codes)