"""IRC-specific utility functions.

Most of the functions in this module are deprecated, having been
superseded by more powerful APIs elsewhere in Omnipresence.
"""


import re

from . import mapping
from .hostmask import Hostmask
from .message.formatting import remove_formatting, unclosed_formatting


def canonicalize(name, casemapping='rfc1459'):
    """Convert an IRC name to its "canonical" lowercase representation.
    The *casemapping* parameter determines the case folding rules used
    to perform the conversion.  It takes the same values as the *name*
    parameter to :py:meth:`~.mapping.by_name`, defaulting to
    ``'rfc1459'``.  If the value of *casemapping* is not one of the
    above values, it is treated as the default.

    .. deprecated:: 2.4
       Use the :py:mod:`~.mapping` API instead.
    """
    try:
        cm = mapping.by_name(casemapping)
    except ValueError:
        cm = mapping.by_name('rfc1459')
    return cm.lower(name)


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


# Aliases for methods that have simply been moved elsewhere.
parse_hostmask = Hostmask.from_string
remove_control_codes = remove_formatting
unclosed_formatting_codes = unclosed_formatting


def close_formatting_codes(s):
    """Return the given string with all open formatting codes closed.

    .. deprecated:: 2.4
       This function simply appends ``^O`` to the end of *s*.  Older
       implementations were overly complex and bug-prone.
    """
    return s + '\x0F'
