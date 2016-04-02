# -*- test-case-name: omnipresence.test.test_message -*-
"""Operations on IRC messages."""


from collections import namedtuple
from functools import partial

from enum import Enum

from ..hostmask import Hostmask
from .formatting import remove_formatting
from .parser import parse as parse_raw


#: The default text encoding.
DEFAULT_ENCODING = 'utf-8'

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


def collapse(string):
    """Return *string* with any runs of whitespace collapsed to single
    spaces, and any leading or trailing whitespace removed."""
    # Don't need to call strip() because parameterless split() already
    # removes any leading and trailing whitespace.
    return ' '.join(string.split())
