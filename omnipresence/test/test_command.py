# -*- coding: utf-8
"""Integration tests for command response handling."""
# pylint: disable=missing-docstring,too-few-public-methods


from itertools import count, imap, repeat
from textwrap import dedent

from twisted.internet.defer import inlineCallbacks, fail, succeed

from ..connection import PRIVATE_CHANNEL
from ..message import Message, collapse
from ..plugin import EventPlugin, UserVisibleError
from .helpers import (AbstractConnectionTestCase, AbstractCommandTestCase,
                      OutgoingPlugin)


class AbstractCommandMonitor(AbstractCommandTestCase):
    def setUp(self):
        super(AbstractCommandMonitor, self).setUp()
        self.connection.settings.set('command_prefixes', ['!'])
        self.outgoing = self.connection.settings.enable(
            OutgoingPlugin.name, [])
        self.connection.joined('#foo')

    def more(self, **kwargs):
        return self.connection.reply_from_buffer(
            self.command_message(
                '', subaction='more', target=self.other_user.nick, **kwargs),
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
        exc_class = UserVisibleError if 'visible' in args else Exception
        exc = exc_class('Lorem ipsum.')
        if 'defer' in args:
            if 'failure' in args:
                return fail(exc)
            return succeed(self.quote)
        if 'failure' in args:
            raise exc
        return self.quote


class BasicCommandTestCase(AbstractCommandMonitor):
    command_class = BasicCommand

    def assert_success(self, deferred_result=None):
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content, collapse("""
            \x0314party3: Deliquatue volut pulvinar feugiat eleifend
            quisque suspendisse faccummy etuerci; vullandigna praestie
            hac consectem ipisim esequi. Facidui augiam proin nisit
            diamet ing. Incinim iliquipisl ero alit amconsecte adionse
            loborer odionsequip sagittis, (+210 more characters)"""))
        self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.content, collapse("""
            \x0314{}: iuscipit hent dipiscipit. Molore proin consecte
            min amcommo; lobortio platea loboreet il consequis. Lan
            ullut corem esectem vercilisit delent exer, feu inciduipit
            feum in augait vullam. Tortor augait dignissim."""
            .format(self.other_user.nick)))

    def assert_hidden_error(self, deferred_result=None):
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content, collapse("""
            \x0314{}: Command \x02basiccommand\x02 encountered an error.
            """.format(self.other_user.nick)))
        self.assertLoggedErrors(1)

    def assert_visible_error(self, deferred_result=None):
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content, collapse("""
            \x0314{}: Lorem ipsum.""".format(self.other_user.nick)))

    def test_empty_buffer(self):
        self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content, collapse("""
            \x0314{}: No text in buffer.""".format(self.other_user.nick)))

    def test_synchronous_success(self):
        self.receive('PRIVMSG #foo :!basiccommand > party3')
        self.assert_success()

    def test_synchronous_success_private(self):
        self.receive('PRIVMSG {} :basiccommand > party3'.format(
            self.connection.nickname))
        self.assertEqual(self.outgoing.last_seen.action, 'notice')
        self.assertEqual(self.outgoing.last_seen.venue, self.other_user.nick)
        self.assertEqual(self.outgoing.last_seen.content, collapse("""
            Deliquatue volut pulvinar feugiat eleifend quisque
            suspendisse faccummy etuerci; vullandigna praestie hac
            consectem ipisim esequi. Facidui augiam proin nisit diamet
            ing. Incinim iliquipisl ero alit amconsecte adionse loborer
            odionsequip sagittis, (+210 more characters)"""))
        self.more(venue=self.connection.nickname)
        self.assertEqual(self.outgoing.last_seen.content, collapse("""
            iuscipit hent dipiscipit. Molore proin consecte min amcommo;
            lobortio platea loboreet il consequis. Lan ullut corem
            esectem vercilisit delent exer, feu inciduipit feum in
            augait vullam. Tortor augait dignissim."""))

    def test_synchronous_hidden_error(self):
        self.receive('PRIVMSG #foo :!basiccommand failure > party3')
        self.assert_hidden_error()

    def test_synchronous_visible_error(self):
        self.receive('PRIVMSG #foo :!basiccommand failure visible > party3')
        self.assert_visible_error()

    def test_deferred_success(self):
        d = self.receive('PRIVMSG #foo :!basiccommand defer > party3')
        d.addCallback(self.assert_success)
        return d

    def test_deferred_hidden_error(self):
        d = self.receive('PRIVMSG #foo :!basiccommand defer failure > party3')
        d.addCallback(self.assert_hidden_error)
        return d

    def test_deferred_visible_error(self):
        d = self.receive(
            'PRIVMSG #foo :!basiccommand defer failure visible > party3')
        d.addCallback(self.assert_visible_error)
        return d


#
# Commands returning iterators
#

