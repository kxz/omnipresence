"""Unit tests for the more event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from itertools import count, imap

from twisted.trial.unittest import TestCase

from ...message.buffering import ReplyBuffer
from ...settings import PRIVATE_CHANNEL
from ...test.helpers import CommandTestMixin, OutgoingPlugin

from . import Default


class MoreTestCase(CommandTestMixin, TestCase):
    command_class = Default

    def setUp(self):
        super(MoreTestCase, self).setUp()
        self.outgoing = self.connection.settings.enable(
            OutgoingPlugin.name, [])
        self.connection.joined('#foo')

    def buffer_reply(self, venue, nick, buf):
        self.connection.venues[venue].add_nick(nick)
        self.connection.venues[venue].nicks[nick].reply_buffer = (
            ReplyBuffer(buf))

    def assert_reply(self, content, expected, **kwargs):
        kwargs.setdefault('venue', '#foo')
        msg = self.command_message(content, **kwargs)
        self.connection.respond_to(msg)
        self.assertEqual(self.outgoing.last_seen.content.split(': ', 1)[-1],
                         expected)

    def test_no_buffer(self):
        self.assert_reply('', 'No results.')

    def test_own_buffer(self):
        self.buffer_reply('#foo', self.other_users[0].nick, imap(str, count()))
        self.assert_reply('', '0')
        self.assert_reply('', '1')
        self.assert_reply('', '2')

    def test_other_buffer_sequence(self):
        self.buffer_reply('#foo', 'party3', map(str, xrange(10)))
        self.assert_reply('party3', '0 (+9 more)')
        # Make sure party3's buffer hasn't been advanced.
        self.assert_reply('party3', '0 (+9 more)')
        self.assert_reply('', '0 (+9 more)', actor='party3')
        self.assert_reply('party3', '1 (+8 more)')
        self.assert_reply('', '1 (+8 more)', actor='party3')
        self.assert_reply('party3', '2 (+7 more)')
        self.assert_reply('', '2 (+7 more)', actor='party3')

    def test_other_buffer_iterator(self):
        self.buffer_reply('#foo', 'party3', imap(str, count()))
        self.assert_reply('party3', '0')
        # Make sure party3's buffer hasn't been advanced.
        self.assert_reply('party3', '0')
        self.assert_reply('', '0', actor='party3')
        self.assert_reply('party3', '1')
        self.assert_reply('', '1', actor='party3')
        self.assert_reply('party3', '2')
        self.assert_reply('', '2', actor='party3')

    def test_other_buffer_private(self):
        self.buffer_reply(PRIVATE_CHANNEL, self.other_users[0].nick,
                          'hello world')
        self.buffer_reply(PRIVATE_CHANNEL, 'party3',
                          'lorem ipsum dolor sit amet')
        self.assert_reply(
            'party3',
            "You cannot read another user's private reply buffer.",
            venue=self.connection.nickname)
        self.assert_reply('', 'hello world', venue=self.connection.nickname)
