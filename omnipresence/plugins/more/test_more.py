"""Unit tests for the more event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from itertools import count, imap

from ...message import Message, collapse
from ...test.helpers import AbstractConnectionTestCase, OutgoingPlugin

from . import Default


class MoreTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(MoreTestCase, self).setUp()
        self.more = self.connection.add_event_plugin(
            Default, {'#foo': ['more']})
        self.outgoing = self.connection.add_event_plugin(
            OutgoingPlugin, {'#foo': []})
        self.connection.joined('#foo')

    def assert_reply(self, actor, args, expected_reply):
        msg = Message(self.connection, False, 'command',
                      actor=actor, venue='#foo',
                      subaction='more', content=args)
        self.more.respond_to(msg)
        self.assertEqual(self.outgoing.last_seen.content.split(': ')[-1],
                         expected_reply)

    def test_no_buffer(self):
        self.assert_reply('', self.other_user, 'No text in buffer.')

    def test_own_buffer(self):
        self.connection.buffer_reply(imap(str, count()), Message(
            self.connection, False, 'command',
            actor=self.other_user, venue='#foo'))
        self.assert_reply(self.other_user, '', '0')
        self.assert_reply(self.other_user, '', '1')
        self.assert_reply(self.other_user, '', '2')

    def test_other_buffer_sequence(self):
        self.connection.buffer_reply(map(str, xrange(10)), Message(
            self.connection, False, 'command',
            actor='party3', venue='#foo'))
        self.assert_reply(self.other_user, 'party3', '0 (+9 more characters)')
        # Make sure party3's buffer hasn't been advanced.
        self.assert_reply(self.other_user, 'party3', '0 (+9 more characters)')
        self.assert_reply('party3', '', '0 (+9 more characters)')
        self.assert_reply(self.other_user, 'party3', '1 (+8 more characters)')
        self.assert_reply('party3', '', '1 (+8 more characters)')
        self.assert_reply(self.other_user, 'party3', '2 (+7 more characters)')
        self.assert_reply('party3', '', '2 (+7 more characters)')

    def test_other_buffer_iterator(self):
        self.connection.buffer_reply(imap(str, count()), Message(
            self.connection, False, 'command',
            actor='party3', venue='#foo'))
        self.assert_reply(self.other_user, 'party3', '0')
        # Make sure party3's buffer hasn't been advanced.
        self.assert_reply(self.other_user, 'party3', '0')
        self.assert_reply('party3', '', '0')
        self.assert_reply(self.other_user, 'party3', '1')
        self.assert_reply('party3', '', '1')
        self.assert_reply(self.other_user, 'party3', '2')
        self.assert_reply('party3', '', '2')
