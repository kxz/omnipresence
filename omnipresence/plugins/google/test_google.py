# -*- coding: utf-8
"""Unit tests for the google event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks

from ...compat import length_hint
from ...message import collapse
from ...plugin import UserVisibleError
from ...test.helpers import AbstractCassetteTestCase

from . import Default


class GoogleTestCase(AbstractCassetteTestCase):
    command_class = Default

    def setUp(self):
        super(GoogleTestCase, self).setUp()
        self.connection.settings.set('google.key', '<KEY>')
        self.connection.settings.set('google.cx', '<CX>')

    @AbstractCassetteTestCase.use_cassette('google/no-results')
    @inlineCallbacks
    def test_no_results(self):
        response = yield self.send_command(
            '"high queen encouraging regret"')  # just four random words
        failed = self.assertFailure(next(response), UserVisibleError)
        failed.addCallback(lambda e: self.assertEqual(
            str(e),
            'No results found for \x02"high queen encouraging regret"\x02.'))

    @AbstractCassetteTestCase.use_cassette('google/single-page')
    @inlineCallbacks
    def test_single_page(self):
        self.command.num = 1
        response = yield self.send_command(
            '"cui said shows that embedded devices"')
        result = yield next(response)
        self.assertEqual(result, collapse(u"""\
            http://arstechnica.com/security/2015/08/funtenna-software-hack-turns-a-laser-printer-into-a-covert-radio/ —
            \x02\u201cFuntenna\u201d software hack turns a laser printer into a covert radio ...\x02:
            5 hours ago \x02...\x02 The demonstration, \x02Cui said,
            shows that embedded devices\x02 need their own built-in
            defenses to truly be secure. And printers are merely a ...
            """))
        self.assertEqual(length_hint(response), 0)
        result = yield next(response)
        self.assertIsNone(result)

    @AbstractCassetteTestCase.use_cassette('google/multiple-pages')
    @inlineCallbacks
    def test_multiple_pages(self):
        self.command.num = 1
        response = yield self.send_command('slartibartfast')
        result = yield next(response)
        self.assertEqual(result, collapse(u"""\
            https://en.wikipedia.org/wiki/Slartibartfast —
            \x02Slartibartfast - Wikipedia, the free encyclopedia\x02:
            \x02Slartibartfast\x02 is a character in The Hitchhiker's
            Guide to the Galaxy, a comedy/science fiction series
            created by Douglas Adams. The character appears in the first
            ...
            """))
        self.assertEqual(length_hint(response), 27999)
        result = yield next(response)
        self.assertEqual(result, collapse(u"""\
            http://hitchhikers.wikia.com/wiki/Slartibartfast —
            \x02Slartibartfast - Hitchhikers\x02:
            \x02Slartibartfast\x02 was a Magrathean designer of planets.
            During the planet's societal height, he...
            """))
        self.assertEqual(length_hint(response), 27998)
