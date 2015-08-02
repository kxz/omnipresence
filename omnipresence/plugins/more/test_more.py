"""Unit tests for the more event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from itertools import count, imap

from ...message import Message, collapse
from ...test.helpers import AbstractCommandTestCase, OutgoingPlugin

from . import Default


class MoreTestCase(AbstractCommandTestCase):
    command_class = Default

    def setUp(self):
        super(MoreTestCase, self).setUp()
        self.outgoing = self.connection.settings.enable(
            OutgoingPlugin.name, [])
        self.connection.joined('#foo')

    def assert_reply(self, content, expected, **kwargs):
        kwargs.setdefault('venue', '#foo')
        msg = self.command_message(content, **kwargs)
        self.command.respond_to(msg)
        self.assertEqual(self.outgoing.last_seen.content.split(': ', 1)[-1],
                         expected)

    def test_no_buffer(self):
        self.assert_reply('', 'No text in buffer.')

    def test_own_buffer(self):
        self.connection.buffer_reply(imap(str, count()), Message(
            self.connection, False, 'command',
            actor=self.other_user, venue='#foo'))
        self.assert_reply('', '0')
        self.assert_reply('', '1')
        self.assert_reply('', '2')

    def test_other_buffer_sequence(self):
        self.connection.buffer_reply(map(str, xrange(10)), Message(
            self.connection, False, 'command',
            actor='party3', venue='#foo'))
        self.assert_reply('party3', '0 (+9 more characters)')
        # Make sure party3's buffer hasn't been advanced.
        self.assert_reply('party3', '0 (+9 more characters)')
        self.assert_reply('', '0 (+9 more characters)', actor='party3')
        self.assert_reply('party3', '1 (+8 more characters)')
        self.assert_reply('', '1 (+8 more characters)', actor='party3')
        self.assert_reply('party3', '2 (+7 more characters)')
        self.assert_reply('', '2 (+7 more characters)', actor='party3')

    def test_other_buffer_iterator(self):
        self.connection.buffer_reply(imap(str, count()), Message(
            self.connection, False, 'command',
            actor='party3', venue='#foo'))
        self.assert_reply('party3', '0')
        # Make sure party3's buffer hasn't been advanced.
        self.assert_reply('party3', '0')
        self.assert_reply('', '0', actor='party3')
        self.assert_reply('party3', '1')
        self.assert_reply('', '1', actor='party3')
        self.assert_reply('party3', '2')
        self.assert_reply('', '2', actor='party3')