class DeferredIterator(object):
    def __init__(self, maximum, raise_on):
        self.count = -1
        self.maximum = maximum
        self.raise_on = raise_on

    def __iter__(self):
        return self

    def next(self):
        self.count += 1
        if self.count >= self.maximum:
            raise StopIteration
        if self.count == self.raise_on:
            return fail(Exception())
        return succeed(str(self.count))


class IteratorCommand(EventPlugin):
    def on_command(self, msg):
        args = msg.content.split()
        if args and args[0] == 'defer':
            return DeferredIterator(2, raise_on=int(''.join(args[1:]) or -2))
        return imap(str, xrange(2))


class IteratorCommandTestCase(AbstractCommandMonitor):
    command_class = IteratorCommand

    def test_synchronous(self):
        self.receive('PRIVMSG #foo :!iteratorcommand > party3')
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314party3: 0')
        self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314{}: 1'.format(self.other_user.nick))
        self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314{}: No text in buffer.'
                         .format(self.other_user.nick))

    @inlineCallbacks
    def test_deferred(self):
        yield self.receive('PRIVMSG #foo :!iteratorcommand defer > party3')
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314party3: 0')
        yield self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314{}: 1'.format(self.other_user.nick))
        yield self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314{}: No text in buffer.'
                         .format(self.other_user.nick))

    @inlineCallbacks
    def test_deferred_error(self):
        yield self.receive('PRIVMSG #foo :!iteratorcommand defer 1 > party3')
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314party3: 0')
        yield self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.content, collapse("""
            \x0314{}: Command \x02more\x02 encountered an error."""
            .format(self.other_user.nick)))
        yield self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314{}: No text in buffer.'
                         .format(self.other_user.nick))
        self.assertLoggedErrors(1)


#
# Unicode replies
#

class UnicodeCommand(EventPlugin):
    def on_command(self, msg):
        return [u'☃'] * 2


class UnicodeReplyTestCase(AbstractCommandMonitor):
    command_class = UnicodeCommand

    @inlineCallbacks
    def test_synchronous(self):
        self.receive('PRIVMSG #foo :!unicodecommand')
        self.assertEqual(self.outgoing.last_seen.action, 'privmsg')
        self.assertEqual(self.outgoing.last_seen.venue, '#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314{}: \xe2\x98\x83 (+1 more characters)'
                         .format(self.other_user.nick))
        yield self.more(venue='#foo')
        self.assertEqual(self.outgoing.last_seen.content,
                         '\x0314{}: \xe2\x98\x83'.format(self.other_user.nick))


#
# Individual reply truncation
#

class ReplyTruncationTestCase(AbstractConnectionTestCase):
    def setUp(self):
        super(ReplyTruncationTestCase, self).setUp()
        self.outgoing = self.connection.settings.enable(OutgoingPlugin.name)
        self.request = Message(self.connection, False, 'command',
            actor=self.other_user, subaction='spam',
            venue=self.connection.nickname, target=self.other_user.nick)

    def test_str(self):
        self.connection.reply(collapse("""\
            Iliquat dictum patin rilit aciduipis, sectem nummolorem
            esequat. Alisis nummolorem ros quatuer iuscing iure nonsequ,
            ad commy congue, faccummy aut esequat quisi. Eugiam velis
            odipsumsan ate a sismolore. Magniat vero sociosqu, mauris
            quamconsequi irilit urna niscidu consequis, magniamet
            aciduipis utet. Justo consequipis os, dolummy tempor nulla
            vel corem adignim, sociis ate verostin."""), self.request)
        self.assertEqual(self.outgoing.last_seen.content, collapse("""\
            Iliquat dictum patin rilit aciduipis, sectem nummolorem
            esequat. Alisis nummolorem ros quatuer iuscing iure nonsequ,
            ad commy congue, faccummy aut esequat quisi. Eugiam velis
            odipsumsan ate a sismolore. Magniat vero sociosqu, mauris
            quamconsequi irilit urna niscidu consequis, magniamet
            aciduipis utet. Justo consequipis..."""))

    def test_unicode(self):
        self.connection.reply(dedent(u"""\
            《施氏食狮史》
            石室诗士施氏，嗜狮，誓食十狮。
            氏时时适市视狮。
            十时，适十狮适市。
            是时，适施氏适市。
            氏视是十狮，恃矢势，使是十狮逝世。
            氏拾是十狮尸，适石室。
            石室湿，氏使侍拭石室。
            石室拭，氏始试食是十狮。
            食时，始识是十狮尸，实十石狮尸。
            试释是事。"""), self.request)
        self.assertEqual(self.outgoing.last_seen.content, collapse(u"""\
            《施氏食狮史》 /
            石室诗士施氏，嗜狮，誓食十狮。 /
            氏时时适市视狮。 /
            十时，适十狮适市。 /
            是时，适施氏适市。 /
            氏视是十狮，恃矢势，使是十狮逝世。 /
            氏拾是十狮尸，适石室。 /
            石室湿，氏使侍拭石室。 /
            石室拭，氏始试食是十狮...""").encode('utf-8'))
