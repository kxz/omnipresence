"""Unit tests for the more event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from itertools import count

from ...message import Message, collapse
from ...test.helpers import AbstractConnectionTestCase, OutgoingPlugin

from . import Default


class MoreTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(MoreTestCase, self).setUp()
        self.more = self.connection.add_event_plugin(
            Default, {'#foo': ['more']})

    def assert_reply(self, actor, args, expected_reply):
        msg = Message(self.connection, False, 'command',
                      actor=actor, venue='#foo',
                      subaction='more', content=args)
        self.assertEqual(self.more.respond_to(msg), expected_reply)

    def test_no_buffer(self):
        self.assert_reply('', self.other_user, 'No text in buffer.')

    def test_own_buffer(self):
        self.connection.buffer_reply(count(), Message(
            self.connection, False, 'command', actor=self.other_user))
        self.assert_reply('', self.other_user, '0')

    def test_other_buffer_sequence(self):
        self.connection.buffer_reply(range(10), Message(
            self.connection, False, 'command', actor='party3'))
        self.assert_reply('party3', self.other_user, '0')
        self.assert_reply('', 'party3', '0')

    def test_other_buffer_iterator(self):
        self.connection.buffer_reply(count(), Message(
            self.connection, False, 'command', actor=self.other_user))
        self.assert_reply('party3', self.other_user, '0')
        self.assert_reply('', 'party3', '0')
