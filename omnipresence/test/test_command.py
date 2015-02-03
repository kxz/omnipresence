"""Unit tests for command response handling."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import Deferred

from ..message import collapse
from ..plugin import EventPlugin, UserVisibleError
from .helpers import AbstractConnectionTestCase
from .test_event import OutgoingPlugin


class CommandTestDummy(EventPlugin):
    quote = collapse("""Deliquatue volut pulvinar feugiat eleifend
        quisque suspendisse faccummy etuerci; vullandigna praestie hac
        consectem ipisim esequi. Facidui augiam proin nisit diamet ing.
        Incinim iliquipisl ero alit amconsecte adionse loborer
        odionsequip sagittis, iuscipit hent dipiscipit. Molore proin
        consecte min amcommo; lobortio platea loboreet il consequis. Lan
        ullut corem esectem vercilisit delent exer, feu inciduipit feum
        in augait vullam. Tortor augait dignissim.""")

    def on_command(self, msg):
        args = msg.content.split()
        exc = (UserVisibleError if 'visible' in args else Exception)(
            'lorem ipsum')
        if 'defer' in args:
            deferred = Deferred()
            deferred.addCallback(lambda _: self.quote)
            callLater = msg.connection.reactor.callLater
            if 'failure' in args:
                callLater(1, deferred.errback, exc)
            else:
                callLater(1, deferred.callback, msg)
            return deferred
        if 'failure' in args:
            raise exc
        return self.quote


class CommandReplyTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(CommandReplyTestCase, self).setUp()
        self.command = self.connection.add_event_plugin(
            CommandTestDummy, {'#foo': ['spam']})
        self.watcher = self.connection.add_event_plugin(
            OutgoingPlugin, {'#foo': []})
        self.connection.joined('#foo')

    def assert_success(self, _=None):
        last_seen = self.watcher.seen[-1]
        self.assertEqual(last_seen.action, 'privmsg')
        self.assertEqual(last_seen.venue, '#foo')
        self.assertEqual(last_seen.content, collapse("""\x0314party3:
            Deliquatue volut pulvinar feugiat eleifend quisque
            suspendisse faccummy etuerci; vullandigna praestie hac
            consectem ipisim esequi. Facidui augiam proin nisit diamet
            ing. Incinim iliquipisl ero alit amconsecte adionse loborer
            odionsequip sagittis, (+210 more characters)"""))
        rb = self.connection.message_buffers['#foo'][self.other_user.nick]
        self.assertEqual(next(rb), collapse("""iuscipit hent dipiscipit.
            Molore proin consecte min amcommo; lobortio platea loboreet
            il consequis. Lan ullut corem esectem vercilisit delent
            exer, feu inciduipit feum in augait vullam. Tortor augait
            dignissim."""))

    def assert_hidden_error(self, _=None):
        last_seen = self.watcher.seen[-1]
        self.assertEqual(last_seen.action, 'privmsg')
        self.assertEqual(last_seen.venue, '#foo')
        self.assertEqual(last_seen.content, collapse("""\x0314{}:
            Command \x02spam\x02 encountered an error.""".format(
                self.other_user.nick)))
        self.assertLoggedErrors(1)

    def assert_visible_error(self, _=None):
        last_seen = self.watcher.seen[-1]
        self.assertEqual(last_seen.action, 'privmsg')
        self.assertEqual(last_seen.venue, '#foo')
        self.assertEqual(last_seen.content, collapse("""\x0314{}:
            Command \x02spam\x02 encountered an error: lorem
            ipsum.""".format(self.other_user.nick)))

    def test_synchronous_success(self):
        self.receive('PRIVMSG #foo :!spam > party3')
        self.assert_success()

    def test_synchronous_hidden_error(self):
        self.receive('PRIVMSG #foo :!spam failure > party3')
        self.assert_hidden_error()

    def test_synchronous_visible_error(self):
        self.receive('PRIVMSG #foo :!spam failure visible > party3')
        self.assert_visible_error()

    def test_deferred_success(self):
        deferred = self.receive('PRIVMSG #foo :!spam defer > party3')
        deferred.addCallback(self.assert_success)
        self.connection.reactor.advance(2)
        return deferred

    def test_deferred_hidden_error(self):
        deferred = self.receive('PRIVMSG #foo :!spam defer failure > party3')
        deferred.addCallback(self.assert_hidden_error)
        self.connection.reactor.advance(2)
        return deferred

    def test_deferred_visible_error(self):
        deferred = self.receive(
            'PRIVMSG #foo :!spam defer failure visible > party3')
        deferred.addCallback(self.assert_visible_error)
        self.connection.reactor.advance(2)
        return deferred
