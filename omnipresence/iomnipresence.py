from zope.interface import Interface, Attribute

class IHandler(Interface):
    """
    A handler that responds to IRC events passed to it by the bot.  There are 
    no required methods for this interface, since handlers may implement only a 
    subset of available events.  Callbacks are generally the same as those 
    defined in omnipresence.IRCClient, except that an instance of the bot 
    protocol class is provided as the second argument (after C{self}).
    """

    name = Attribute("""
        @type name: C{str}
        @ivar name: The name used to refer to this handler in the configuration 
        file, among other places.
        """)

class ICommand(Interface):
    """
    A command that is invoked in response to specially-formatted IRC messages.
    """

    def execute(self, bot, prefix, channel, args):
        """
        Invoked when a command message is seen.

        @type bot: C{IRCClient}
        @param bot: The bot protocol instance.  Use this to provide replies 
        through bot.msg and other bot methods.

        @type prefix: C{str}
        @param prefix: The prefix of the user that invoked this command.

        @type channel: C{str}
        @param channel: The channel on which the command was invoked.

        @type args: C{str}
        @param args: The arguments passed with the command, including the 
        keyword used to invoke the command ("keyword arg1 arg2").

        @rtype: C{None} or C{Deferred}
        @return: A C{Deferred} can be used to indicate that the command 
        will not immediately return a result; for instance, if it needs 
        to make a Web request first.
        """

    name = Attribute("""
        @type name: C{str}
        @ivar name: The name used to refer to this command in the configuration 
        file, among other places.
        """)
