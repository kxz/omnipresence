"""Unit tests for the dice event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from ...hostmask import Hostmask
from ...message import Message, collapse
from ...plugin import UserVisibleError
from ...test.helpers import AbstractConnectionTestCase

from . import Default


class DummyRandom(object):
    def randint(self, a, b):
        return b


class DiceTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(DiceTestCase, self).setUp()
        self.dice = self.connection.add_event_plugin(
            Default, {'#foo': ['dice']})
        self.dice.random = DummyRandom()

    def send_command(self, args, actor):
        if actor is None:
            actor = Hostmask('nick', 'user', 'host')
        return Message(self.connection, False, 'command', actor=actor,
                       venue='#foo', subaction='dice', content=args)

    def assert_reply(self, args, expected_reply, actor=None):
        msg = self.send_command(args, actor)
        self.assertEqual(self.dice.respond_to(msg), expected_reply)

    def assert_error(self, args, expected_reply, actor=None):
        msg = self.send_command(args, actor)
        e = self.assertRaises(UserVisibleError, self.dice.respond_to, msg)
        self.assertEqual(str(e), expected_reply)

    def test_show(self):
        self.assert_reply('', 'Bank has no rolls.')
        self.assert_reply('show', 'Bank has no rolls.')

    def test_simple_rolls(self):
        self.assert_reply('roll 4 d6 3d10 4d8',
                          'Rolled \x024 6 8 8 8 8 10 10 10\x02 = 72.')

    def test_bad_rolls(self):
        self.assert_error('roll asdf',
                          'Invalid die group specification asdf.')
        self.assert_error('roll -1d16', 'Invalid number of dice -1.')
        self.assert_error('roll 1d-20', 'Invalid die size -20.')

    def test_bank_accumulation(self):
        self.assert_reply('add d6 3d10 4d8', collapse("""\
            Rolled \x026 8 8 8 8 10 10 10\x02 = 68.
            Bank now has \x026 8 8 8 8 10 10 10\x02 = 68.
            """))
        self.assert_reply('add d4', collapse("""\
            Rolled \x024\x02 = 4.
            Bank now has \x024 6 8 8 8 8 10 10 10\x02 = 72.
            """))
        self.assert_reply('new d4', collapse("""\
            Rolled \x024\x02 = 4.
            Bank now has \x024\x02 = 4.
            """))
        self.assert_reply('clear', 'Bank cleared.')
        self.assert_reply('', 'Bank has no rolls.')

    def test_bank_isolation(self):
        self.assert_reply('add d6 3d10 4d8', collapse("""\
            Rolled \x026 8 8 8 8 10 10 10\x02 = 68.
            Bank now has \x026 8 8 8 8 10 10 10\x02 = 68.
            """))
        self.assert_reply('', 'Bank has no rolls.',
                          actor=Hostmask('other', 'user', 'host'))
        self.assert_reply('show nick',
                          'Bank has \x026 8 8 8 8 10 10 10\x02 = 68.')

    def test_bank_follows_nick(self):
        self.assert_reply('add d6 3d10 4d8', collapse("""\
            Rolled \x026 8 8 8 8 10 10 10\x02 = 68.
            Bank now has \x026 8 8 8 8 10 10 10\x02 = 68.
            """))
        self.dice.respond_to(Message(
            self.connection, False, 'nick',
            actor=Hostmask('nick', 'user', 'host'), content='other'))
        self.assert_reply('', 'Bank has no rolls.')
        self.assert_reply('', 'Bank has \x026 8 8 8 8 10 10 10\x02 = 68.',
                          actor=Hostmask('other', 'user', 'host'))

    def test_use(self):
        self.assert_reply('add d6 3d10 4d8', collapse("""\
            Rolled \x026 8 8 8 8 10 10 10\x02 = 68.
            Bank now has \x026 8 8 8 8 10 10 10\x02 = 68.
            """))
        self.assert_reply('use 6 8 10', collapse("""\
            Used \x026 8 10\x02 = 24.
            Bank now has \x028 8 8 10 10\x02 = 44.
            """))
        self.assert_error('use 1 2 3 8', collapse("""\
            You do not have enough 1s, 2s, and 3s in your die bank to
            use those rolls.
            """))
