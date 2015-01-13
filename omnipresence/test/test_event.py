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
            plugin.seen = []

        @self.plugin.on('privmsg', 'quit')
        def callback(plugin, msg):
            plugin.seen.append(msg)

        super(EventDelegationTestCase, self).setUp()
        self.connection.add_event_plugin(self.plugin, ['#foo', '#bar'])

    def _send(self, line):
        self.connection.lineReceived(':other!user@host ' + line)

    def test_configure(self):
        self.assertEqual(len(self.plugin.seen), 0)

    def test_privmsg(self):
        self._send('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.plugin.seen), 1)
        self.assertEqual(self.plugin.seen[0].actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(self.plugin.seen[0].action, 'privmsg')
        self.assertEqual(self.plugin.seen[0].venue, '#foo')
        self.assertEqual(self.plugin.seen[0].content, 'lorem ipsum')
        self.assertFalse(self.plugin.seen[0].private)

    def test_privmsg_casemapping(self):
        self._send('PRIVMSG #FOO :lorem ipsum')
        self.assertEqual(len(self.plugin.seen), 1)
        self.assertEqual(self.plugin.seen[0].actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(self.plugin.seen[0].action, 'privmsg')
        self.assertEqual(self.plugin.seen[0].venue, '#FOO')
        self.assertEqual(self.plugin.seen[0].content, 'lorem ipsum')
        self.assertFalse(self.plugin.seen[0].private)

    def test_visible_quit(self):
        self.connection.joined(self.connection.nickname, '#foo')
        self.connection.channel_names['#foo'].add('other')
        self._send('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 1)
        self.assertEqual(self.plugin.seen[0].actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(self.plugin.seen[0].action, 'quit')
        self.assertIsNone(self.plugin.seen[0].venue)
        self.assertEqual(self.plugin.seen[0].content, 'Client Quit')
        self.assertFalse(self.plugin.seen[0].private)

    def test_visible_quit_call_once(self):
        for channel in ('#foo', '#bar'):
            self.connection.joined(self.connection.nickname, channel)
            self.connection.channel_names[channel].add('other')
        self._send('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 1)

    def test_invisible_quit(self):
        self._send('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 0)


class DeferredCallbackTestCase(AbstractConnectionTestCase):
    pass
