"""Unit tests for IRC message handling."""


import functools

from twisted.trial import unittest

from ..hostmask import Hostmask
from ..message import (Message,
                       remove_formatting as rm,
                       unclosed_formatting as uc)


class FormattingTestCase(unittest.TestCase):
    def test_removal(self):
        self.assertEqual(rm('lorem ipsum'), 'lorem ipsum')
        self.assertEqual(rm('lorem \x03ipsum'), 'lorem ipsum')
        self.assertEqual(rm('dolor \x032,12sit'), 'dolor sit')
        self.assertEqual(rm('\x02a\x0Fm\x033et'), 'amet')

    def test_unclosed(self):
        self.assertEqual(uc('lorem ipsum'), frozenset())
        self.assertEqual(uc('lorem \x03ipsum'), frozenset())
        self.assertEqual(uc('dolor \x032,12sit'),
                         frozenset(['\x032,12']))
        self.assertEqual(uc('dolor \x031,12\x032sit'),
                         frozenset(['\x032,12']))
        self.assertEqual(uc('\x02a\x0F\x1Fm\x033et'),
                         frozenset(['\x1F', '\x033']))


class ExtractionTestCase(unittest.TestCase):
    prototype = Message(None, 'nick!user@host', 'privmsg')

    def sample(self, *args, **kwargs):
        return self.prototype._replace(*args, **kwargs)

    def test_extraction(self):
        e = functools.partial(Message.extract_command,
                              prefixes=['!', 'bot:', 'bot,'])
        self.assertEqual(
            e(self.sample(action='topic')),
            None)
        self.assertEqual(
            e(self.sample(content='ipsum')),
            None)
        self.assertEqual(
            e(self.sample(content='!help')),
            self.sample(action='command', target='nick',
                        content=('help', '')))
        self.assertEqual(
            e(self.sample(content='bot: help')),
            self.sample(action='command', target='nick',
                        content=('help', '')))
        self.assertEqual(
            e(self.sample(content='bot, help me')),
            self.sample(action='command', target='nick',
                        content=('help', 'me')))
        self.assertEqual(
            e(self.sample(content='!help >')),
            self.sample(action='command', target='nick',
                        content=('help', '')))
        self.assertEqual(
            e(self.sample(content='!help > other')),
            self.sample(action='command', target='other',
                        content=('help', '')))
