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
   For example, the following code in the top-level module ``foo``
   creates two event plugins named ``foo/Default`` and ``foo/Other``::

       from omnipresence.plugin import EventPlugin

       class Default(EventPlugin):
           pass

       class Other(EventPlugin):
           pass

   For convenience, a plugin key containing only a module name implies
   ``Default``, so ``foo`` is a shorter name for ``foo/Default``.

   On initialization, Omnipresence passes the current
   :py:class:`~.Connection` as a positional parameter, which can be used
   to read configuration settings::

       class Default(EventPlugin):
           def __init__(self, bot):
               self.bar = bot.factory.config.get('foo', 'bar')

   Callbacks can be added to an event plugin using
   :py:meth:`~.EventPlugin.register`:

   .. classmethod:: register(callback, action, ..., outgoing=False)

      Register *callback* to be fired when an instance of this plugin
      receives a message with a :ref:`type <message-types>` matching any
      *action*, with a :py:class:`~.Message` object as the sole
      parameter.

   For example, the following plugin sends a private message to
   greet incoming channel users::

       class Default(EventPlugin):
           def greet(self, message):
               greeting = 'Hello, {}!'.format(message.actor.nick)
               message.connection.msg(message.venue, greeting)

       Default.register(Default.greet, 'join')

   Callbacks that need to execute blocking code can return a Twisted
   :py:class:`~twisted.internet.defer.Deferred` object::

       class Default(EventPlugin):
           def long_runner(self, message):
               d = some_deferred_task()
               d.addCallback(lambda s: message.connection.msg(message.venue, s))
               return d

       Default.register(Default.long_runner, 'privmsg')

   By default, callbacks are not fired for outgoing events generated
   by bot messages, in order to reduce the probability of accidental
   response loops.
   To change this behavior, pass the *outgoing* keyword argument.
   A message's :py:attr:`~.Message.outgoing` attribute can be used to
   determine its direction of transit::

       class Default(EventPlugin):
           def log(self, message):
               direction = 'Outgoing' if message.outgoing else 'Incoming'
               self.log.msg('{} message: {!r}'.format(direction, message))

       Default.register(Default.log, 'privmsg', outgoing=True)


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
