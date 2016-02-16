# -*- test-case-name: omnipresence.test.test_message -*-
"""Operations on IRC messages."""


from collections import namedtuple, Iterable, Iterator, Sequence
from functools import partial
import itertools

from enum import Enum

from ..compat import length_hint
from ..hostmask import Hostmask
from .formatting import remove_formatting, unclosed_formatting
from .parser import parse as parse_raw


#: The default text encoding.
DEFAULT_ENCODING = 'utf-8'

#: The length to chunk string command replies to, in bytes.
CHUNK_LENGTH = 256


#
# Core message class
#

#: An enumeration of recognized Omnipresence message types.
MessageType = Enum('MessageType', [
    'action', 'ctcpquery', 'ctcpreply', 'join', 'kick', 'mode', 'nick',
    'notice', 'part', 'privmsg', 'quit', 'topic',
    'connected', 'disconnected', 'command', 'cmdhelp', 'unknown'])


class MessageSettings(object):
    """A proxy for `ConnectionSettings` that automatically adds the
    given *message* as a scope to method calls."""

    def __init__(self, settings, message):
        self.settings = settings
        self.message = message

    def __getattr__(self, name):
        return partial(getattr(self.settings, name), message=self.message)


class Message(namedtuple('Message',
                         ('connection', 'outgoing', 'action', 'actor',
                          'venue', 'target', 'subaction', 'content',
                          'raw'))):
    """Represents a message, loosely defined as an event to which
    plugins can respond.  Messages have the following basic attributes:

    .. attribute:: connection

       The `.Connection` on which the message was received.

    .. attribute:: outgoing

       A boolean indicating whether this message resulted from a bot
       action.

    .. attribute:: action

       This message's `.MessageType`.  A string containing a message
       type name may be passed to the constructor, but the property
       always contains an enumeration member.

    .. attribute:: actor

       A `.Hostmask` corresponding to the message prefix, indicating the
       message's true origin.  In some cases, ``unknown`` messages will
       set this attribute to `None` if a prefix could not be parsed.

    .. py:attribute:: venue
                      target
                      subaction
                      content

       Optional attributes, whose presence and meaning depend on the
       message type.  An attribute is `None` if and only if it is not
       used by the current message type, and a string value otherwise.

    .. py:attribute:: raw

       If this message was created using `.Message.from_raw`, the
       original raw IRC message string passed to that function.
       Otherwise, `None`.
    """

    def __new__(cls,
                connection, outgoing, action, actor=None,
                venue=None, target=None, subaction=None, content=None,
                raw=None):
        if not isinstance(action, MessageType):
            try:
                action = MessageType[action]
            except KeyError:
                raise ValueError('unrecognized message type "{}"'
                                 .format(action))
        if isinstance(actor, str):
            actor = Hostmask.from_string(actor)
        return super(Message, cls).__new__(
            cls, connection, outgoing, action, actor,
            venue, target, subaction, content, raw)

    @classmethod
    def from_raw(cls, connection, outgoing, raw, **kwargs):
        """Parse a raw IRC message string and return a corresponding
        `.Message` object.  Any keyword arguments override field values
        returned by the parser."""
        parser_kwargs = parse_raw(raw)
        parser_kwargs.update(kwargs)
        return cls.__new__(cls, connection, outgoing, raw=raw, **parser_kwargs)

    @property
    def encoding(self):
        """The character encoding in effect for this message's venue."""
        return self.settings.get('encoding', default=DEFAULT_ENCODING)

    def extract_command(self, prefixes=None):
        """Attempt to extract a command invocation from this message.
        *prefixes* is an iterable of strings; if provided and non-empty,
        messages are only considered to have invocations if they begin
        with exactly one prefix.  Return any invocation found as a new
        `.Message`, or `None` otherwise."""
        if self.action is not MessageType.privmsg:
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
                if not self.private:
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
        return self._replace(action=MessageType.command, target=target,
                             subaction=keyword, content=content)

    @property
    def private(self):
        """`True` if this message has a venue and that venue is not a
        public channel.  Otherwise, `False`."""
        return not (self.venue is None or
                    self.connection.is_channel(self.venue))

    @property
    def settings(self):
        """The settings in place for this message.  Methods are like
        those for `ConnectionSettings`, with the *scope* argument set to
        this message."""
        return MessageSettings(self.connection.settings, self)


#
# Reply buffering
#

def truncate_unicode(string, byte_limit, encoding=DEFAULT_ENCODING):
    """Truncate a Unicode *string* so that it fits within *byte_limit*
    when encoded using *encoding*.  Return the truncated string as a
    byte string."""
    # Per Denis Otkidach on SO <http://stackoverflow.com/a/1820949>.
    encoded = string.encode(encoding)[:byte_limit]
    return encoded.decode(encoding, 'ignore').encode(encoding)


def chunk(string, encoding=DEFAULT_ENCODING, max_length=CHUNK_LENGTH):
    """Return a list containing chunks of at most *max_length* bytes
    from *string*.  Breaks are made at whitespace instead of in the
    middle of words when possible.  If *string* is a Unicode string,
    it is converted to a byte string using *encoding* before calculating
    the byte length.

    Any mIRC-style formatting codes present in *string* are repeated at
    the beginning of each subsequent chunk until they are overridden or
    a newline is encountered.

    Omnipresence uses this function internally to perform command reply
    buffering, as the name implies.  Plugin authors should not need to
    call it themselves.
    """
    if not isinstance(string, basestring):
        raise TypeError('expected basestring, not ' + type(string).__name__)
    chunks = []
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
        chunks.append(truncated)
    return chunks


class ReplyBuffer(Iterator):
    """An iterator wrapping the :ref:`command reply <command-replies>`
    *response* for the invocation `.Message` *request*."""

    def __init__(self, response, request=None):
        if isinstance(response, ReplyBuffer):
            self.response = response.response
        elif isinstance(response, basestring):
            if request is None:
                encoding = DEFAULT_ENCODING
            else:
                encoding = request.encoding
            self.response = chunk(response, encoding)
        elif isinstance(response, (Iterable, Sequence)):
            self.response = response
        else:
            raise TypeError('invalid command reply type ' +
                            type(response).__name__)

    def next(self):
        if isinstance(self.response, Sequence):
            if not self.response:
                raise StopIteration
            reply_string = self.response[0]
            self.response = self.response[1:]
            return reply_string
        return next(self.response)

    def tee(self, num=2):
        """Return *num* independent reply buffers from this one, like
        `itertools.tee`, but without making unnecessary copies of the
        underlying response."""
        if isinstance(self.response, Sequence):
            return (ReplyBuffer(self.response),) * num
        return tuple(ReplyBuffer(t) for t in itertools.tee(self.response, num))

    def __length_hint__(self):
        return length_hint(self.response)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, repr(self.response))


#
# Miscellaneous methods
#

def collapse(string):
    """Return *string* with any runs of whitespace collapsed to single
    spaces, and any leading or trailing whitespace removed."""
    # Don't need to call strip() because parameterless split() already
    # removes any leading and trailing whitespace.
    return ' '.join(string.split())
