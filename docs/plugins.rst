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

   When a message is received, Omnipresence looks for a plugin method
   named ``on_`` followed by the :ref:`message type <message-types>`,
   such as ``on_privmsg``.
   If one exists, it is called with a `~.Message` object as the sole
   parameter.
   For example, the following plugin sends a private message to
   greet incoming channel users::

       class Default(EventPlugin):
           def on_join(self, message):
               greeting = 'Hello, {}!'.format(message.actor.nick)
               message.connection.msg(message.venue, greeting)

   Callbacks that need to execute blocking code can return a Twisted
   `~twisted.internet.defer.Deferred` object::

       class Default(EventPlugin):
           def on_privmsg(self, message):
               d = some_deferred_task()
               d.addCallback(lambda s: message.connection.msg(message.venue, s))
               return d

   By default, callbacks are not fired for outgoing events generated
   by bot messages, in order to reduce the probability of accidental
   response loops.
   To change this behavior, set the ``outgoing`` attribute of a callback
   method to `True`.
   Inside the callback, each message's `~.Message.outgoing` attribute
   can be used to determine its direction of transit::

       from twisted.python import log

       class Default(EventPlugin):
           def on_privmsg(self, message):
               direction = 'Outgoing' if message.outgoing else 'Incoming'
               log.msg('%s message: %r' % (direction, message))
           on_privmsg.outgoing = True

   .. note:: Since most servers echo joins, parts, and quits back to
      clients, callbacks registered for these actions will always fire
      once on bot actions, twice if enabled for outgoing messages.
      You may wish to compare the message's `~.Message.actor` and the
      connection's `~.Connection.nickname` attributes to distinguish bot
      actions in these cases::

          class Default(EventPlugin):
              def on_join(self, message):
                  if message.actor.matches(message.connection.nickname):
                      the_bot_joined()
                  else:
                      someone_else_joined()


.. _command-replies:

Command replies
===============

Any plugin with an ``on_command`` callback can be assigned one or more
keywords in :doc:`its configuration <settings-plugin>`.
Unlike most other callbacks, whose return values are ignored, any value
returned from ``on_command`` becomes the command reply, and is sent as
either a channel message addressed to the command target or a private
notice depending on how the command was invoked.
A command reply may take one of the following forms:

* A byte or Unicode string.
  Long strings are broken into chunks of up to `.CHUNK_LENGTH` bytes and
  treated as a sequence.

* A sequence of strings.
  Any reply strings containing more than `.MAX_REPLY_LENGTH` bytes are
  truncated on display.

* An iterator yielding either strings or
  `~twisted.internet.defer.Deferred` objects that yield strings.
  Long reply strings are truncated as with sequence replies.

* A `~twisted.internet.defer.Deferred` object yielding any of the above.

In all cases, the first reply is immediately shown to the target user,
and any remaining replies are placed in a buffer for later retrieval
using the `.more <.plugins.more>` command.
Newlines inside replies are displayed as a slash surrounded by spaces.

The following example plugin implements an infinite counter::

    from itertools import count
    from omnipresence.plugin import EventPlugin

    class Default(EventPlugin):
        def on_command(self, msg):
            return count()

Error reporting
---------------

By default, if an error occurs inside an ``on_command`` callback,
Omnipresence replies with a generic error message and logs the full
traceback to the twistd log file.
This behavior can be changed with the ``show_errors`` configuration
option.
If you wish to always show detailed information for an error, raise a
`.UserVisibleError`:

.. autoexception:: UserVisibleError(*args)

Help strings
------------

To provide a help string for the `.help <.plugins.help>` command, return
it from the ``on_cmdhelp`` callback.
The incoming `.Message`'s `~.Message.content` attribute contains any
additional arguments to `.help <.plugins.help>`, allowing help
subtopics::

        def on_cmdhelp(self, msg):
            if msg.content == 'detailed':
                return '\x02detailed\x02 - Show more information.'
            if msg.content == 'terse':
                return '\x02terse\x02 - Show less information.'
            return ('[\x02detailed\x02|\x02terse\x02] - Do some stuff. '
                    'For more details, see help for \x02{}\x02 \x1Faction\x1F.'
                    .format(msg.subaction))

Note that the command keyword is automatically prepended to the help
string on display.

Omnipresence's :doc:`built-in plugins <builtins>` provide help strings
of the form ``usage - Help text.``, where the usage string is formatted
as follows:

* Strings to be typed literally by the user are bolded using ``\x02``.

* Strings representing command arguments are underlined using ``\x1F``.

* Optional components are surrounded by brackets (``[optional]``).

* Alternatives are separated by vertical bars (``this|that|other``).


Configuration options
=====================

Use the `.Message.settings` wrapper to look up the value of a
configuration variable::

    def on_command(self, msg):
        return msg.settings.get('foo.bar', 'default value')

The value of a configuration variable may change while the bot is
running (see :ref:`settings-reload`).
If a plugin needs to update its internal state on these changes, it can
do so by defining a ``configure`` callback, which is passed the current
bot settings::

    def configure(self, settings):
        self.process(settings.get('foo.bar'))

By convention, plugin configuration variable names should share a common
prefix ending with a period (``.``).
Undotted names are reserved for Omnipresence core variables.


Writing tests
=============

...
