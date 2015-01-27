"""Unit tests for event delegation."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from ..hostmask import Hostmask
from ..plugin import EventPlugin
from .helpers import AbstractConnectionTestCase


class EventDelegationTestCase(AbstractConnectionTestCase):
    def setUp(self):
        self.plugin = EventPlugin()

        @self.plugin.on_registration
        def registered(plugin, bot):
            plugin.seen = []

        @self.plugin.on('privmsg', 'command', 'quit')
        def callback(plugin, msg):
            plugin.seen.append(msg)

        super(EventDelegationTestCase, self).setUp()
        self.connection.add_event_plugin(
            self.plugin, {'#foo': ['spam'], '#bar': []})

    def _send(self, line):
        self.connection.lineReceived(':other!user@host ' + line)

    def test_configure(self):
        self.assertEqual(len(self.plugin.seen), 0)

    def test_privmsg(self):
        self._send('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.plugin.seen), 1)
        last_seen = self.plugin.seen[0]
        self.assertEqual(last_seen.actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(last_seen.action, 'privmsg')
        self.assertEqual(last_seen.venue, '#foo')
        self.assertEqual(last_seen.content, 'lorem ipsum')
        self.assertFalse(last_seen.private)

    def test_own_privmsg(self):
        self.connection.sendLine('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.plugin.seen), 1)
        last_seen = self.plugin.seen[0]
        self.assertTrue(last_seen.actor.matches(self.connection.nickname))
        self.assertEqual(last_seen.action, 'privmsg')
        self.assertEqual(last_seen.venue, '#foo')
        self.assertEqual(last_seen.content, 'lorem ipsum')
        self.assertFalse(last_seen.private)

    def test_privmsg_casemapping(self):
        # This will no longer be a direct part of the event delegation
        # code once the new settings machinery works, but it might not
        # be a bad idea to keep this around as an integration test with
        # various settings for the case mapping.
        self._send('PRIVMSG #FOO :lorem ipsum')
        self.assertEqual(len(self.plugin.seen), 1)
        last_seen = self.plugin.seen[0]
        self.assertEqual(last_seen.actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(last_seen.action, 'privmsg')
        self.assertEqual(last_seen.venue, '#FOO')
        self.assertEqual(last_seen.content, 'lorem ipsum')
        self.assertFalse(last_seen.private)

    def test_command_enabled(self):
        self._send('PRIVMSG #foo :!spam ham eggs')
        self.assertEqual(len(self.plugin.seen), 2)
        last_seen = self.plugin.seen[1]
        self.assertEqual(last_seen.actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(last_seen.action, 'command')
        self.assertEqual(last_seen.venue, '#foo')
        self.assertEqual(last_seen.target, 'other')
        self.assertEqual(last_seen.subaction, 'spam')
        self.assertEqual(last_seen.content, 'ham eggs')
        self.assertFalse(last_seen.private)

    def test_command_disabled(self):
        self._send('PRIVMSG #bar :!spam ham eggs')
        self.assertEqual(len(self.plugin.seen), 1)  # no command message

    def test_command_self(self):
        self.connection.sendLine('PRIVMSG #foo :!spam ham eggs')
        self.assertEqual(len(self.plugin.seen), 1)  # no command message

    def test_visible_quit(self):
        self.connection.joined(self.connection.nickname, '#foo')
        self.connection.channel_names['#foo'].add('other')
        self._send('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 1)
        last_seen = self.plugin.seen[0]
        self.assertEqual(last_seen.actor,
                         Hostmask('other', 'user', 'host'))
        self.assertEqual(last_seen.action, 'quit')
        self.assertIsNone(last_seen.venue)
        self.assertEqual(last_seen.content, 'Client Quit')
        self.assertFalse(last_seen.private)

    def test_visible_quit_call_once(self):
        for channel in ('#foo', '#bar'):
            self.connection.joined(self.connection.nickname, channel)
            self.connection.channel_names[channel].add('other')
        self._send('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 1)

    def test_invisible_quit(self):
        self._send('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 0)

    def test_own_quit(self):
        self.connection.joined(self.connection.nickname, '#foo')
        self.connection.channel_names['#foo'].add(self.connection.nickname)
        self.connection.sendLine('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 1)
        last_seen = self.plugin.seen[0]
        self.assertTrue(last_seen.actor.matches(self.connection.nickname))
        self.assertEqual(last_seen.action, 'quit')
        self.assertIsNone(last_seen.venue)
        self.assertEqual(last_seen.content, 'Client Quit')
        self.assertFalse(last_seen.private)


class DeferredCallbackTestCase(AbstractConnectionTestCase):
    pass
