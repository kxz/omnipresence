"""Integration tests for event delegation."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks, succeed, fail

from ..connection import PRIVATE_CHANNEL
from ..plugin import EventPlugin
from .helpers import (AbstractConnectionTestCase,
                      NoticingPlugin, OutgoingPlugin)


#
# Base case
#

class EmptyPluginTestCase(AbstractConnectionTestCase):
    def test_empty_plugin(self):
        self.connection.add_event_plugin(EventPlugin, {})


#
# Simple event delegation
#

class EventDelegationTestCase(AbstractConnectionTestCase):
    sign_on = False

    def setUp(self):
        super(EventDelegationTestCase, self).setUp()
        self.one = self.connection.add_event_plugin(
            NoticingPlugin,
            {PRIVATE_CHANNEL: ['spam'], '#foo': ['spam'], '#bar': []})
        # We would normally never instantiate two instances of the same
        # event plugin class, but this is the easiest way to test the
        # delegation of events that have no actor or venue.
        self.two = self.connection.add_event_plugin(
            NoticingPlugin, {'#baz': []})
        self.connection.joined('#foo')

    def test_init(self):
        self.assertEqual(self.one.bot, self.connection)

    def test_connected(self):
        self.connection.signedOn()
        self.assertEqual(len(self.two.seen), 1)
        self.assertEqual(self.two.last_seen.action, 'connected')
        self.assertIsNone(self.two.last_seen.actor)
        self.assertIsNone(self.two.last_seen.venue)
        self.assertIsNone(self.two.last_seen.content)
        self.assertFalse(self.two.last_seen.private)

    def test_disconnected(self):
        self.connection.connectionLost(None)
        self.assertEqual(len(self.two.seen), 1)
        self.assertEqual(self.two.last_seen.action, 'disconnected')
        self.assertIsNone(self.two.last_seen.actor)
        self.assertIsNone(self.two.last_seen.venue)
        self.assertIsNone(self.two.last_seen.content)
        self.assertFalse(self.two.last_seen.private)

    def test_privmsg(self):
        self.receive('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.one.seen), 1)
        self.assertEqual(self.one.last_seen.action, 'privmsg')
        self.assertEqual(self.one.last_seen.actor, self.other_user)
        self.assertEqual(self.one.last_seen.venue, '#foo')
        self.assertEqual(self.one.last_seen.content, 'lorem ipsum')
        self.assertFalse(self.one.last_seen.private)

    def test_privmsg_user(self):
        self.receive('PRIVMSG {} :lorem ipsum'.format(
            self.connection.nickname))
        self.assertEqual(len(self.one.seen), 1)
        self.assertEqual(self.one.last_seen.action, 'privmsg')
        self.assertEqual(self.one.last_seen.actor, self.other_user)
        self.assertEqual(self.one.last_seen.venue, self.connection.nickname)
        self.assertEqual(self.one.last_seen.content, 'lorem ipsum')
        self.assertTrue(self.one.last_seen.private)

    def test_privmsg_casemapping(self):
        # This will no longer be a direct part of the event delegation
        # code once the new settings machinery works, but it might not
        # be a bad idea to keep this around as an integration test with
        # various settings for the case mapping.
        self.receive('PRIVMSG #FOO :lorem ipsum')
        self.assertEqual(len(self.one.seen), 1)
        self.assertEqual(self.one.last_seen.action, 'privmsg')
        self.assertEqual(self.one.last_seen.actor, self.other_user)
        self.assertEqual(self.one.last_seen.venue, '#FOO')
        self.assertEqual(self.one.last_seen.content, 'lorem ipsum')
        self.assertFalse(self.one.last_seen.private)

    def test_command_enabled(self):
        self.receive('PRIVMSG #foo :!spam ham eggs')
        self.assertEqual(len(self.one.seen), 2)
        self.assertEqual(self.one.last_seen.action, 'command')
        self.assertEqual(self.one.last_seen.actor, self.other_user)
        self.assertEqual(self.one.last_seen.venue, '#foo')
        self.assertEqual(self.one.last_seen.target, 'other')
        self.assertEqual(self.one.last_seen.subaction, 'spam')
        self.assertEqual(self.one.last_seen.content, 'ham eggs')
        self.assertFalse(self.one.last_seen.private)

    def test_command_disabled(self):
        self.receive('PRIVMSG #bar :!spam ham eggs')
        self.assertEqual(len(self.one.seen), 1)  # no command message

    def test_visible_quit(self):
        self.connection.joined('#foo')
        self.connection.channel_names['#foo'].add(self.other_user.nick)
        self.receive('QUIT :Client Quit')
        self.assertEqual(len(self.one.seen), 1)
        self.assertEqual(self.one.last_seen.action, 'quit')
        self.assertEqual(self.one.last_seen.actor, self.other_user)
        self.assertIsNone(self.one.last_seen.venue)
        self.assertEqual(self.one.last_seen.content, 'Client Quit')
        self.assertFalse(self.one.last_seen.private)

    def test_visible_quit_call_once(self):
        for channel in ('#foo', '#bar'):
            self.connection.joined(channel)
            self.connection.channel_names[channel].add(self.other_user.nick)
        self.receive('QUIT :Client Quit')
        self.assertEqual(len(self.one.seen), 1)

    def test_invisible_quit(self):
        self.receive('QUIT :Client Quit')
        self.assertEqual(len(self.one.seen), 0)


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
        self.one = self.connection.add_event_plugin(
            OrderingPluginOne, {'#foo': []})
        self.two = self.connection.add_event_plugin(
            OrderingPluginTwo, {'#foo': ['spam']})
        self.connection.joined('#foo')

    def test_callback_ordering(self):
        """Ensure that messages generated by plugin callbacks are only
        processed after the message that triggered the callbacks."""
        self.receive('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.two.seen), 2)
        self.assertEqual(self.two.seen[0].content, 'lorem ipsum')
        self.assertEqual(self.two.seen[1].content, 'dolor sit amet')

    def test_immediate_command(self):
        """Ensure that command messages generated from privmsg messages
        are processed immediately after their originators."""
        self.receive('PRIVMSG #foo :!spam')
        self.assertEqual(len(self.two.seen), 3)
        self.assertEqual(self.two.seen[0].action, 'privmsg')
        self.assertEqual(self.two.seen[0].content, '!spam')
        self.assertEqual(self.two.seen[1].action, 'command')
        self.assertEqual(self.two.seen[1].subaction, 'spam')
        self.assertEqual(self.two.seen[2].action, 'privmsg')
        self.assertEqual(self.two.seen[2].content, 'dolor sit amet')


#
# Outgoing events
#

class OutgoingEventTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(OutgoingEventTestCase, self).setUp()
        self.outgoing = self.connection.add_event_plugin(
            OutgoingPlugin, {'#foo': ['spam']})
        self.no_outgoing = self.connection.add_event_plugin(
            NoticingPlugin, {'#foo': ['spam']})
        self.connection.joined('#foo')

    def test_own_privmsg(self):
        self.connection.sendLine('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.outgoing.seen), 1)
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertTrue(self.outgoing.last_seen.actor.matches(
            self.connection.nickname))
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content, 'lorem ipsum')
        self.assertFalse(self.outgoing.last_seen.private)
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
        self.echo('JOIN #foo')
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
        self.echo('QUIT :Client Quit')
        self.assertEqual(len(self.outgoing.seen), 1)
        self.assertEqual(len(self.no_outgoing.seen), 1)


#
# Deferred callbacks
#

class DeferredPlugin(EventPlugin):
    def __init__(self, bot):
        self.seen = []

    def on_privmsg(self, msg):
        if msg.content == 'failure':
            return fail(Exception())
        self.seen.append(msg)
        return succeed(None)


class DeferredCallbackTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(DeferredCallbackTestCase, self).setUp()
        self.plugin = self.connection.add_event_plugin(
            DeferredPlugin, {'#foo': []})

    @inlineCallbacks
    def test_deferred_callback(self):
        yield self.receive('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.plugin.seen), 1)

    @inlineCallbacks
    def test_default_errback(self):
        yield self.receive('PRIVMSG #foo :failure')
        self.assertLoggedErrors(1)
