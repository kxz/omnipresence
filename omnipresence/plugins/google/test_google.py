# -*- coding: utf-8
"""Unit tests for the google event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.web.client import ContentDecoderAgent, RedirectAgent, GzipDecoder

from ...compat import length_hint
from ...message import collapse
from ...plugin import UserVisibleError
from ...test.helpers import AbstractCommandTestCase, CassetteAgent

from . import Default


class GoogleTestCase(AbstractCommandTestCase):
    command_class = Default

    def setUp(self):
        super(GoogleTestCase, self).setUp()
        self.connection.settings.set('google.key', '<KEY>')
        self.connection.settings.set('google.cx', '<CX>')

    @staticmethod
    def make_agent(*args, **kwargs):
        return ContentDecoderAgent(
            RedirectAgent(CassetteAgent(*args, **kwargs)),
            [('gzip', GzipDecoder)])

    @inlineCallbacks
    def test_no_key(self):
        self.command.agent = self.make_agent('google/no-key')
        response = yield self.send_command('no key')
        failure = self.failureResultOf(next(response), UserVisibleError)
        self.assertEqual(
            str(failure.value),
            'Google API error: Daily Limit for Unauthenticated Use '
            'Exceeded. Continued use requires signup.')

    @inlineCallbacks
    def test_no_results(self):
        self.command.agent = self.make_agent('google/no-results')
        response = yield self.send_command(
            '"high queen encouraging regret"')  # just four random words
        failure = self.failureResultOf(next(response), UserVisibleError)
        self.assertEqual(
            str(failure.value),
            'No results found for \x02"high queen encouraging regret"\x02.')

    @inlineCallbacks
    def test_single_page(self):
        self.command.agent = self.make_agent('google/single-page')
        self.command.num = 1
        response = yield self.send_command(
            '"cuphead is difficult i mean really really difficult"')
        result = yield next(response)
        self.assertEqual(result, collapse(u"""\
            http://arstechnica.co.uk/gaming/2015/08/cuphead-is-stupidly-hard-stupidly-beautiful-and-i-love-it/ —
            \x02Cuphead is stupidly hard, stupidly beautiful, and I love it | Ars ...\x02:
            8 hours ago \x02...\x02 COLOGNE, Germany—\x02Cuphead is
            difficult. I mean, really, really difficult\x02. If you
            don't die within the first few minutes of playing, you're
            either ...
            """))
        self.assertEqual(length_hint(response), 0)
        result = yield next(response)
        self.assertIsNone(result)

    @inlineCallbacks
    def test_multiple_pages(self):
        self.command.agent = self.make_agent('google/multiple-pages')
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
        self.assertEqual(length_hint(response), 28099)
        result = yield next(response)
        self.assertEqual(result, collapse(u"""\
            http://hitchhikers.wikia.com/wiki/Slartibartfast —
            \x02Slartibartfast - Hitchhikers\x02:
            \x02Slartibartfast\x02 was a Magrathean designer of planets.
            During the planet's societal height, he...
            """))
        self.assertEqual(length_hint(response), 28098)
