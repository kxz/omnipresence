"""Unit tests for core connection functionality."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.words.protocols.irc import RPL_NAMREPLY, RPL_ENDOFNAMES

from .helpers import AbstractConnectionTestCase


class JoinSuspensionTestCase(AbstractConnectionTestCase):
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
        # XXX:  Maybe resumption should perform suspended joins in the
        # order they were requested, even if duplicates are present.
        self.assertEqual(self.transport.value(),
                         'JOIN #foo\r\nJOIN #foo\r\nJOIN #bar\r\n')
        self.transport.clear()
        # Same for redundant resumptions.
        self.connection.resume_joins()
        self.assertEqual(self.transport.value(), '')


class NamesCommandTestCase(AbstractConnectionTestCase):
    def test_names_command(self):
        # FIXME:  This doesn't actually directly test that the correct
        # callbacks were invoked, just side effects of their default
        # implementations.  Is this worth the effort to actually fix?
        self.connection.joined(self.connection.nickname, '#foo')
        self.assertEqual(self.connection.channel_names['#foo'],
                         frozenset())
        self.transport.clear()
        self.connection.names('#foo')
        self.assertEqual(self.transport.value(), 'NAMES #foo\r\n')
        self.connection.lineReceived(
            '{} {} = #foo :@Chanop +Voiced Normal'
            .format(RPL_NAMREPLY, self.connection.nickname))
        self.connection.lineReceived(
            '{} {} #foo :End of NAMES list'
            .format(RPL_ENDOFNAMES, self.connection.nickname))
        self.assertEqual(self.connection.channel_names['#foo'],
                         frozenset(['Chanop', 'Voiced', 'Normal']))


class NameTrackingTestCase(AbstractConnectionTestCase):
    # TODO:  Ensure case mapping works properly.

    def setUp(self):
        super(NameTrackingTestCase, self).setUp()
        self.connection.joined(self.connection.nickname, '#foo')
        self.connection.namesArrived('#foo', ['@Chanop', '+Voiced', 'Normal'])
        self.connection.joined(self.connection.nickname, '#bar')
        self.connection.namesArrived('#bar', ['@Chanop', '+Voiced'])

    def test_userRenamed(self):
        self.connection.userRenamed('Chanop', 'Chanop_')
        self.assertEqual(self.connection.channel_names['#foo'],
                         frozenset(['Chanop_', 'Voiced', 'Normal']))
        self.assertEqual(self.connection.channel_names['#bar'],
                         frozenset(['Chanop_', 'Voiced']))

    def test_userLeft(self):
        self.connection.userLeft('Normal', '#foo')
        self.assertEqual(self.connection.channel_names['#foo'],
                         frozenset(['Chanop', 'Voiced']))

    def test_userJoined(self):
        self.connection.userJoined('Normal', '#bar')
        self.assertEqual(self.connection.channel_names['#bar'],
                         frozenset(['Chanop', 'Voiced', 'Normal']))

    def test_userKicked(self):
        self.connection.userKicked('Normal', '#foo', 'Chanop', '')
        self.assertEqual(self.connection.channel_names['#foo'],
                         frozenset(['Chanop', 'Voiced']))

    def test_userQuit(self):
        self.connection.userQuit('Voiced', 'Client Quit')
        self.assertEqual(self.connection.channel_names['#foo'],
                         frozenset(['Chanop', 'Normal']))
        self.assertEqual(self.connection.channel_names['#bar'],
                         frozenset(['Chanop']))

    def test_leave(self):
        self.connection.leave('#foo')
        self.assertFalse('#foo' in self.connection.channel_names)


class PingTimeoutTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(PingTimeoutTestCase, self).setUp(sign_on=False)

    def test_signon_timeout(self):
        self.assertFalse(self.transport.disconnecting)
        self.connection.reactor.advance(self.connection.max_lag +
                                        self.connection.heartbeatInterval)
        self.assertTrue(self.transport.disconnecting)

    def test_ping_timeout(self):
        self.connection.irc_RPL_WELCOME('remote.test', [])
        self.connection.reactor.advance(self.connection.max_lag)
        self.assertFalse(self.transport.disconnecting)
        self.connection.irc_PONG('remote.test', [])
        self.connection.reactor.advance(self.connection.max_lag)
        self.assertFalse(self.transport.disconnecting)
        self.connection.reactor.advance(self.connection.heartbeatInterval)
        self.assertTrue(self.transport.disconnecting)
