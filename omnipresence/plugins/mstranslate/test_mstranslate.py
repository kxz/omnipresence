# -*- coding: utf-8
"""Unit tests for the mstranslate event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...test.helpers import CommandTestMixin

from . import Default


class MicrosoftTranslatorTestCase(CommandTestMixin, TestCase):
    command_class = Default

    def setUp(self):
        super(MicrosoftTranslatorTestCase, self).setUp()
        self.connection.settings.set('mstranslate.subscription_key', '<KEY>')

    @CommandTestMixin.use_cassette('mstranslate/no-language-spec')
    @inlineCallbacks
    def test_no_language_spec(self):
        yield self.send_command('hola')
        yield self.assert_reply('Hello')
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('mstranslate/source-language-spec')
    @inlineCallbacks
    def test_source_language_spec(self):
        yield self.send_command(u'ja:手紙')
        yield self.assert_reply('Letter')
        yield self.assert_no_replies()
        yield self.send_command(u'zh-CHT:手紙')
        yield self.assert_reply('Toilet paper')
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('mstranslate/target-language-spec')
    @inlineCallbacks
    def test_target_language_spec(self):
        yield self.send_command('hola ja:')
        yield self.assert_reply(u'こんにちは')
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('mstranslate/both-language-specs')
    @inlineCallbacks
    def test_both_language_specs(self):
        yield self.send_command(u'ja:手紙 de:')
        yield self.assert_reply('Brief')
        yield self.assert_no_replies()
