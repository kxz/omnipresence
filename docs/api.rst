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

   .. attribute:: case_mapping

      The `.CaseMapping` currently in effect on this connection.
      Defaults to ``rfc1459`` if none is explicitly provided by the
      server.

   .. attribute:: venues

      A mapping of venue names to `VenueInfo` objects.

   .. attribute:: reactor

      The reactor in use on this client.
      This may be overridden when a deterministic clock is needed, such
      as in unit tests.

.. autoclass:: VenueInfo
   :members:

.. autoclass:: VenueUserInfo
   :members:

.. autodata:: MAX_REPLY_LENGTH


Messages
========

.. module:: omnipresence.message

.. autoclass:: Message(connection, outgoing, action, actor=None, venue=None, target=None, subaction=None, content=None)

   .. note:: All string values are byte strings, not Unicode strings,
      and therefore must be appropriately decoded when necessary.

   The following additional properties are derived from the values of
   one or more basic attributes, and are included for convenience:

   .. autoattribute:: private
   .. autoattribute:: encoding

   New message objects can be created using either the standard
   constructor, or by parsing a raw IRC message string:

   .. automethod:: from_raw

   `.Message` is a `~collections.namedtuple` type, and thus its
   instances are immutable.
   To create a new object based on the attributes of an existing one,
   use an instance's `~collections.somenamedtuple._replace` method.

.. class:: MessageType

   A message's type is stored in its `.action` attribute as a member of
   this enumeration.
   The following message types directly correspond to incoming or
   outgoing IRC messages (also see :rfc:`1459#section-4`):

   .. attribute:: action

      Represents a CTCP ACTION (``/me``).
      All attributes are as for the `.privmsg` type.

   .. attribute:: ctcpquery

      Represents an unrecognized CTCP query wrapped in a ``PRIVMSG``.
      `.venue` is the nick or channel name of the recipient.
      `.subaction` is the CTCP message tag.
      `.content` is a string containing any trailing arguments.

      .. note:: Omnipresence does not support mixed messages containing
         both normal and CTCP extended content.

   .. attribute:: ctcpreply

      Represents an unrecognized CTCP reply wrapped in a ``NOTICE``.
      All attributes are as for the `.ctcpquery` type.

   .. attribute:: join

      Represents a channel join.
      `.venue` is the channel being joined.

   .. attribute:: kick

      Represents a kick.
      `.venue` is the channel the kick took place in.
      `.target` is the nick of the kicked user.
      `.content` is the kick message.

   .. attribute:: mode

      Represents a mode change.
      `.venue` is the affected channel or nick.
      `.content` is the mode change string.

   .. attribute:: nick

      Represents a nick change.
      `.content` is the new nick.

   .. attribute:: notice

      Represents a notice.
      All attributes are as for the `privmsg` type.

   .. attribute:: part

      Represents a channel part.
      `.venue` is the channel being departed from.
      `.content` is the part message.

   .. attribute:: privmsg

      Represents a typical message.
      `.venue` is the nick or channel name of the recipient.
      (`.private` can also be used to determine whether a message was
      sent to a single user or a channel.)
      `.content` is the text of the message.

   .. attribute:: quit

      Represents a client quit from the IRC network.
      `.content` is the quit message.

   .. attribute:: topic

      Represents a topic change.
      `.venue` is the affected channel.
      `.content` is the new topic, or an empty string if the topic is
      being unset.

   .. attribute:: unknown

      Represents a message not of one of the above types, or that could
      not be correctly parsed.
      `.subaction` is the IRC command name or numeric.
      `.content` is a string containing any trailing arguments.

   Omnipresence defines additional message types for synthetic events:

   .. attribute:: connected

      Created when the server has responded with ``RPL_WELCOME``.
      No optional arguments are specified.

   .. attribute:: disconnected

      Created when the connection to the server has been closed or lost.
      No optional arguments are specified.

   .. attribute:: command

      Represents a :ref:`command invocation <command-replies>`.
      `.venue` is as for the `.privmsg` type.
      `.target` is a string containing the reply redirection target, or
      the actor's nick if none was specified.
      `.subaction` is the command keyword.
      `.content` is a string containing any trailing arguments.

   .. attribute:: cmdhelp

      Represents a command help request.
      `.venue` and `.target` are as for the `.command` type.
      `.subaction` is the command keyword for which help was requested.
      `.content` is a string containing any trailing arguments.


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

.. automodule:: omnipresence.case_mapping
   :members: CaseMapping, CaseMappedDict


Web resource interactions
=========================

.. module:: omnipresence.web

.. autofunction:: omnipresence.web.html.textify
.. autofunction:: omnipresence.web.http.read_json_body


Human-readable output helpers
=============================

.. automodule:: omnipresence.humanize
   :members:
