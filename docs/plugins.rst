Writing event plugins
*********************

.. module:: omnipresence.plugin

Event plugins are Omnipresence's primary extension mechanism.
This page details how to add new functionality by creating your own
plugins.
For information on the built-in plugins shipped with the Omnipresence
distribution, see :doc:`builtins`.

.. autoclass:: EventPlugin(bot)

   Omnipresence locates event plugin classes by their Python module and
   class names, as detailed in :doc:`settings`.
   For convenience, a plugin key containing only a module name implies
   the class name ``Default``.
   The following code in the top-level module ``foo`` therefore creates
   event plugins named ``foo`` (or ``foo/Default``) and ``foo/Other``::

       from omnipresence.plugin import EventPlugin

       class Default(EventPlugin):
           pass

       class Other(EventPlugin):
           pass

   On plugin initialization, Omnipresence passes the current
   :py:class:`~.Connection` as a positional parameter, which can be used
   to read configuration settings needed during setup::

       class Default(EventPlugin):
           def __init__(self, bot):
               self.load_data(bot.factory.config.get('foo', 'bar'))

   When a message is received, Omnipresence looks for a plugin method
   named ``on_`` followed by the :ref:`message type <message-types>`,
   such as ``on_privmsg``.
   If one exists, it is called with a :py:class:`~.Message` object as
   the sole parameter.
   For example, the following plugin sends a private message to
   greet incoming channel users::

       class Default(EventPlugin):
           def on_join(self, message):
               greeting = 'Hello, {}!'.format(message.actor.nick)
               message.connection.msg(message.venue, greeting)

   Callbacks that need to execute blocking code can return a Twisted
   :py:class:`~twisted.internet.defer.Deferred` object::

       class Default(EventPlugin):
           def on_privmsg(self, message):
               d = some_deferred_task()
               d.addCallback(lambda s: message.connection.msg(message.venue, s))
               return d

   By default, callbacks are not fired for outgoing events generated
   by bot messages, in order to reduce the probability of accidental
   response loops.
   To change this behavior, set the ``outgoing`` attribute of a callback
   method to :py:data:`True`.
   Inside the callback, each message's :py:attr:`~.Message.outgoing`
   attribute can be used to determine its direction of transit::

       from twisted.python import log

       class Default(EventPlugin):
           def on_privmsg(self, message):
               direction = 'Outgoing' if message.outgoing else 'Incoming'
               log.msg('%s message: %r' % (direction, message))
           on_privmsg.outgoing = True


Command plugins
===============

...

Omnipresence provides the :py:class:`~omnipresence.web.WebCommand` class
for creating commands that rely on making an HTTP request and parsing
the response.
See the class documentation for more details.


Writing tests
=============

...
