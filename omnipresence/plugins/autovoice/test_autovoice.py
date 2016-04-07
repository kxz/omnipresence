"""Unit tests for the autovoice event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...message import MessageType
from ...test.helpers import ConnectionTestMixin, OutgoingPlugin

from . import Default


class AutovoiceTestCase(ConnectionTestMixin, TestCase):
    def setUp(self):
        super(AutovoiceTestCase, self).setUp()
        self.connection.settings.enable(Default.name, [])
        self.outgoing = self.connection.settings.enable(
            OutgoingPlugin.name, [])
        self.connection.joined(self.channels[0])

    @inlineCallbacks
    def test_unmoderated_voice(self):
        yield self.receive('JOIN ' + self.channels[0])
        self.assertEqual(self.outgoing.last_seen.action, MessageType.mode)
        self.assertEqual(self.outgoing.last_seen.venue, self.channels[0])
        self.assertEqual(self.outgoing.last_seen.content,
                         '+v {}'.format(self.other_users[0].nick))

    @inlineCallbacks
    def test_moderated_no_voice(self):
        yield self.receive('MODE {} +m'.format(self.channels[0]))
        yield self.receive('JOIN ' + self.channels[0])
        self.assertNotEqual(self.outgoing.last_seen.action, MessageType.mode)
