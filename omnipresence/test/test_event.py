"""Unit tests for event delegation."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from .. import IRCClient
from ..hostmask import Hostmask
from ..plugin import EventPlugin
from ._helpers import AbstractConnectionTestCase


class EventDelegationTestCase(AbstractConnectionTestCase):
    def setUp(self):
        self.plugin = EventPlugin()

        @self.plugin.on_registration
        def registered(plugin, bot):
            plugin.last_seen = None

        @self.plugin.on('privmsg', 'quit')
        def callback(plugin, msg):
            plugin.last_seen = msg

        super(EventDelegationTestCase, self).setUp()
        self.connection.event_plugins['dummy'] = self.plugin
        # XXX:  Figure out how to declare channel-specific stuff.

    def _send(self, line):
        self.connection.lineReceived(':other!user@host ' + line)

    def test_configure(self):
        self.assertIsNone(self.plugin.last_seen)

    def test_privmsg(self):
        self._send('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(self.plugin.last_seen.actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(self.plugin.last_seen.action, 'privmsg')
        self.assertEqual(self.plugin.last_seen.venue, '#foo')
        self.assertEqual(self.plugin.last_seen.content, 'lorem ipsum')
        self.assertFalse(self.plugin.last_seen.private)

    def test_visible_quit(self):
        # XXX:  Add "other" to visible channel.
        self._send('QUIT :Client Quit')
        self.assertEqual(self.plugin.last_seen.actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(self.plugin.last_seen.action, 'quit')
        self.assertIsNone(self.plugin.last_seen.venue)
        self.assertEqual(self.plugin.last_seen.content, 'Client Quit')
        self.assertFalse(self.plugin.last_seen.private)

    def test_invisible_quit(self):
        self._send('QUIT :Client Quit')
        self.assertIsNone(self.plugin.last_seen)


class DeferredCallbackTestCase(AbstractConnectionTestCase):
    pass
