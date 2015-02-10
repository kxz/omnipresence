API reference
*************

Connections
===========

.. module:: omnipresence.connection

.. autoclass:: Connection

   See `Twisted's IRCClient documentation`__ for details on methods used
   to perform basic actions.

   __ http://twistedmatrix.com/documents/current/api/twisted.words.protocols.irc.IRCClient.html

   .. automethod:: reply
   .. automethod:: is_channel
   .. automethod:: suspend_joins
   .. automethod:: resume_joins

   .. autoinstanceattribute:: case_mapping
      :annotation:
   .. autoinstanceattribute:: channel_names
      :annotation:
   .. autoinstanceattribute:: message_buffers
      :annotation:
   .. autoinstanceattribute:: suspended_joins
      :annotation:
   .. autoinstanceattribute:: reactor
      :annotation:

.. autoclass:: UserInfo
   :members:

.. autoclass:: ChannelInfo
   :members:

.. autoclass:: ChannelUserInfo
   :members:

.. autodata:: CHUNK_LENGTH
.. autodata:: MAX_REPLY_LENGTH


Messages
========

.. module:: omnipresence.message

.. autoclass:: Message(connection, outgoing, action, actor=None, venue=None, target=None, subaction=None, content=None)

   .. note:: All string values are byte strings, not Unicode strings,
      and therefore must be appropriately decoded when necessary.

   The following additional properties are derived from the values of
   one or more basic attributes, and are included for convenience:

   .. autoattribute:: bot
   .. autoattribute:: private

   New message objects can be created using either the standard
   constructor, or by parsing a raw IRC message string:

   .. automethod:: from_raw

   `~.Message` is a `~collections.namedtuple` type, and thus its
   instances are immutable.
   To create a new object based on the attributes of an existing one,
   use an instance's `~collections.somenamedtuple._replace` method.


.. _message-types:

Message types
-------------

A message's type is stored in its `~.Message.action` attribute.
The following message types directly correspond to incoming or outgoing
IRC messages (also see :rfc:`1459#section-4`):

.. describe:: action

   Represents a CTCP ACTION (``/me``).
   All attributes are as for the ``privmsg`` type.

.. describe:: ctcpquery

   Represents an unrecognized CTCP query wrapped in a PRIVMSG.
   `~.Message.venue` is the nick or channel name of the recipient.
   `~.Message.subaction` is the CTCP message tag.
   `~.Message.content` is a string containing any trailing arguments.

   .. note:: Omnipresence does not support mixed messages containing
      both normal and CTCP extended content.

.. describe:: ctcpreply

   Represents an unrecognized CTCP reply wrapped in a NOTICE.
   All attributes are as for the ``ctcpquery`` type.

.. describe:: join

   Represents a channel join.
   `~.Message.venue` is the channel being joined.

.. describe:: kick

   Represents a kick.
   `~.Message.venue` is the channel the kick took place in.
   `~.Message.target` is the nick of the kicked user.
   `~.Message.content` is the kick message.

.. describe:: mode

   Represents a mode change.
   `~.Message.venue` is the affected channel or nick.
   `~.Message.content` is the mode change string.

.. describe:: nick

   Represents a nick change.
   `~.Message.content` is the new nick.

.. describe:: notice

   Represents a notice.
   All attributes are as for the ``privmsg`` type.

.. describe:: part

   Represents a channel part.
   `~.Message.venue` is the channel being departed from.
   `~.Message.content` is the part message.

.. describe:: privmsg

   Represents a typical message.
   `~.Message.venue` is the nick or channel name of the recipient.
   (`~.Message.private` can also be used to determine
   whether a message was sent to a single user or a channel.)
   `~.Message.content` is the text of the message.

.. describe:: quit

   Represents a client quit from the IRC network.
   `~.Message.content` is the quit message.

.. describe:: topic

   Represents a topic change.
   `~.Message.venue` is the affected channel.
   `~.Message.content` is the new topic, or an empty string if the topic
   is being unset.

.. describe:: unknown

   Represents a message not of one of the above types, or that could not
   be correctly parsed.
   `~.Message.subaction` is the IRC command name or numeric.
   `~.Message.content` is a string containing any trailing arguments.

.. _synthetic-message-types:

Omnipresence defines additional message types for synthetic events:

.. describe:: connected

   Created when the server has responded with ``RPL_WELCOME``.
   No optional arguments are specified.

.. describe:: disconnected

   Created when the connection to the server has been closed or lost.
   No optional arguments are specified.

.. describe:: command

   Represents a command invocation.
   `~.Message.venue` is as for the ``privmsg`` type.
   `~.Message.target` is a string containing the reply redirection
   target, or the actor's nick if none was specified.
   `~.Message.subaction` is the command keyword.
   `~.Message.content` is a string containing any trailing arguments.

.. describe:: cmdhelp

   Represents a command help request.
   `~.Message.venue` and `~.Message.target` are as for the ``command``
   type.
   `~.Message.subaction` is the command keyword for which help was
   requested.
   `~.Message.content` is a string containing any trailing arguments.


Message formatting
------------------

.. automodule:: omnipresence.message.formatting
   :members: remove_formatting, unclosed_formatting

Hostmasks
=========

.. automodule:: omnipresence.hostmask
   :members: Hostmask

Case mappings
=============

.. automodule:: omnipresence.mapping
   :members: CaseMapping, by_name

Web resource interactions
=========================

.. automodule:: omnipresence.web
   :members: request, textify_html

Human-readable output helpers
=============================

.. automodule:: omnipresence.humanize
   :members:
