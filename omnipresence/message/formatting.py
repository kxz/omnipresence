# -*- test-case-name: omnipresence.test.test_formatting -*-
"""Operations on mIRC-style message formatting."""


import re


#: A regex matching mIRC-style formatting control codes.
#
# <http://forum.egghelp.org/viewtopic.php?p=94834>
# <http://www.mirc.com/help/colors.html>
CONTROL_CODES = re.compile(r"""
    \x02 |             # Bold
    \x03(?:            # Color
      ([0-9]{1,2})(?:  # Optional foreground number (from 0 or 00 to 99)
        ,([0-9]{1,2})  # Optional background number (from 0 or 00 to 99)
      )?
    )? |
    \x0F |             # Normal (revert to default formatting)
    \x16 |             # Reverse video (sometimes rendered as italics)
    \x1F               # Underline
    """, re.VERBOSE)


def remove_formatting(string):
    """Remove mIRC-style formatting control codes from a string."""
    return CONTROL_CODES.sub('', string)


def unclosed_formatting(string):
    """Return a frozenset containing any unclosed mIRC-style formatting
    codes in a string."""
    fg = bg = ''
    bold = reverse = underline = False
    # ^O resets everything, so we split on it and only operate on the
    # portion of the string that is beyond the rightmost occurrence.
    for match in CONTROL_CODES.finditer(string.rsplit('\x0F')[-1]):
        code = match.group(0)
        if code.startswith('\x03'):
            if code == '\x03':
                # No color codes were specified.  Reset everything.
                fg = bg = ''
            else:
                fg = match.group(1) or fg
                bg = match.group(2) or bg
        elif code == '\x02':
            bold = not bold
        elif code == '\x16':
            reverse = not reverse
        elif code == '\x1F':
            underline = not underline
    # Thankfully, we don't have to keep track of proper nesting.
    open_codes = []
    if fg or bg:
        open_codes.append('\x03' + fg + (',' + bg if bg else ''))
    if bold:
        open_codes.append('\x02')
    if reverse:
        open_codes.append('\x16')
    if underline:
        open_codes.append('\x1F')
    return frozenset(open_codes)
