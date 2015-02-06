# -*- test-case-name: omnipresence.plugins.help.test
"""Event plugins for providing command help."""


from ...message import collapse
from ...plugin import EventPlugin


class Default(EventPlugin):
    def on_command(self, msg):
        args = msg.content.split(None, 1)
        # FIXME:  This definitely shouldn't be implemented here.
        keywords = {}
        for p, k in msg.connection.event_plugins.get(msg.venue, []):
            for keyword in k:
                keywords[keyword] = p
        if not args:
            return collapse("""\
                Available commands: \x02{keywords}\x02. For further help,
                use \x02{help}\x02 \x1Fkeyword\x1F. To redirect a command
                reply to another user, use \x1Fcommand\x1F \x02>\x02
                \x1Fnick\x1F.
                """.format(
                    keywords='\x02, \x02'.join(sorted(keywords.iterkeys())),
                    help=msg.subaction))
        if args[0] in keywords:
            # FIXME:  Detect whether or not anything was actually
            # returned and display a default "No further help is
            # available" message if not.
            return keywords[args[0]].respond_to(msg._replace(
                action='cmdhelp', subaction=args[0],
                content=''.join(args[1:])))
        return 'There is no command with the keyword \x02{}\x02.'.format(
            args[0])

    def on_cmdhelp(self, msg):
        return collapse("""\
            \x02{}\x02 [\x1Fkeyword\x1F] - List available command
            keywords, or, given a keyword, get detailed help on a
            specific command.
            """.format(msg.subaction))
