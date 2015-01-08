# -*- test-case-name: omnipresence.test.test_message -*-
"""Operations on IRC messages."""


from collections import namedtuple
import re

from .hostmask import Hostmask


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


def remove_formatting(s):
    """Remove mIRC-style formatting control codes from a string."""
    return CONTROL_CODES.sub('', s)


def unclosed_formatting(s):
    """Return a frozenset containing any unclosed mIRC-style formatting
    codes in a string."""
    fg = bg = ''
    bold = reverse = underline = False
    # ^O resets everything, so we split on it and only operate on the
    # portion of the string that is beyond the rightmost occurrence.
    for match in CONTROL_CODES.finditer(s.rsplit('\x0F')[-1]):
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


class Message(namedtuple('Message',
                         ('connection', 'actor', 'action',
                          'venue', 'target', 'content'))):
    """Represents a message, loosely defined as an event to which
    plugins can respond.  Most message types correspond to those defined
    in :rfc:`1459#section-4`; Omnipresence also specifies some custom
    types for internal event handling.

    The following attributes are present on all :py:class:`~.Message`
    objects:

    * *connection* is the :py:class:`~.IRCClient` instance on which the
      message was received.  It is equivalent to the *bot* argument in
      old-style :py:class:`~omnipresence.iomnipresence.IHandler` and
      :py:class:`~omnipresence.iomnipresence.ICommand` callbacks.
    * *actor* is a :py:class:`~.Hostmask` corresponding to the message
      prefix, indicating the message's true origin.
    * *action* is a string containing the message type, explained below.

    The remaining three attributes are optional; their presence and
    meaning depend on the message type.  An attribute is set to ``None``
    if and only if it is not used by the current message type.

    Note that all string values are byte strings, not Unicode strings,
    and must be appropriately decoded when necessary.

    Omnipresence supports messages of the following types:

    ``privmsg``
        Represents a typical message, or PRIVMSG according to the IRC
        protocol.  *venue* is the nick or channel name of the recipient;
        *content* is the text of the message as a string.  *target* is
        not used.

    ``notice``
        Represents a notice.  All attributes are as for the ``privmsg``
        type.

    ``command``
        Represents a command invocation.  *venue* is as for the
        ``privmsg`` type; *target* is the reply redirection target, or
        the actor's nick if none was specified; and *content* is a
        2-tuple containing the command keyword followed by a string
        containing any trailing arguments.
    """

    def __new__(cls,
                connection, actor, action,
                venue=None, target=None, content=None):
        if isinstance(actor, str):
            actor = Hostmask.from_string(actor)
        return super(Message, cls).__new__(
            cls, connection, actor, action, venue, target, content)

    @classmethod
    def from_raw(cls, raw):
        """Parse a raw IRC message string and return a corresponding
        :py:class:`~.Message` object."""
        raise NotImplementedError

    def to_raw(self):
        """Return this message as a raw IRC message string."""
        # TODO:  What should be done about command messages?
        raise NotImplementedError
    __str__ = to_raw

    @property
    def bot(self):
        """Return the bot instance associated with this message.  This
        is currently an alias for the *connection* attribute.  In the
        future, Omnipresence is planned to have support for multiple IRC
        connections in a single bot instance; *bot* will then become a
        pointer to that global instance."""
        return self.connection

    def extract_command(self, prefixes=None):
        """Attempt to extract a command invocation, preceded by at most
        one of the given prefixes in the iterable *prefixes* if it is
        provided, from this message.  If an invocation is found, return
        it; otherwise, return ``None``."""
        if self.action != 'privmsg':
            return
        # We don't care about formatting in looking for commands.
        content = remove_formatting(self.content)
        # See if any of the specified command prefixes match.
        if prefixes:
            for prefix in prefixes:
                if content.lower().startswith(prefix.lower()):
                    content = content[len(prefix):]
                    break
            else:
                # The message doesn't start with any of the given
                # prefixes.  We're done here.
                return
        # Extract the keyword for looking up the corresponding plugin.
        #
        # TODO:  Should this check against the list of plugins enabled
        # on the current connection?  In that case, couldn't we pull the
        # command prefixes from the venue configuration as well?  Might
        # violate separation of concerns...
        args = content.strip().split(None, 1)
        if not args:
            return
        keyword = args.pop(0).lower()
        # Pull the remainder of *args* for the new command message's
        # *content*.  *args* is guaranteed to have at most one element,
        # but might be empty, so we just use a string join to handle
        # both cases.
        content = ''.join(args)
        # Handle command redirection in the form of "args > nickname".
        target = None
        if '>' in content:
            content, target = (x.strip() for x in content.rsplit('>', 1))
        if not target:
            target = self.actor.nick
        return self._replace(
            action='command', target=target, content=(keyword, content))

    @property
    def private(self):
        """Return ``True`` if this message has a venue, and that venue
        is not a public channel; otherwise, return ``False``."""
        return not (self.venue is None or
                    self.connection.is_channel(self.venue))


def truncate_unicode(string, byte_limit, encoding='utf-8'):
    """Truncate a Unicode *string* so that it fits within *byte_limit*
    when encoded using *encoding*.  Return the truncated string as a
    byte string."""
    # Per Denis Otkidach on SO <http://stackoverflow.com/a/1820949>.
    encoded = string.encode(encoding)[:byte_limit]
    return encoded.decode(encoding, 'ignore').encode(encoding)


def chunk(string, encoding='utf-8', max_length=256):
    """Return an iterator that progressively yields chunks of at most
    *max_length* bytes from *string*.  When possible, breaks are made at
    whitespace, instead of in the middle of words.  If *string* is a
    Unicode string, the given *encoding* is used to convert it to a byte
    string and calculate the chunk length.  Any mIRC-style formatting
    codes present are repeated at the beginning of each subsequent chunk
    until they are overridden.

    Omnipresence uses this function internally to perform message
    buffering, as its name implies.  Plugin authors should not need to
    call this function themselves."""
    remaining = string
    while remaining:
        if isinstance(remaining, unicode):
            # See if the encoded string is longer than the maximum
            # reply length by truncating it and then comparing it to
            # the original.  If so, place the rest in the buffer.
            truncated = truncate_unicode(remaining, max_length, encoding)
            if truncated.decode(encoding) == remaining:
                remaining = ''
            else:
                # Try and find whitespace to split the string on.
                truncated = truncated.rsplit(None, 1)[0]
                remaining = remaining[len(truncated.decode(encoding)):]
        else:
            # We don't have to be so careful about length comparisons
            # with byte strings; just use slice notation.
            if len(remaining) <= max_length:
                truncated = remaining
                remaining = ''
            else:
                truncated = remaining[:max_length].rsplit(None, 1)[0]
                remaining = remaining[len(truncated):]
        truncated = truncated.strip()
        remaining = ''.join(unclosed_formatting(truncated)) + remaining.strip()
        # If all that's left are formatting codes, there's basically no
        # real content remaining in the string.
        if not remove_formatting(remaining):
            remaining = ''
        yield truncated
