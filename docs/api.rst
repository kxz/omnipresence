API reference
=============

Core IRC client
---------------

.. automodule:: omnipresence
   :members: IRCClient

Messages
--------

.. autoclass:: omnipresence.message.Message(connection, actor, action, venue=None, target=None, subaction=None, content=None)
   :no-members:

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

Omnipresence generates messages of the following types.
Most correspond to those defined in :rfc:`1459#section-4`, with the
addition of some custom types for internal event handling.
A message's type is stored in its :py:attr:`~.Message.action` attribute.

.. describe:: privmsg

   Represents a typical message.
   :py:attr:`~.Message.venue` is the nick or channel name of the
   recipient; :py:attr:`~.Message.private` can also be used to determine
   whether a message was sent to a single user or a channel.
   :py:attr:`~.Message.content` is the text of the message.
   :py:attr:`~.Message.subaction` and :py:attr:`~.Message.target` are
   not used.

.. describe:: notice

   Represents a notice.
   All attributes are as for the ``privmsg`` type.

.. describe:: command

   Represents a command invocation.
   :py:attr:`~.Message.venue` is as for the ``privmsg`` type.
   :py:attr:`~.Message.target` is a string containing the reply
   redirection target, or the actor's nick if none was specified.
   :py:attr:`~.Message.subaction` is the command keyword.
   :py:attr:`~.Message.content` is a string containing any trailing
   arguments.

.. describe:: unknown

   Represents a message not of one of the above types.
   :py:attr:`~.Message.subaction` is the IRC command name.
   :py:attr:`~.Message.content` is a string containing any trailing
   arguments.
   :py:attr:`~.Message.venue` and :py:attr:`~.Message.target` are not
   used.

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
