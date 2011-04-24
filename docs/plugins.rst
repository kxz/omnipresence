Writing plugins
===============

Omnipresence supports two different types of plugins:

* **Handler plugins** listen for and respond to general events.

* **Command plugins** are more specialized variants of handler plugins that
  only respond when a specific *keyword* is sent to the bot in a message.  In
  IRC channels, a *command prefix* is also expected.  Both of these are
  specified in the bot configuration.

Plugins are expected to be module-level variables in submodules of the package
:py:mod:`omnipresence.plugins`.  `Twisted's plugin documentation
<http://twistedmatrix.com/documents/current/core/howto/plugin.html#auto1>`_ has
further details.  In practice, this means that you will write a plugin class
that implements the provided interfaces, and assign an instance of that class
to a variable in your plugin module::

    # omnipresence/plugins/example.py
    
    from twisted.plugin import IPlugin
    from omnipresence.iomnipresence import ICommand

    class ExampleCommand(object):
        implements(IPlugin, ICommand)
        name = 'example'

        def execute(self, bot, prefix, reply_target, channel, args):
            # ...

    # Don't forget to do this at the end of your module file, or Omnipresence
    # will not load your command plugin!
    example = ExampleCommand()

Handler plugins
---------------

Handler plugins are expected to implement both
:py:class:`twisted.plugin.IPlugin` and
:py:class:`~omnipresence.iomnipresence.IHandler`:

.. autointerface:: omnipresence.iomnipresence.IHandler
   :members:

   .. py:method:: registered()

      An optional callback, fired when the plugin is initialized.  At this
      point, an :py:class:`omnipresence.IRCClientFactory` object has been
      assigned to the ``self.factory`` object attribute, which can be used to
      read configuration data (through
      :py:data:`~omnipresence.IRCClientFactory.config`) and make HTTP requests
      (through :py:meth:`~omnipresence.IRCClientFactory.get_http`).

Command plugins
---------------

Handler plugins are expected to implement both
:py:class:`twisted.plugin.IPlugin` and
:py:class:`~omnipresence.iomnipresence.ICommand`:

.. autointerface:: omnipresence.iomnipresence.ICommand
   :members:

   .. py:method:: registered()

      See :py:meth:`IHandler.registered`.

.. _web-commands:

Web-based command example
`````````````````````````

Command plugins that must make requests that would otherwise block the main
thread should use `Twisted's deferred execution mechanism
<http://twistedmatrix.com/documents/current/core/howto/defer.html>`_ to make
the blocking call in a separate thread.  Omnipresence provides a convenience
method to simplify the creation of commands that need to make HTTP requests,
:py:meth:`omnipresence.IRCClientFactory.get_http`, which returns a
:py:class:`~twisted.internet.defer.Deferred` object.  Callbacks can be added to
this object; the first parameter provided will be a ``(headers, content)``
tuple.  :py:meth:`~ICommand.execute` should then return the
:py:class:`~twisted.internet.defer.Deferred` for further processing by the
Omnipresence core.

The following command plugin performs an HTTP request and replies with the
content type of the specified document::

    from twisted.plugin import IPlugin
    from omnipresence.iomnipresence import ICommand

    class ContentTypeCommand(object):
        """\x02%s\x02 \x1Fhttp_url\x1F - Get the MIME content type of the
        document at the given URL."""
        implements(IPlugin, ICommand)
        name = 'ctype'

        def execute(self, bot, prefix, reply_target, channel, args):
            args = args.split(None, 1)

            if len(args) < 2:
                bot.reply(prefix, channel, 'Please specify a URL.')
                return

            # Be careful when making HTTP requests to arbitrary URLs.  In
            # practice, you should check the address to make sure it doesn't
            # point to an internal network server or other sensitive locations.
            # The "url" plugin provided with Omnipresence, for example, looks
            # up the IP address corresponding to the given URL, and ensures
            # that it does not fall within private IP address blocks.
            d = self.factory.get_http(args[1])
            d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
            return d

        def reply(self, response, bot, prefix, reply_target, channel, args):
            bot.reply(reply_target, channel,
                      response[0].get('content-type', 'unknown content type'))

    ctype = ContentTypeCommand()
