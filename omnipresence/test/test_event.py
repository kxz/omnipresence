"""Integration tests for event delegation."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks, succeed, fail

from ..plugin import EventPlugin
from .helpers import (AbstractConnectionTestCase,
                      NoticingPlugin, OutgoingPlugin)


#
# Base case
#

class EmptyPluginTestCase(AbstractConnectionTestCase):
    def test_empty_plugin(self):
        self.connection.settings.enable(EventPlugin.name)


#
# Simple event delegation
#

class EventDelegationTestCase(AbstractConnectionTestCase):
    sign_on = False

    def setUp(self):
        super(EventDelegationTestCase, self).setUp()
        self.noticing = self.connection.settings.enable(NoticingPlugin.name)
        self.connection.settings.enable(
            NoticingPlugin.name, ['spam'], scope='#foo')
        self.connection.joined('#foo')

    def test_connected(self):
        self.connection.signedOn()
        self.assertEqual(len(self.noticing.seen), 1)
        self.assertEqual(self.noticing.last_seen.action, 'connected')
        self.assertIsNone(self.noticing.last_seen.actor)
        self.assertIsNone(self.noticing.last_seen.venue)
        self.assertIsNone(self.noticing.last_seen.content)
        self.assertFalse(self.noticing.last_seen.private)

    def test_disconnected(self):
        self.connection.connectionLost(None)
        self.assertEqual(len(self.noticing.seen), 1)
        self.assertEqual(self.noticing.last_seen.action, 'disconnected')
        self.assertIsNone(self.noticing.last_seen.actor)
        self.assertIsNone(self.noticing.last_seen.venue)
        self.assertIsNone(self.noticing.last_seen.content)
        self.assertFalse(self.noticing.last_seen.private)

    def test_privmsg(self):
        self.receive('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.noticing.seen), 1)
        self.assertEqual(self.noticing.last_seen.action, 'privmsg')
        self.assertEqual(self.noticing.last_seen.actor, self.other_user)
        self.assertEqual(self.noticing.last_seen.venue, '#foo')
        self.assertEqual(self.noticing.last_seen.content, 'lorem ipsum')
        self.assertFalse(self.noticing.last_seen.private)

    def test_privmsg_user(self):
        self.receive('PRIVMSG {} :lorem ipsum'.format(
            self.connection.nickname))
        self.assertEqual(len(self.noticing.seen), 1)
        self.assertEqual(self.noticing.last_seen.action, 'privmsg')
        self.assertEqual(self.noticing.last_seen.actor, self.other_user)
        self.assertEqual(self.noticing.last_seen.venue,
                         self.connection.nickname)
        self.assertEqual(self.noticing.last_seen.content, 'lorem ipsum')
        self.assertTrue(self.noticing.last_seen.private)

    def test_privmsg_casemapping(self):
        # This will no longer be a direct part of the event delegation
        # code once the new settings machinery works, but it might not
        # be a bad idea to keep this around as an integration test with
        # various settings for the case mapping.
        self.receive('PRIVMSG #FOO :lorem ipsum')
        self.assertEqual(len(self.noticing.seen), 1)
        self.assertEqual(self.noticing.last_seen.action, 'privmsg')
        self.assertEqual(self.noticing.last_seen.actor, self.other_user)
        self.assertEqual(self.noticing.last_seen.venue, '#FOO')
        self.assertEqual(self.noticing.last_seen.content, 'lorem ipsum')
        self.assertFalse(self.noticing.last_seen.private)

    def test_command_enabled(self):
        self.receive('PRIVMSG #foo :!spam ham eggs')
        self.assertEqual(len(self.noticing.seen), 2)
        self.assertEqual(self.noticing.last_seen.action, 'command')
        self.assertEqual(self.noticing.last_seen.actor, self.other_user)
        self.assertEqual(self.noticing.last_seen.venue, '#foo')
        self.assertEqual(self.noticing.last_seen.target, self.other_user.nick)
        self.assertEqual(self.noticing.last_seen.subaction, 'spam')
        self.assertEqual(self.noticing.last_seen.content, 'ham eggs')
        self.assertFalse(self.noticing.last_seen.private)

    def test_command_disabled(self):
        self.receive('PRIVMSG #bar :!spam ham eggs')
        self.assertEqual(len(self.noticing.seen), 1)  # no command

    def test_visible_quit(self):
        self.connection.joined('#foo')
        self.connection.channel_names['#foo'].add(self.other_user.nick)
        self.receive('QUIT :Client Quit')
        self.assertEqual(len(self.noticing.seen), 1)
        self.assertEqual(self.noticing.last_seen.action, 'quit')
        self.assertEqual(self.noticing.last_seen.actor, self.other_user)
        self.assertIsNone(self.noticing.last_seen.venue)
        self.assertEqual(self.noticing.last_seen.content, 'Client Quit')
        self.assertFalse(self.noticing.last_seen.private)

    def test_visible_quit_call_once(self):
        for channel in ('#foo', '#bar'):
            self.connection.joined(channel)
            self.connection.channel_names[channel].add(self.other_user.nick)
        self.receive('QUIT :Client Quit')
        self.assertEqual(len(self.noticing.seen), 1)

    def test_invisible_quit(self):
        self.receive('QUIT :Client Quit')
        self.assertEqual(len(self.noticing.seen), 0)


#
# Event ordering
#

class OrderingPluginOne(EventPlugin):
    def __init__(self):
        self.quote = 'dolor sit amet'

    def on_privmsg(self, msg):
        msg.connection.msg(msg.venue, self.quote)


class OrderingPluginTwo(EventPlugin):
    def __init__(self):
        self.seen = []

    def on_privmsg(self, msg):
        self.seen.append(msg)
    on_privmsg.outgoing = True

    on_command = on_privmsg


class EventOrderingTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(EventOrderingTestCase, self).setUp()
        self.one = self.connection.settings.enable(OrderingPluginOne.name)
        self.two = self.connection.settings.enable(OrderingPluginTwo.name,
                                                   ['spam'])
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
        self.connection.settings.set('command_prefixes', ['!'])
        self.outgoing = self.connection.settings.enable(
            OutgoingPlugin.name, ['spam'])
        self.no_outgoing = self.connection.settings.enable(
            NoticingPlugin.name, ['spam'])
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
    def __init__(self):
        self.seen = []

    def on_privmsg(self, msg):
        if msg.content == 'failure':
            return fail(Exception())
        self.seen.append(msg)
        return succeed(None)


class DeferredCallbackTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(DeferredCallbackTestCase, self).setUp()
        self.plugin = self.connection.settings.enable(DeferredPlugin.name)

    @inlineCallbacks
    def test_deferred_callback(self):
        yield self.receive('PRIVMSG #foo :lorem ipsum')
        self.assertEqual(len(self.plugin.seen), 1)

    @inlineCallbacks
    def test_default_errback(self):
        yield self.receive('PRIVMSG #foo :failure')
        self.assertLoggedErrors(1)
