Writing plugins
===============

Omnipresence supports two different types of plugins:

* **Handler plugins** listen for and respond to general events.

* **Command plugins** are more specialized variants of handler plugins that only respond when a specific *keyword* is sent to the bot in a message.
  In IRC channels, a *command prefix* is also expected.  Both of these are specified in the bot configuration.

Plugins are expected to be module-level variables in submodules of the package :py:mod:`omnipresence.plugins`.
`Twisted's plugin documentation <http://twistedmatrix.com/documents/current/core/howto/plugin.html#auto1>`_ has further details.
In practice, this means that you will write a plugin class that implements the provided interfaces, and assign an instance of that class to a variable in your plugin module::

    # omnipresence/plugins/example.py
    from twisted.plugin import IPlugin
    from omnipresence.iomnipresence import ICommand


    class ExampleCommand(object):
        implements(IPlugin, ICommand)
        name = 'example'

        def execute(self, bot, prefix, reply_target, channel, args):
            # ... command performs its work ...
            bot.reply(reply_target, channel, text)


    # Don't forget to do this at the end of your module file, or Omnipresence
    # will not load your command plugin!
    example = ExampleCommand()

Handler plugins
---------------

Handler plugins are expected to implement both :py:class:`twisted.plugin.IPlugin` and :py:class:`~omnipresence.iomnipresence.IHandler`.

.. autointerface:: omnipresence.iomnipresence.IHandler
   :members:

   .. py:method:: registered()

      An optional callback, fired when the plugin is initialized.
      At this point, a :py:class:`omnipresence.ConnectionFactory` object has been assigned to the ``self.factory`` object attribute, which can be used to read configuration data (through :py:data:`~omnipresence.ConnectionFactory.config`).

Command plugins
---------------

Handler plugins are expected to implement both :py:class:`twisted.plugin.IPlugin` and :py:class:`~omnipresence.iomnipresence.ICommand`.

.. autointerface:: omnipresence.iomnipresence.ICommand
   :members:

   .. py:method:: registered()

      See :py:meth:`IHandler.registered`.

Web-based commands
``````````````````

Omnipresence provides a convenience class for commands that rely on making an HTTP request and parsing the response, :py:class:`~omnipresence.web.WebCommand`.
See the class documentation for more details.

.. _using-deferreds:

Using Deferreds
---------------

Command and handler plugins that need to perform actions that would otherwise block the main thread should use `Twisted's deferred execution mechanism <http://twistedmatrix.com/documents/current/core/howto/defer.html>`_ to make the blocking call asynchronously.
Omnipresence automatically adds an errback to any :py:class:`~twisted.internet.defer.Deferred` objects returned by a command plugin's :py:meth:`~ICommand.execute` method, so that any unhandled errors encountered during the command's execution can be reported to the user.
