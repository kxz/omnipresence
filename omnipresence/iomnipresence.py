from zope.interface import Interface, Attribute

class IHandler(Interface):
    """A handler that responds to IRC events passed to it by the bot.
    There are no required methods for this interface, since handlers may
    implement only a subset of available events.  Callbacks are
    generally the same as those defined in
    :py:class:`omnipresence.IRCClient`, except that an instance of the
    bot protocol class is provided as the second argument (after
    *self*)."""

    name = Attribute("""
        The name used to refer to this handler in the configuration
        file, among other places.
        """)

class ICommand(Interface):
    """A command that is invoked in response to specially-formatted IRC
    messages.
    
    The docstring is used to provide documentation for the ``help``
    command plugin, with ``%s`` standing in for the keyword assigned by
    the bot's configuration.  Generally, command docstrings take the
    form of a brief usage note, with the following formatting:

    * Text to be typed literally by the user, including the command
      keyword, is presented in boldface, through wrapping with the IRC
      format code ``\\x02``.
    * Variable names are presented with an underline, through wrapping
      with the IRC format code ``\\x1F``.
    * Optional arguments are surrounded by unformatted square brackets.
    * Choices among mutually-exclusive arguments are separated with
      vertical pipes.

    For example::

        class SampleCommand(object):
            '''
            \\x02%s\\x02
            \\x1Fa\\x1F|\\x1Fb\\x1F|\\x1Fc\\x1F
            [\\x1Foptional_argument\\x1F] -
            Provides an example within documentation.
            '''

    This would be presented to a typical IRC client as follows, assuming
    that the command keyword ``sample`` has been assigned:

        **sample** *a* | *b* | *c* [*optional_argument*] - Provides an
        example within documentation.
    """

    def execute(self, bot, prefix, reply_target, channel, args):
        """Invoked when a command message is seen.

        :param bot: The current bot protocol instance.
        :type bot: :py:class:`omnipresence.IRCClient`
        :param str prefix: The ``nick@user!host`` prefix of the user
            that invoked this command.
        :param str reply_target: The target of command output
            redirection suggested by the invoking user with ``>
            target``, or *prefix* if no such redirection is specified.
            This is not necessarily a valid prefix or nickname, as it is
            given by the user!
        :param str channel: The channel on which the command was
            invoked.  For private messages, this is generally the bot's
            own nickname.
        :param str args: The arguments passed with the command,
            including the keyword used to invoke the command (``"keyword
            arg1 arg2"``).

        Generally, a command's :py:meth:`execute` method should either
        call the bot's :py:meth:`~omnipresence.IRCClient.reply` method
        and (implicitly) return ``None``; or create a Twisted
        :py:class:`~twisted.internet.defer.Deferred` object, add a
        callback that calls :py:meth:`~omnipresence.IRCClient.reply`,
        and return that :py:class:`~twisted.internet.defer.Deferred`
        (see :ref:`using-deferreds`).  An error handler will be
        automatically added that replies with the associated value of
        any exceptions that are not handled by the command itself.

        Most command plugins shipped with Omnipresence send error or
        "no-result" replies to *prefix*, giving the invoking user a
        chance to correct any potential mistakes, while successful
        replies are sent to *reply_target*::

            def execute(self, bot, prefix, reply_target, channel, args):
                results = do_something(args)

                if not results:
                    bot.reply(prefix, channel, 'No results found.')
                    return

                bot.reply(reply_target, channel, results[0])
        """

    name = Attribute("""
        The name used to refer to this command in the configuration
        file, among other places.
        """)
