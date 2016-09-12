# -*- test-case-name: omnipresence.test.test_message -*-
"""Operations on IRC messages."""


from collections import namedtuple
from functools import partial

from enum import Enum

from ..hostmask import Hostmask
from .formatting import remove_formatting


#: The default text encoding.
DEFAULT_ENCODING = 'utf-8'


class MessageType(Enum):
    """An enumeration of valid values of `.Message.action`.

    The following message types directly correspond to incoming or
    outgoing IRC messages (also see :rfc:`1459#section-4`):

    .. autoattribute:: action
    .. autoattribute:: ctcpquery
    .. autoattribute:: ctcpreply
    .. autoattribute:: join
    .. autoattribute:: kick
    .. autoattribute:: mode
    .. autoattribute:: nick
    .. autoattribute:: notice
    .. autoattribute:: part
    .. autoattribute:: privmsg
    .. autoattribute:: quit
    .. autoattribute:: topic
    .. autoattribute:: unknown

    Omnipresence defines additional message types for synthetic events:

    .. autoattribute:: connected
    .. autoattribute:: disconnected
    .. autoattribute:: command
    .. autoattribute:: cmdhelp
    """

    #: Represents a message that is not of any known type, or that could
    #: not be correctly parsed.
    #: `.subaction` is the IRC command name or numeric.
    #: `.content` is a string containing any trailing arguments.
    unknown = 0

    #: Represents a CTCP ACTION (``/me``).
    #: All attributes are as for the `.privmsg` type.
    action = 1

    #: Represents an otherwise unrecognized CTCP query wrapped in a
    #: ``PRIVMSG``.
    #: `.venue` is the nick or channel name of the recipient.
    #: `.subaction` is the CTCP message tag.
    #: `.content` is a string containing any trailing arguments.
    #:
    #: .. note:: Omnipresence does not support mixed messages containing
    #:    both normal and CTCP extended content.
    ctcpquery = 2

    #: Represents an unrecognized CTCP reply wrapped in a ``NOTICE``.
    #: All attributes are as for the `.ctcpquery` type.
    ctcpreply = 3

    #: Represents a channel join.
    #: `.venue` is the channel being joined.
    join = 4

    #: Represents a kick.
    #: `.venue` is the channel the kick took place in.
    #: `.target` is the nick of the kicked user.
    #: `.content` is the kick message.
    kick = 5

    #: Represents a mode change.
    #: `.venue` is the affected channel or nick.
    #: `.content` is the mode change string.
    mode = 6

    #: Represents a nick change.
    #: `.content` is the new nick.
    nick = 7

    #: Represents a notice.
    #: All attributes are as for the `privmsg` type.
    notice = 8

    #: Represents a channel part.
    #: `.venue` is the channel being departed from.
    #: `.content` is the part message.
    part = 9

    #: Represents a typical message.
    #: `.venue` is the nick or channel name of the recipient.
    #: (`.private` can also be used to determine whether a message was
    #: sent to a single user or a channel.)
    #: `.content` is the text of the message.
    privmsg = 10

    #: Represents a client quit from the IRC network.
    #: `.content` is the quit message.
    quit = 11

    #: Represents a topic change.
    #: `.venue` is the affected channel.
    #: `.content` is the new topic, or an empty string if the topic is
    #: being unset.
    topic = 12

    #: Created when the server has responded with ``RPL_WELCOME``.
    #: No optional arguments are specified.
    connected = 9001

    #: Created when the connection to the server has been closed or lost.
    #: No optional arguments are specified.
    disconnected = 9002

    #: Represents a :ref:`command invocation <command-replies>`.
    #: `.venue` is as for the `.privmsg` type.
    #: `.target` is a string containing the reply redirection target, or
    #: the actor's nick if none was specified.
    #: `.subaction` is the command keyword.
    #: `.content` is a string containing any trailing arguments.
    command = 9003

    #: Represents a command help request.
    #: `.venue` and `.target` are as for the `.command` type.
    #: `.subaction` is the command keyword for which help was requested.
    #: `.content` is a string containing any trailing arguments.
    cmdhelp = 9004


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

    .. attribute:: venue
                   target
                   subaction
                   content

       Optional attributes, whose presence and meaning depend on the
       message type.  An attribute is `None` if and only if it is not
       used by the current message type, and a string value otherwise.

    .. attribute:: raw

       If this message was created by parsing a raw message with
       `.RawMessageParser.parse`, the original raw IRC message string
       passed to that function.  Otherwise, `None`.

    .. note:: All string values are byte strings, not Unicode strings,
       and therefore must be appropriately decoded when necessary.

    The following additional properties are derived from the values of
    one or more basic attributes, and are included for convenience:

    .. autoattribute:: private
    .. autoattribute:: encoding

    New message objects can be created using either the standard
    constructor, or by parsing a raw IRC message string using
    `.RawMessageParser.parse`.

    `.Message` is a `~collections.namedtuple` type, and thus its
    instances are immutable.  To create a new object based on the
    attributes of an existing one, use an instance's
    `~collections.somenamedtuple._replace` method.
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
