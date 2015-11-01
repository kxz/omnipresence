"""Unit tests for the dice event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...hostmask import Hostmask
from ...message import Message, collapse
from ...test.helpers import CommandTestMixin

from . import Default


class DummyRandom(object):
    def randint(self, a, b):
        return b


class DiceTestCase(CommandTestMixin, TestCase):
    command_class = Default
    help_arguments = ('add', 'clear', 'new', 'notation', 'roll', 'show', 'use')

    def setUp(self):
        super(DiceTestCase, self).setUp()
        self.command.random = DummyRandom()

    @inlineCallbacks
    def test_show(self):
        yield self.send_command('')
        yield self.assert_reply('Bank has no rolls.')
        yield self.send_command('show')
        yield self.assert_reply('Bank has no rolls.')

    @inlineCallbacks
    def test_simple_rolls(self):
        yield self.send_command('roll 4 d6 3d10 4d8')
        yield self.assert_reply('Rolled \x024 6 8 8 8 8 10 10 10\x02 = 72.')

    @inlineCallbacks
    def test_bad_rolls(self):
        yield self.send_command('roll 2d6 asdf')
        self.assert_error('Invalid die group specification asdf.')
        yield self.send_command('roll -1d16')
        self.assert_error('Invalid number of dice -1.')
        yield self.send_command('roll 1d-20')
        self.assert_error('Invalid die size -20.')

    @inlineCallbacks
    def test_bank_accumulation(self):
        yield self.send_command('add d6 3d10 4d8')
        yield self.assert_reply(collapse("""\
            Rolled \x026 8 8 8 8 10 10 10\x02 = 68.
            Bank now has \x026 8 8 8 8 10 10 10\x02 = 68.
            """))
        yield self.send_command('add d4')
        yield self.assert_reply(collapse("""\
            Rolled \x024\x02 = 4.
            Bank now has \x024 6 8 8 8 8 10 10 10\x02 = 72.
            """))
        yield self.send_command('new d4')
        yield self.assert_reply(collapse("""\
            Rolled \x024\x02 = 4.
            Bank now has \x024\x02 = 4.
            """))
        yield self.send_command('clear')
        yield self.assert_reply('Bank cleared.')
        yield self.send_command('')
        yield self.assert_reply('Bank has no rolls.')

    @inlineCallbacks
    def test_bank_isolation(self):
        yield self.send_command('add d6 3d10 4d8')
        yield self.assert_reply(collapse("""\
            Rolled \x026 8 8 8 8 10 10 10\x02 = 68.
            Bank now has \x026 8 8 8 8 10 10 10\x02 = 68.
            """))
        yield self.send_command('', actor=self.other_users[1])
        yield self.assert_reply('Bank has no rolls.')
        yield self.send_command('show {}'.format(self.other_users[0].nick),
                                actor=self.other_users[1])
        yield self.assert_reply('Bank has \x026 8 8 8 8 10 10 10\x02 = 68.')

    @inlineCallbacks
    def test_bank_follows_nick(self):
        yield self.send_command('add d6 3d10 4d8')
        yield self.assert_reply(collapse("""\
            Rolled \x026 8 8 8 8 10 10 10\x02 = 68.
            Bank now has \x026 8 8 8 8 10 10 10\x02 = 68.
            """))
        yield self.command.respond_to(Message(
            self.connection, False, 'nick',
            actor=self.other_users[0], content=self.other_users[1].nick))
        yield self.send_command('')
        yield self.assert_reply('Bank has no rolls.')
        yield self.send_command('', actor=self.other_users[1])
        yield self.assert_reply('Bank has \x026 8 8 8 8 10 10 10\x02 = 68.')

    @inlineCallbacks
    def test_use(self):
        yield self.send_command('add d6 3d10 4d8')
        yield self.assert_reply(collapse("""\
            Rolled \x026 8 8 8 8 10 10 10\x02 = 68.
            Bank now has \x026 8 8 8 8 10 10 10\x02 = 68.
            """))
        yield self.send_command('use 6 8 10')
        yield self.assert_reply(collapse("""\
            Used \x026 8 10\x02 = 24.
            Bank now has \x028 8 8 10 10\x02 = 44.
            """))
        yield self.send_command('use 1 2 3 8')
        self.assert_error(collapse("""\
            You do not have enough 1s, 2s, and 3s in your die bank to
            use those rolls.
            """))
