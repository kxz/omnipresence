"""Unit tests for IRC message handling."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial.unittest import TestCase

from ..hostmask import Hostmask
from ..message import Message, MessageType
from .helpers import DummyConnection


class MessageTestCase(TestCase):
    def test_invalid_action(self):
        self.assertRaises(ValueError, Message, None, False, 'foo')


class RawParsingTestCase(TestCase):
    def setUp(self):
        self.connection = DummyConnection()

    def _from_raw(self, raw, **kwargs):
        msg = Message.from_raw(
            self.connection, False, ':nick!user@host ' + raw, **kwargs)
        if raw:
            self.assertEqual(msg.actor, Hostmask('nick', 'user', 'host'))
        return msg

    def test_quit(self):
        msg = self._from_raw('QUIT :lorem ipsum')
        self.assertEqual(msg.action, MessageType.quit)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_nick(self):
        msg = self._from_raw('NICK :other')
        self.assertEqual(msg.action, MessageType.nick)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'other')
        self.assertFalse(msg.private)

    def test_channel_message(self):
        msg = self._from_raw('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_private_message(self):
        msg = self._from_raw('PRIVMSG foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)

    def test_ctcp_query(self):
        msg = self._from_raw('PRIVMSG #foo :\x01tag param\x01')
        self.assertEqual(msg.action, MessageType.ctcpquery)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'tag')
        self.assertEqual(msg.content, 'param')
        self.assertFalse(msg.private)

    def test_ctcp_reply(self):
        msg = self._from_raw('NOTICE #foo :\x01tag param\x01')
        self.assertEqual(msg.action, MessageType.ctcpreply)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'tag')
        self.assertEqual(msg.content, 'param')
        self.assertFalse(msg.private)

    def test_channel_notice(self):
        msg = self._from_raw('NOTICE #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.notice)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_private_notice(self):
        msg = self._from_raw('NOTICE foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.notice)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)

    def test_action_query(self):
        msg = self._from_raw('PRIVMSG #foo :\x01ACTION lorem ipsum\x01')
        self.assertEqual(msg.action, MessageType.action)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_action_reply(self):
        msg = self._from_raw('NOTICE #foo :\x01ACTION lorem ipsum\x01')
        self.assertEqual(msg.action, MessageType.action)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_topic(self):
        msg = self._from_raw('TOPIC #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.topic)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_join(self):
        msg = self._from_raw('JOIN #foo')
        self.assertEqual(msg.action, MessageType.join)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertIsNone(msg.content)
        self.assertFalse(msg.private)

    def test_part(self):
        msg = self._from_raw('PART #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.part)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_part_without_message(self):
        msg = self._from_raw('PART #foo')
        self.assertEqual(msg.action, MessageType.part)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, '')
        self.assertFalse(msg.private)

    def test_mode(self):
        msg = self._from_raw('MODE #foo +mo other')
        self.assertEqual(msg.action, MessageType.mode)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, '+mo other')
        self.assertFalse(msg.private)

    def test_kick(self):
        msg = self._from_raw('KICK #foo other :lorem ipsum')
        self.assertEqual(msg.action, MessageType.kick)
        self.assertEqual(msg.venue, '#foo')
        self.assertEqual(msg.target, 'other')
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_unknown(self):
        msg = self._from_raw('NONSENSE a b c :foo bar')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'NONSENSE')
        self.assertEqual(msg.content, 'a b c :foo bar')
        self.assertFalse(msg.private)

    def test_empty(self):
        msg = self._from_raw('')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertIsNone(msg.content)
        self.assertFalse(msg.private)

    def test_malformed(self):
        msg = self._from_raw('PRIVMSG')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'PRIVMSG')
        self.assertEqual(msg.content, '')
        self.assertFalse(msg.private)

    def test_malformed_with_params(self):
        msg = self._from_raw('KICK not :enough arguments')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'KICK')
        self.assertEqual(msg.content, 'not :enough arguments')
        self.assertFalse(msg.private)

    def test_override(self):
        msg = self._from_raw('PRIVMSG #foo :lorem ipsum', venue='foo')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)


class ExtractionTestCase(TestCase):
    def setUp(self):
        self.connection = DummyConnection()
        self.prototype = Message(
            self.connection, False, 'privmsg', 'nick!user@host')

    def _extract(self, content):
        return self.prototype._replace(content=content).extract_command(
            prefixes=['!', 'bot:', 'bot,'])

    def test_ignore_non_privmsg(self):
        self.assertIsNone(Message(
            self.connection, 'nick!user@host', 'topic').extract_command())

    def test_ignore_missing_prefix(self):
        self.assertIsNone(self._extract('ipsum'))

    def test_ignore_missing_content(self):
        self.assertIsNone(self._extract('!'))

    def test_simple_command(self):
        msg = self._extract('!help')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_simple_command_with_long_prefix(self):
        msg = self._extract('bot: help')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_command_with_arguments(self):
        msg = self._extract('bot, help me')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, 'me')

    def test_command_redirection(self):
        msg = self._extract('!help > other')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'other')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')

    def test_empty_command_redirection(self):
        msg = self._extract('!help >')
        self.assertEqual(msg.action, MessageType.command)
        self.assertEqual(msg.target, 'nick')
        self.assertEqual(msg.subaction, 'help')
        self.assertEqual(msg.content, '')
