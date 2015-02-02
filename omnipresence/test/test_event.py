"""Unit tests for event delegation."""
# pylint: disable=missing-docstring,too-few-public-methods


import gc

from twisted.internet.defer import Deferred
from twisted.trial import unittest

from ..hostmask import Hostmask
from ..message import Message
from ..plugin import EventPlugin
from .helpers import AbstractConnectionTestCase


#
# Base case
#

class EmptyPluginTestCase(AbstractConnectionTestCase):
    def test_empty_plugin(self):
        self.connection.add_event_plugin(EventPlugin, {})


#
# Simple event delegation
#

class NoticingPlugin(EventPlugin):
    def __init__(self, bot):
        self.bot = bot
        self.seen = []

    def on_privmsg(self, msg):
        self.seen.append(msg)

    on_command = on_join = on_quit = on_privmsg


class EventDelegationTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(EventDelegationTestCase, self).setUp()
        self.plugin = self.connection.add_event_plugin(
            NoticingPlugin, {'#foo': ['spam'], '#bar': []})

    def _send(self, line):
        self.connection.lineReceived(':other!user@host ' + line)

    def test_init(self):
        self.assertEqual(self.plugin.bot, self.connection)

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

    def test_visible_quit(self):
        self.connection.joined('#foo')
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
            self.connection.joined(channel)
            self.connection.channel_names[channel].add('other')
        self._send('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 1)

    def test_invisible_quit(self):
        self._send('QUIT :Client Quit')
        self.assertEqual(len(self.plugin.seen), 0)


#
# Event ordering
#

class OrderingPluginOne(EventPlugin):
    def __init__(self, bot):
        self.quote = 'dolor sit amet'

    def on_privmsg(self, msg):
        msg.connection.msg(msg.venue, self.quote)


class OrderingPluginTwo(EventPlugin):
    def __init__(self, bot):
        self.seen = []

    def on_privmsg(self, msg):
        self.seen.append(msg)
    on_privmsg.outgoing = True

    on_command = on_privmsg


class EventOrderingTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(EventOrderingTestCase, self).setUp()
        self.plugin_one = self.connection.add_event_plugin(
            OrderingPluginOne, {'#foo': []})
        self.plugin_two = self.connection.add_event_plugin(
            OrderingPluginTwo, {'#foo': ['spam']})

    def _send(self, line):
        self.connection.lineReceived(':other!user@host ' + line)

    def test_callback_ordering(self):
        """Ensure that messages generated by plugin callbacks are only
        processed after the message that triggered the callbacks."""
        self._send('PRIVMSG #foo :lorem ipsum')
        seen = self.plugin_two.seen
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0].content, 'lorem ipsum')
        self.assertEqual(seen[1].content, 'dolor sit amet')

    def test_immediate_command(self):
        """Ensure that command messages generated from privmsg messages
        are processed immediately after their originators."""
        self._send('PRIVMSG #foo :!spam')
        seen = self.plugin_two.seen
        self.assertEqual(len(seen), 3)
        self.assertEqual(seen[0].action, 'privmsg')
        self.assertEqual(seen[0].content, '!spam')
        self.assertEqual(seen[1].action, 'command')
        self.assertEqual(seen[1].subaction, 'spam')
        self.assertEqual(seen[2].action, 'privmsg')
        self.assertEqual(seen[2].content, 'dolor sit amet')


#
# Outgoing events
#

class OutgoingPlugin(NoticingPlugin):
    def on_privmsg(self, msg):
        super(OutgoingPlugin, self).on_privmsg(msg)
    on_privmsg.outgoing = True

    on_command = on_join = on_quit = on_privmsg


class OutgoingEventTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(OutgoingEventTestCase, self).setUp()
        self.outgoing = self.connection.add_event_plugin(
            OutgoingPlugin, {'#foo': ['spam']})
        self.no_outgoing = self.connection.add_event_plugin(
            NoticingPlugin, {'#foo': ['spam']})

    def _echo(self, line):
        self.connection.lineReceived(
            ':' + self.connection.nickname + '!user@host ' + line)

    def test_own_privmsg(self):
        self.connection.sendLine('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.outgoing.seen), 1)
        last_seen = self.outgoing.seen[0]
        self.assertTrue(last_seen.actor.matches(self.connection.nickname))
        self.assertEqual(last_seen.action, 'privmsg')
        self.assertEqual(last_seen.venue, '#foo')
        self.assertEqual(last_seen.content, 'lorem ipsum')
        self.assertFalse(last_seen.private)
        self.assertEqual(len(self.no_outgoing.seen), 0)

    def test_own_command(self):
        self.connection.sendLine('PRIVMSG #foo :!spam ham eggs')
        self.assertEqual(len(self.outgoing.seen), 2)
        self.assertEqual(len(self.no_outgoing.seen), 0)

    def test_own_join(self):
        self.connection.sendLine('JOIN #foo')
        self.assertEqual(len(self.outgoing.seen), 1)
        self.assertEqual(len(self.no_outgoing.seen), 0)

    def test_echoed_join(self):
        self._echo('JOIN #foo')
        self.assertEqual(len(self.outgoing.seen), 1)
        self.assertEqual(len(self.no_outgoing.seen), 1)

    def test_own_quit(self):
        self.connection.joined('#foo')
        self.connection.channel_names['#foo'].add(self.connection.nickname)
        self.connection.sendLine('QUIT :Client Quit')
        self.assertEqual(len(self.outgoing.seen), 1)
        self.assertEqual(len(self.no_outgoing.seen), 0)

    def test_echoed_quit(self):
        self.connection.joined('#foo')
        self.connection.channel_names['#foo'].add(self.connection.nickname)
        self._echo('QUIT :Client Quit')
        self.assertEqual(len(self.outgoing.seen), 1)
        self.assertEqual(len(self.no_outgoing.seen), 1)


#
# Deferred callbacks
#

class DeferredPlugin(EventPlugin):
    def __init__(self, bot):
        self.seen = []

    def on_privmsg(self, msg):
        deferred = Deferred()
        deferred.addCallback(self.seen.append)
        callLater = msg.connection.reactor.callLater
        if msg.content == 'failure':
            callLater(1, deferred.errback, Exception())
        else:
            callLater(1, deferred.callback, msg)
        return deferred


class DeferredCallbackTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(DeferredCallbackTestCase, self).setUp()
        self.plugin = self.connection.add_event_plugin(
            DeferredPlugin, {'#foo': []})

    def test_deferred_callback(self):
        deferred = self.connection.respond_to(Message.from_raw(
            self.connection, False, 'PRIVMSG #foo :lorem ipsum'))
        deferred.addCallback(
            lambda _: self.assertEqual(len(self.plugin.seen), 1))
        self.connection.reactor.advance(2)
        return deferred

    def test_default_errback(self):
        deferred = self.connection.respond_to(Message.from_raw(
            self.connection, False, 'PRIVMSG #foo :failure'))
        self.connection.reactor.advance(2)
        # <http://stackoverflow.com/a/3252306>
        gc.collect()
        self.assertEqual(len(self.flushLoggedErrors()), 1)
        return deferred
