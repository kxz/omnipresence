"""Unit tests for the help event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from ...message import Message, collapse
from ...plugin import EventPlugin
from ...test.helpers import AbstractConnectionTestCase

from . import Default


class HelplessPlugin(EventPlugin):
    pass


class HelpTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(HelpTestCase, self).setUp()
        self.help = self.connection.add_event_plugin(
            Default, {'#foo': ['help']})
        self.connection.add_event_plugin(
            HelplessPlugin, {'#foo': ['helpless']})

    def assert_reply(self, args, expected_reply):
        msg = Message(self.connection, False, 'command',
                      venue='#foo', subaction='help', content=args)
        self.assertEqual(self.help.respond_to(msg), expected_reply)

    def test_no_arguments(self):
        self.assert_reply('', collapse("""\
            Available commands: \x02help\x02, \x02helpless\x02. For
            further help, use \x02help\x02 \x1Fkeyword\x1F. To redirect
            a command reply to another user, use \x1Fcommand\x1F
            \x02>\x02 \x1Fnick\x1F.
            """))

    def test_missing_command(self):
        self.assert_reply('lorem', collapse("""\
            There is no command with the keyword \x02lorem\x02.
            """))

    def test_missing_help(self):
        self.assert_reply('helpless', collapse("""\
            There is no further help available for \x02helpless\x02.
            """))

    def test_own_help(self):
        self.assert_reply('help', collapse("""\
            \x02help\x02 [\x1Fkeyword\x1F] - List available command
            keywords, or, given a keyword, get detailed help on a
            specific command.
            """))