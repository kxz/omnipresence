# -*- test-case-name: omnipresence.plugins.help.test_help
"""Event plugins for providing command help."""


from twisted.internet.defer import inlineCallbacks, returnValue

from ...message import MessageType, collapse
from ...plugin import EventPlugin


class Default(EventPlugin):
    """Show detailed help for other commands, or list all available
    commands if no argument is given.

    :alice: help
    :bot: Available commands: **alpha**, **beta**, **help**.
          For further help, use **help** *keyword*.
          To redirect a command reply to another user, use *command*
          **>** *nick*.
    :alice: help alpha
    :bot: **alpha** *argument* - Help for command **alpha**.
    """

    @inlineCallbacks
    def on_command(self, msg):
        args = msg.content.split(None, 1)
        keywords = {}
        for p, k in msg.settings.active_plugins().iteritems():
            for keyword in k:
                keywords[keyword] = p
        if not args:
            returnValue(collapse("""\
                Available commands: \x02{keywords}\x02. For further help,
                use \x02{help}\x02 \x1Fkeyword\x1F. To redirect a command
                reply to another user, use \x1Fcommand\x1F \x02>\x02
                \x1Fnick\x1F.
                """.format(
                    keywords='\x02, \x02'.join(sorted(keywords.iterkeys())),
                    help=msg.subaction)))
        if args[0] in keywords:
            help_string = yield keywords[args[0]].respond_to(msg._replace(
                action=MessageType.cmdhelp, subaction=args[0],
                content=''.join(args[1:])))
            if help_string:
                returnValue(u'\x02{}\x02 {}'.format(args[0], help_string))
            returnValue('There is no further help available for \x02{}\x02.'
                        .format(args[0]))
        returnValue('There is no command with the keyword \x02{}\x02.'
                    .format(args[0]))

    def on_cmdhelp(self, msg):
        return collapse("""\
            [\x1Fkeyword\x1F] - List available command keywords, or,
            given a keyword, get detailed help on a specific command.
            """)
