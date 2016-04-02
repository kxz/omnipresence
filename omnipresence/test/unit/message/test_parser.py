"""Unit tests for raw message parsing."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial.unittest import TestCase

from ....hostmask import Hostmask
from ....message import Message, MessageType
from ....message.parser import IRCV2_PARSER
from ...helpers import DummyConnection


class ParserTestMixin(object):
    def setUp(self):
        self.connection = DummyConnection()

    def parse(self, raw, **kwargs):
        msg = self.parser.parse(
            self.connection, False, ':nick!user@host ' + raw, **kwargs)
        if raw:
            self.assertEqual(msg.actor, Hostmask('nick', 'user', 'host'))
        return msg


class IRCv2ParserTestCase(ParserTestMixin, TestCase):
    def setUp(self):
        super(IRCv2ParserTestCase, self).setUp()
        self.parser = IRCV2_PARSER

    def test_quit(self):
        msg = self.parse('QUIT :lorem ipsum')
        self.assertEqual(msg.action, MessageType.quit)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_nick(self):
        msg = self.parse('NICK :other')
        self.assertEqual(msg.action, MessageType.nick)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'other')
        self.assertFalse(msg.private)

    def test_channel_message(self):
        msg = self.parse('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_private_message(self):
        msg = self.parse('PRIVMSG foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)

    def test_ctcp_query(self):
        msg = self.parse('PRIVMSG #foo :\x01tag param\x01')
        self.assertEqual(msg.action, MessageType.ctcpquery)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'tag')
        self.assertEqual(msg.content, 'param')
        self.assertFalse(msg.private)

    def test_ctcp_reply(self):
        msg = self.parse('NOTICE #foo :\x01tag param\x01')
        self.assertEqual(msg.action, MessageType.ctcpreply)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'tag')
        self.assertEqual(msg.content, 'param')
        self.assertFalse(msg.private)

    def test_channel_notice(self):
        msg = self.parse('NOTICE #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.notice)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_private_notice(self):
        msg = self.parse('NOTICE foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.notice)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)

    def test_action_query(self):
        msg = self.parse('PRIVMSG #foo :\x01ACTION lorem ipsum\x01')
        self.assertEqual(msg.action, MessageType.action)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_action_reply(self):
        msg = self.parse('NOTICE #foo :\x01ACTION lorem ipsum\x01')
        self.assertEqual(msg.action, MessageType.action)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_topic(self):
        msg = self.parse('TOPIC #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.topic)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_join(self):
        msg = self.parse('JOIN #foo')
        self.assertEqual(msg.action, MessageType.join)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertIsNone(msg.content)
        self.assertFalse(msg.private)

    def test_part(self):
        msg = self.parse('PART #foo :lorem ipsum')
        self.assertEqual(msg.action, MessageType.part)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_part_without_message(self):
        msg = self.parse('PART #foo')
        self.assertEqual(msg.action, MessageType.part)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, '')
        self.assertFalse(msg.private)

    def test_mode(self):
        msg = self.parse('MODE #foo +mo other')
        self.assertEqual(msg.action, MessageType.mode)
        self.assertEqual(msg.venue, '#foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, '+mo other')
        self.assertFalse(msg.private)

    def test_kick(self):
        msg = self.parse('KICK #foo other :lorem ipsum')
        self.assertEqual(msg.action, MessageType.kick)
        self.assertEqual(msg.venue, '#foo')
        self.assertEqual(msg.target, 'other')
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertFalse(msg.private)

    def test_unknown(self):
        msg = self.parse('NONSENSE a b c :foo bar')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'NONSENSE')
        self.assertEqual(msg.content, 'a b c :foo bar')
        self.assertFalse(msg.private)

    def test_empty(self):
        msg = self.parse('')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertIsNone(msg.content)
        self.assertFalse(msg.private)

    def test_malformed(self):
        msg = self.parse('PRIVMSG')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'PRIVMSG')
        self.assertEqual(msg.content, '')
        self.assertFalse(msg.private)

    def test_malformed_with_params(self):
        msg = self.parse('KICK not :enough arguments')
        self.assertEqual(msg.action, MessageType.unknown)
        self.assertIsNone(msg.venue)
        self.assertIsNone(msg.target)
        self.assertEqual(msg.subaction, 'KICK')
        self.assertEqual(msg.content, 'not :enough arguments')
        self.assertFalse(msg.private)

    def test_override(self):
        msg = self.parse('PRIVMSG #foo :lorem ipsum', venue='foo')
        self.assertEqual(msg.action, MessageType.privmsg)
        self.assertEqual(msg.venue, 'foo')
        self.assertIsNone(msg.target)
        self.assertIsNone(msg.subaction)
        self.assertEqual(msg.content, 'lorem ipsum')
        self.assertTrue(msg.private)
