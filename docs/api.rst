API reference
=============

Core IRC client
---------------

.. automodule:: omnipresence.connection
   :members: Connection

Messages
--------

.. autoclass:: omnipresence.message.Message(connection, actor, action, venue=None, target=None, subaction=None, content=None)

   .. note:: All string values are byte strings, not Unicode strings,
      and therefore must be appropriately decoded when necessary.

   The following additional properties are derived from the values of
   one or more basic attributes, and are included for convenience:

   .. autoattribute:: omnipresence.message.Message.bot
   .. autoattribute:: omnipresence.message.Message.private

   New message objects can be created using either the standard
   constructor, or by parsing a raw IRC message string:

   .. automethod:: omnipresence.message.Message.from_raw

   Most message objects can also be converted back to raw strings:

   .. automethod:: omnipresence.message.Message.to_raw

   :py:class:`~.Message` is a :py:func:`collections.namedtuple` type,
   and thus its instances are immutable.
   To create a new object based on the attributes of an existing one,
   use an instance's :py:meth:`~collections.somenamedtuple._replace`
   method.


.. _message-types:

Message types
~~~~~~~~~~~~~

A message's type is stored in its :py:attr:`~.Message.action` attribute.
The following message types directly correspond to incoming or outgoing
IRC messages (also see :rfc:`1459#section-4`):

.. describe:: join

   Represents a channel join.
   :py:attr:`~.Message.venue` is the channel being joined.

.. describe:: kick

   Represents a kick.
   :py:attr:`~.Message.venue` is the channel the kick took place in.
   :py:attr:`~.Message.target` is the nick of the kicked user.
   :py:attr:`~.Message.content` is the kick message.

.. describe:: mode

   Represents a mode change.
   :py:attr:`~.Message.venue` is the affected channel or nick.
   :py:attr:`~.Message.content` is the mode change string.

.. describe:: nick

   Represents a nick change.
   :py:attr:`~.Message.content` is the new nick.

.. describe:: notice

   Represents a notice.
   All attributes are as for the ``privmsg`` type.

.. describe:: part

   Represents a channel part.
   :py:attr:`~.Message.venue` is the channel being departed from.
   :py:attr:`~.Message.content` is the part message.

.. describe:: privmsg

   Represents a typical message.
   :py:attr:`~.Message.venue` is the nick or channel name of the
   recipient; :py:attr:`~.Message.private` can also be used to determine
   whether a message was sent to a single user or a channel.
   :py:attr:`~.Message.content` is the text of the message.

.. describe:: quit

   Represents a client quit from the IRC network.
   :py:attr:`~.Message.content` is the quit message.

.. describe:: unknown

   Represents a message not of one of the above types.
   :py:attr:`~.Message.subaction` is the IRC command name or numeric.
   :py:attr:`~.Message.content` is a string containing any trailing
   arguments.

Omnipresence defines additional message types for synthetic events:

.. describe:: registration

   Passed to a plugin instance to indicate that it has been attached to
   a running bot.
   No optional attributes are given.

.. describe:: command

   Represents a command invocation.
   :py:attr:`~.Message.venue` is as for the ``privmsg`` type.
   :py:attr:`~.Message.target` is a string containing the reply
   redirection target, or the actor's nick if none was specified.
   :py:attr:`~.Message.subaction` is the command keyword.
   :py:attr:`~.Message.content` is a string containing any trailing
   arguments.

.. describe:: cmdhelp

   Represents a command help request.
   :py:attr:`~.Message.venue` and :py:attr:`~.Message.target` are as for
   the ``command`` type.
   :py:attr:`~.Message.subaction` is the command keyword for which help
   was requested.
   :py:attr:`~.Message.content` is a string containing any trailing
   arguments.


Message formatting
~~~~~~~~~~~~~~~~~~

.. automodule:: omnipresence.message.formatting
   :members: remove_formatting, unclosed_formatting

Hostmasks
---------

.. automodule:: omnipresence.hostmask
   :members: Hostmask

Case mappings
-------------

.. automodule:: omnipresence.mapping
   :members: CaseMapping, by_name

Web resource interactions
-------------------------

.. automodule:: omnipresence.web
   :members: WebCommand, request, textify_html

Human-readable output helpers
-----------------------------

.. automodule:: omnipresence.humanize
   :members:
