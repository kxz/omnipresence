# -*- test-case-name: omnipresence.test.test_message -*-
"""Operations on IRC messages."""


from collections import namedtuple

from ..hostmask import Hostmask
from .formatting import remove_formatting, unclosed_formatting
from .parser import parse as parse_raw


class Message(namedtuple('Message',
                         ('connection', 'actor', 'action',
                          'venue', 'target', 'subaction', 'content',
                          'raw'))):
    """Represents a message, loosely defined as an event to which
    plugins can respond.  Most message types correspond to those defined
    in :rfc:`1459#section-4`; Omnipresence also specifies some custom
    types for internal event handling.

    The following attributes are present on all :py:class:`~.Message`
    objects:

    .. py:attribute:: connection

       The :py:class:`~.IRCClient` instance on which the message was
       received.  It is equivalent to the *bot* argument in old-style
       :py:class:`~omnipresence.iomnipresence.IHandler` and
       :py:class:`~omnipresence.iomnipresence.ICommand` callbacks.

    .. py:attribute:: actor

       A :py:class:`~.Hostmask` corresponding to the message prefix,
       indicating the message's true origin.

    .. py:attribute:: action

       A string containing the message type, explained below.

    The remaining attributes are optional; their presence and meaning
    depend on the message type.  An attribute is ``None`` if and only if
    it is not used by the current message type, and a string value
    otherwise.

    :py:class:`~.Message` objects are instances of
    :py:class:`collections.namedtuple`, and thus immutable.  To create a
    new object based on the attributes of an existing one, use
    :py:meth:`~collections.namedtuple._replace`.

    Note that all string values are byte strings, not Unicode strings,
    and must be appropriately decoded when necessary.

    Omnipresence supports messages of the following types:

    .. describe:: privmsg

       Represents a typical message to a user or channel.  *venue* is
       the nick or channel name of the recipient; *content* is the text
       of the message.  *subaction* and *target* are not used.

       The :py:attr:`private` property can be used to determine whether
       a message was sent to a single user or a channel.

    .. describe:: notice

       Represents a notice.  All attributes are as for the ``privmsg``
       type.

    .. describe:: command

       Represents a command invocation.  *venue* is as for the
       ``privmsg`` type; *target* is a string containing the reply
       redirection target, or the actor's nick if none was specified;
       *subaction* is the command keyword; and *content* is a string
       containing any trailing arguments.

    .. describe:: unknown

       Represents an unrecognized message type.  *subaction* is the
       IRC command name; *content* is a string containing any trailing
       arguments.  *venue* and *target* are not used.
    """

    def __new__(cls,
                connection, actor, action,
                venue=None, target=None, subaction=None, content=None):
        if isinstance(actor, str):
            actor = Hostmask.from_string(actor)
        return super(Message, cls).__new__(
            cls, connection, actor,
            action, venue, target, subaction, content,
            raw=None)

    @classmethod
    def from_raw(cls, connection, raw):
        """Parse a raw IRC message string and return a corresponding
        :py:class:`~.Message` object."""
        return super(Message, cls).__new__(
            cls, connection, raw=raw, **parse_raw(raw))

    def to_raw(self):
        """Return this message as a raw IRC message string.  If this
        object was created using :py:meth:`.Message.from_raw`, the raw
        string that was originally provided is returned; otherwise, one
        is constructed from this object's fields.  This method is not
        supported for ``command`` messages, since they are artificially
        created.
        """
        if self.raw is not None:
            return self.raw
        if self.action == 'command':
            raise ValueError('command messages have no raw IRC representation')
        raise NotImplementedError

    @property
    def bot(self):
        """Return the bot instance associated with this message.  This
        is currently an alias for the *connection* attribute.  In the
        future, Omnipresence is planned to have support for multiple IRC
        connections in a single bot instance; *bot* will then become a
        pointer to that global instance."""
        return self.connection

    def extract_command(self, prefixes=None):
        """Attempt to extract a command invocation from this message.
        *prefixes* is an iterable of strings; if provided and non-empty,
        messages are only considered to have invocations if they begin
        with exactly one prefix.  Return any invocation found as a new
        :py:class:`~.Message`, or ``None`` otherwise."""
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
        return self._replace(action='command', target=target,
                             subaction=keyword, content=content)

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
