"""Unit tests for the help event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from ...message import Message, collapse
from ...test.helpers import AbstractConnectionTestCase

from . import Default


class HelpTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(HelpTestCase, self).setUp()
        self.plugin = self.connection.add_event_plugin(
            Default, {'#foo': ['help']})

    def assert_reply(self, args, expected_reply):
        deferred = self.plugin.respond_to(Message(
            self.connection, False, 'command',
            venue='#foo', subaction='help', content=args))
        deferred.addCallback(self.assertEqual, expected_reply)
        return deferred

    def test_no_arguments(self):
        return self.assert_reply('', collapse("""\
            Available commands: \x02help\x02. For further help, use
            \x02help\x02 \x1Fkeyword\x1F. To redirect a command reply to
            another user, use \x1Fcommand\x1F \x02>\x02 \x1Fnick\x1F.
            """))

    def test_missing_command(self):
        return self.assert_reply('lorem', collapse("""\
            There is no command with the keyword \x02lorem\x02.
            """))

    def test_own_help(self):
        return self.assert_reply('help', collapse("""\
            \x02help\x02 [\x1Fkeyword\x1F] - List available command
            keywords, or, given a keyword, get detailed help on a
            specific command.
            """))
