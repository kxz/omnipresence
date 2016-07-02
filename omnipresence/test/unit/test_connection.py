"""Unit tests for core connection functionality."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase
from twisted.web.test.test_agent import AbortableStringTransport
from twisted.words.protocols.irc import RPL_NAMREPLY, RPL_ENDOFNAMES

from ...connection import Connection, ConnectionFactory
from ...settings import ConnectionSettings
from ..helpers import ConnectionTestMixin, NoticingPlugin


class JoinSuspensionTestCase(ConnectionTestMixin, TestCase):
    def test_join_suspension(self):
        self.transport.clear()
        self.connection.join('#foo')
        self.assertEqual(self.transport.value(), 'JOIN #foo\r\n')
        self.transport.clear()
        self.connection.suspend_joins()
        self.connection.join('#foo')
        # Ensure that redundant suspensions cause no harm.
        self.connection.suspend_joins()
        self.connection.join('#foo')
        self.connection.join('#bar')
        self.assertEqual(self.transport.value(), '')
        self.connection.resume_joins()
        self.assertEqual(self.transport.value(),
                         'JOIN #foo\r\nJOIN #foo\r\nJOIN #bar\r\n')
        self.transport.clear()
        # Same for redundant resumptions.
        self.connection.resume_joins()
        self.assertEqual(self.transport.value(), '')


class NamesCommandTestCase(ConnectionTestMixin, TestCase):
    def test_names_command(self):
        # FIXME:  This doesn't actually directly test that the correct
        # callbacks were invoked, just side effects of their default
        # implementations.  Is this worth the effort to actually fix?
        self.connection.joined('#foo')
        self.assertItemsEqual(self.connection.venues['#foo'].nicks.keys(), [])
        self.transport.clear()
        self.connection.lineReceived(
            '{} {} = #foo :@Chanop +Voiced Normal'
            .format(RPL_NAMREPLY, self.connection.nickname))
        self.connection.lineReceived(
            '{} {} #foo :End of NAMES list'
            .format(RPL_ENDOFNAMES, self.connection.nickname))
        self.assertItemsEqual(self.connection.venues['#foo'].nicks.keys(),
                              ['Chanop', 'Voiced', 'Normal'])


class NameTrackingTestCase(ConnectionTestMixin, TestCase):
    # TODO:  Ensure case mapping works properly.

    def setUp(self):
        super(NameTrackingTestCase, self).setUp()
        self.connection.joined('#foo')
        self.connection.names_arrived('#foo', ['@Chanop', '+Voiced', 'Normal'])
        self.connection.joined('#bar')
        self.connection.names_arrived('#bar', ['@Chanop', '+Voiced'])

    def test_userRenamed(self):
        self.connection.userRenamed('Chanop', 'Chanop_')
        self.assertItemsEqual(self.connection.venues['#foo'].nicks.keys(),
                              ['Chanop_', 'Voiced', 'Normal'])
        self.assertItemsEqual(self.connection.venues['#bar'].nicks.keys(),
                              ['Chanop_', 'Voiced'])

    def test_userLeft(self):
        self.connection.userLeft('Normal', '#foo')
        self.assertItemsEqual(self.connection.venues['#foo'].nicks.keys(),
                              ['Chanop', 'Voiced'])

    def test_userJoined(self):
        self.connection.userJoined('Normal', '#bar')
        self.assertItemsEqual(self.connection.venues['#bar'].nicks.keys(),
                              ['Chanop', 'Voiced', 'Normal'])

    def test_userKicked(self):
        self.connection.userKicked('Normal', '#foo', 'Chanop', '')
        self.assertItemsEqual(self.connection.venues['#foo'].nicks.keys(),
                              ['Chanop', 'Voiced'])

    def test_userQuit(self):
        self.connection.userQuit('Voiced', 'Client Quit')
        self.assertItemsEqual(self.connection.venues['#foo'].nicks.keys(),
                              ['Chanop', 'Normal'])
        self.assertItemsEqual(self.connection.venues['#bar'].nicks.keys(),
                              ['Chanop'])

    def test_left(self):
        self.connection.left('#foo')
        self.assertFalse('#foo' in self.connection.venues)


class PingTimeoutTestCase(ConnectionTestMixin, TestCase):
    sign_on = False

    def test_signon_timeout(self):
        self.assertFalse(self.transport.disconnecting)
        self.connection.reactor.advance(self.connection.max_lag +
                                        self.connection.heartbeatInterval)
        self.assertTrue(self.transport.disconnecting)

    def test_ping_timeout(self):
        # Twisted's IRCClient starts the heartbeat in irc_RPL_WELCOME,
        # not signedOn.
        self.connection.irc_RPL_WELCOME('remote.test', [])
        self.connection.reactor.advance(self.connection.max_lag)
        self.assertFalse(self.transport.disconnecting)
        self.connection.irc_PONG('remote.test', [])
        self.connection.reactor.advance(self.connection.max_lag)
        self.assertFalse(self.transport.disconnecting)
        self.connection.reactor.advance(self.connection.heartbeatInterval)
        self.assertTrue(self.transport.disconnecting)


class SettingsReloadingTestCase(TestCase):
    def setUp(self):
        self.transport = AbortableStringTransport()
        self.factory = ConnectionFactory()
        self.factory.settings = ConnectionSettings({
            'channel #foo': {'enabled': True},
            'plugin {}'.format(NoticingPlugin.name): True})
        self.connection = self.factory.buildProtocol(None)
        self.connection.reactor = Clock()
        self.connection.makeConnection(self.transport)
        self.connection.irc_RPL_WELCOME('irc.server.test', [])
        self.connection.joined('#foo')

    def test_joins_and_parts(self):
        self.connection.joined('#bar')
        self.transport.clear()
        self.factory.reload_settings({
            'channel #foo': {'enabled': False},
            'channel #bar': {'enabled': 'soft'},
            'channel #baz': {'enabled': 'soft'},
            'channel #quux': {'enabled': True}})
        self.assertItemsEqual(self.transport.value().splitlines(),
                              ['PART #foo', 'JOIN #quux'])

    def test_plugin_identity(self):
        old_plugin = self.factory.settings.active_plugins().keys()[0]
        self.factory.reload_settings({
            'channel #foo': {'enabled': True},
            'plugin {}'.format(NoticingPlugin.name): True})
        new_plugin = self.factory.settings.active_plugins().keys()[0]
        self.assertIs(old_plugin, new_plugin)
