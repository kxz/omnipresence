Writing event plugins
=====================

.. module:: omnipresence.plugin

Event plugins are Omnipresence's primary extension mechanism.
This page details how to add new functionality by creating your own
plugins.
For information on the built-in plugins shipped with the Omnipresence
distribution, see :doc:`builtins`.

.. autoclass:: EventPlugin

   Omnipresence locates event plugins by their Python module and
   variable names, as detailed in :doc:`settings`.
   For example, the following code in the top-level module ``foo``
   creates two event plugins named ``foo/default`` and ``foo/other``::

       from omnipresence.plugin import EventPlugin

       default = EventPlugin()
       other   = EventPlugin()

   For convenience, a plugin key containing only a module name implies
   ``default``, so ``foo`` is a shorter name for ``foo/default``.

   Once instantiated, callbacks can be added to an event plugin using
   its :py:meth:`~.EventPlugin.on` decorator:

   .. decoratormethod:: on(action, ..., outgoing=False)

      Register a function as a callback to be fired when this plugin
      receives a message with one of the :ref:`message types
      <message-types>` matching any *action*, with this plugin and a
      :py:class:`~.Message` object as positional parameters.

      For example, the following callback sends a private message to
      greet incoming channel users::

          @default.on('join')
          def greet(self, message):
              greeting = 'Hello, {}!'.format(message.actor.nick)
              message.connection.msg(message.venue, greeting)

      Multiple callbacks can be added for the same event; they are
      executed in the order they are defined.
      Thus, the following callbacks yield two messages reading "first"
      and "second" whenever a channel message or notice is received::

          @default.on('privmsg', 'notice')
          def first(self, message):
              message.connection.msg(message.venue, 'first')

          @default.on('privmsg', 'notice')
          def second(self, message):
              message.connection.msg(message.venue, 'second')

      Callbacks that need to execute blocking code can return a Twisted
      :py:class:`~twisted.internet.defer.Deferred` object::

          @default.on('privmsg')
          def long_runner(self, message):
              d = some_deferred_task()
              d.addCallback(lambda s: message.connection.msg(message.venue, s))
              return d

      If a plugin needs to perform setup tasks, add a callback listening
      for the ``registration`` message type::

          @default.on('registration')
          def setup(self, message):
              self.log.msg('Ready and waiting')

      By default, callbacks are not fired for outgoing events generated
      by bot messages, in order to reduce the probability of accidental
      response loops.
      To change this behavior, pass the *outgoing* keyword argument.
      A message's :py:attr:`~.Message.outgoing` attribute can be used to
      determine its direction of transit::

          @default.on('privmsg', outgoing=True)
          def log(self, message):
              direction = 'Outgoing' if message.outgoing else 'Incoming'
              self.log.msg('{} message: {!r}'.format(direction, message))


Command plugins
---------------

...

Omnipresence provides the :py:class:`~omnipresence.web.WebCommand` class
for creating commands that rely on making an HTTP request and parsing
the response.
See the class documentation for more details.
