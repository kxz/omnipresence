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

   .. attribute:: parser

      The `.RawMessageParser` being used on this connection.

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
.. autoclass:: MessageType

.. module:: omnipresence.message.parser

.. autoclass:: RawMessageParser
   :members: parse


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
