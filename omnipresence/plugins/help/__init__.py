# -*- test-case-name: omnipresence.plugins.help.test
"""Event plugins for providing command help."""


import re

from ...plugin import EventPlugin


WHITESPACE = re.compile('\s+')


def reflow(string):
    """Return *string* with runs of whitespace replaced by single spaces
    and any leading or trailing whitespace stripped."""
    return WHITESPACE.sub(' ', string).strip()


class Default(EventPlugin):
    def command(self, msg):
        args = msg.content.split(None, 1)
        # FIXME:  This definitely shouldn't be implemented here.
        keywords = {}
        for p, k in msg.connection.event_plugins.get(msg.venue, []):
            for keyword in k:
                keywords[keyword] = p
        if not args:
            return reflow("""\
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

    def cmdhelp(self, msg):
        return reflow("""\
            \x02{}\x02 [\x1Fkeyword\x1F] - List available command
            keywords, or, given a keyword, get detailed help on a
            specific command.
        """.format(msg.subaction))

Default.register(Default.command, 'command')
Default.register(Default.cmdhelp, 'cmdhelp')
