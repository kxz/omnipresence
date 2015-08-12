# -*- coding: utf-8
"""Unit tests for the google event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...compat import length_hint
from ...message import collapse
from ...plugin import UserVisibleError
from ...test.helpers import CommandTestMixin

from . import Default


class GoogleTestCase(CommandTestMixin, TestCase):
    command_class = Default

    def setUp(self):
        super(GoogleTestCase, self).setUp()
        self.connection.settings.set('google.key', '<KEY>')
        self.connection.settings.set('google.cx', '<CX>')

    @CommandTestMixin.use_cassette('google/no-results')
    @inlineCallbacks
    def test_no_results(self):
        # Just four random words.  The query may have to be changed if
        # the cassette is updated, since the source is public.
        yield self.send_command('"high queen encouraging regret"')
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('google/single-page')
    @inlineCallbacks
    def test_single_page(self):
        self.command.num = 1
        yield self.send_command('"cui said shows that embedded devices"')
        yield self.assert_reply(collapse(u"""\
            http://arstechnica.com/security/2015/08/funtenna-software-hack-turns-a-laser-printer-into-a-covert-radio/ —
            \x02\u201cFuntenna\u201d software hack turns a laser printer into a covert radio ...\x02:
            5 hours ago \x02...\x02 The demonstration, \x02Cui said,
            shows that embedded devices\x02 need their own built-in
            defenses to truly be secure. And printers are merely a ...
            """))
        yield self.assertEqual(length_hint(self.reply_buffer), 0)
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('google/multiple-pages')
    @inlineCallbacks
    def test_multiple_pages(self):
        self.command.num = 1
        yield self.send_command('slartibartfast')
        yield self.assert_reply(collapse(u"""\
            https://en.wikipedia.org/wiki/Slartibartfast —
            \x02Slartibartfast - Wikipedia, the free encyclopedia\x02:
            \x02Slartibartfast\x02 is a character in The Hitchhiker's
            Guide to the Galaxy, a comedy/science fiction series
            created by Douglas Adams. The character appears in the first
            ...
            """))
        self.assertEqual(length_hint(self.reply_buffer), 27999)
        yield self.assert_reply(collapse(u"""\
            http://hitchhikers.wikia.com/wiki/Slartibartfast —
            \x02Slartibartfast - Hitchhikers\x02:
            \x02Slartibartfast\x02 was a Magrathean designer of planets.
            During the planet's societal height, he...
            """))
        self.assertEqual(length_hint(self.reply_buffer), 27998)
