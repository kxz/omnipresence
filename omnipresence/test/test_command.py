"""Integration tests for command response handling."""
# pylint: disable=missing-docstring,too-few-public-methods


from itertools import count, imap

from twisted.internet.defer import Deferred

from ..message import Message, collapse
from ..plugin import EventPlugin, UserVisibleError
from .helpers import AbstractConnectionTestCase, OutgoingPlugin


class AbstractCommandTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(AbstractCommandTestCase, self).setUp()
        self.command = self.connection.add_event_plugin(
            self.command_class, {'#foo': ['spam']})
        self.watcher = self.connection.add_event_plugin(
            OutgoingPlugin, {'#foo': []})
        self.connection.joined('#foo')

    def more(self):
        self.connection.reply_from_buffer(
            self.other_user.nick,
            Message(self.connection, False, 'command',
                    actor=self.other_user, venue='#foo',
                    subaction='more', target=self.other_user.nick),
            reply_when_empty=True)


#
# Basic commands
#

class BasicCommand(EventPlugin):
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


class BasicCommandTestCase(AbstractCommandTestCase):
    command_class = BasicCommand

    def assert_success(self, _=None):
        self.assertEqual(self.watcher.last_seen.action, 'privmsg')
        self.assertEqual(self.watcher.last_seen.venue, '#foo')
        self.assertEqual(self.watcher.last_seen.content, collapse("""
            \x0314party3: Deliquatue volut pulvinar feugiat eleifend
            quisque suspendisse faccummy etuerci; vullandigna praestie
            hac consectem ipisim esequi. Facidui augiam proin nisit
            diamet ing. Incinim iliquipisl ero alit amconsecte adionse
            loborer odionsequip sagittis, (+210 more characters)"""))
        self.more()
        self.assertEqual(self.watcher.last_seen.content, collapse("""
            \x0314{}: iuscipit hent dipiscipit. Molore proin consecte
            min amcommo; lobortio platea loboreet il consequis. Lan
            ullut corem esectem vercilisit delent exer, feu inciduipit
            feum in augait vullam. Tortor augait dignissim."""
            .format(self.other_user.nick)))

    def assert_hidden_error(self, _=None):
        self.assertEqual(self.watcher.last_seen.action, 'privmsg')
        self.assertEqual(self.watcher.last_seen.venue, '#foo')
        self.assertEqual(self.watcher.last_seen.content, collapse("""
            \x0314{}: Command \x02spam\x02 encountered an error."""
            .format(self.other_user.nick)))
        self.assertLoggedErrors(1)

    def assert_visible_error(self, _=None):
        self.assertEqual(self.watcher.last_seen.action, 'privmsg')
        self.assertEqual(self.watcher.last_seen.venue, '#foo')
        self.assertEqual(self.watcher.last_seen.content, collapse("""
            \x0314{}: Command \x02spam\x02 encountered an error: lorem
            ipsum.""".format(self.other_user.nick)))

    def test_empty_buffer(self):
        self.more()
        self.assertEqual(self.watcher.last_seen.action, 'privmsg')
        self.assertEqual(self.watcher.last_seen.venue, '#foo')
        self.assertEqual(self.watcher.last_seen.content, collapse("""
            \x0314{}: No text in buffer.""".format(self.other_user.nick)))

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
        self.receive('PRIVMSG #foo :!spam defer > party3')
        self.connection.reactor.advance(2)
        self.assert_success()

    def test_deferred_hidden_error(self):
        self.receive('PRIVMSG #foo :!spam defer failure > party3')
        self.connection.reactor.advance(2)
        self.assert_hidden_error()

    def test_deferred_visible_error(self):
        self.receive('PRIVMSG #foo :!spam defer failure visible > party3')
        self.connection.reactor.advance(2)
        self.assert_visible_error()


#
# Commands returning iterators
#

class DeferredIterator(object):
    def __init__(self, maximum, callLater, raise_on):
        self.count = 0
        self.maximum = maximum
        self.callLater = callLater
        self.raise_on = raise_on

    def __iter__(self):
        return self

    def next(self):
        if self.count >= self.maximum:
            raise StopIteration
        deferred = Deferred()
        if self.count == self.raise_on:
            self.callLater(1, deferred.errback, Exception())
        else:
            self.callLater(1, deferred.callback, str(self.count))
        self.count += 1
        return deferred


class IteratorCommand(EventPlugin):
    def on_command(self, msg):
        args = msg.content.split()
        if args and args[0] == 'defer':
            return DeferredIterator(2, msg.connection.reactor.callLater,
                                    raise_on=int(''.join(args[1:]) or -1))
        return imap(str, xrange(2))


class IteratorCommandTestCase(AbstractCommandTestCase):
    command_class = IteratorCommand

    def test_synchronous(self):
        self.receive('PRIVMSG #foo :!spam > party3')
        self.assertEqual(self.watcher.last_seen.action, 'privmsg')
        self.assertEqual(self.watcher.last_seen.venue, '#foo')
        self.assertEqual(self.watcher.last_seen.content,
                         '\x0314party3: 0')
        self.more()
        self.assertEqual(self.watcher.last_seen.content,
                         '\x0314{}: 1'.format(self.other_user.nick))
        self.more()
        self.assertEqual(self.watcher.last_seen.content,
                         '\x0314{}: No text in buffer.'
                         .format(self.other_user.nick))


    def test_deferred(self):
        self.receive('PRIVMSG #foo :!spam defer > party3')
        self.connection.reactor.advance(2)
        self.assertEqual(self.watcher.last_seen.action, 'privmsg')
        self.assertEqual(self.watcher.last_seen.venue, '#foo')
        self.assertEqual(self.watcher.last_seen.content,
                         '\x0314party3: 0')
        self.more()
        self.connection.reactor.advance(2)
        self.assertEqual(self.watcher.last_seen.content,
                         '\x0314{}: 1'.format(self.other_user.nick))
        self.more()
        self.connection.reactor.advance(2)
        self.assertEqual(self.watcher.last_seen.content,
                         '\x0314{}: No text in buffer.'
                         .format(self.other_user.nick))


    def test_deferred_error(self):
        self.receive('PRIVMSG #foo :!spam defer 1 > party3')
        self.connection.reactor.advance(2)
        self.assertEqual(self.watcher.last_seen.action, 'privmsg')
        self.assertEqual(self.watcher.last_seen.venue, '#foo')
        self.assertEqual(self.watcher.last_seen.content,
                         '\x0314party3: 0')
        self.more()
        self.connection.reactor.advance(2)
        self.assertEqual(self.watcher.last_seen.content, collapse("""
            \x0314{}: Command \x02more\x02 encountered an error."""
            .format(self.other_user.nick)))
        self.more()
        self.connection.reactor.advance(2)
        self.assertEqual(self.watcher.last_seen.content,
                         '\x0314{}: No text in buffer.'
                         .format(self.other_user.nick))
        self.assertLoggedErrors(1)
