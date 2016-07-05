"""Unit tests for the autorejoin event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...message import MessageType
from ...test.helpers import ConnectionTestMixin, OutgoingPlugin

from . import Default


class AutorejoinTestCase(ConnectionTestMixin, TestCase):
    def setUp(self):
        super(AutorejoinTestCase, self).setUp()
        self.connection.settings.enable(Default.name, [])
        self.outgoing = self.connection.settings.enable(
            OutgoingPlugin.name, [])
        self.connection.joined(self.channels[0])
        self.connection.names_arrived(self.channels[0],
                                      (self.other_users[1].nick,))

    @inlineCallbacks
    def test_kicked(self):
        yield self.receive('KICK {} {} :kick message'.format(
            self.channels[0], self.connection.nickname))
        self.assertEqual(self.outgoing.last_seen.action, MessageType.join)
        self.assertEqual(self.outgoing.last_seen.venue, self.channels[0])

    @inlineCallbacks
    def test_other_kicked(self):
        yield self.receive('KICK {} {} :kick message'.format(
            self.channels[0], self.other_users[1].nick))
        self.assertEqual(self.outgoing.last_seen.action, MessageType.kick)
