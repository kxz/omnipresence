# -*- coding: utf-8
"""Unit tests for the wwwjdic event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...message import collapse
from ...test.helpers import CommandTestMixin

from . import Default


class WWWJDICTestCase(CommandTestMixin, TestCase):
    command_class = Default

    @staticmethod
    def romanize(string):
        return 'mogiroomazi'

    def setUp(self):
        super(WWWJDICTestCase, self).setUp()
        self.command.romanize = self.romanize

    @CommandTestMixin.use_cassette('wwwjdic/no-results')
    @inlineCallbacks
    def test_no_results(self):
        yield self.send_command('slartibartfast')
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('wwwjdic/blank-results')
    @inlineCallbacks
    def test_blank_results(self):
        yield self.send_command('fureba')
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('wwwjdic/some-results')
    @inlineCallbacks
    def test_some_results(self):
        yield self.send_command('amanogawa')
        yield self.assert_reply(collapse(u"""\
            天の川(P);天の河(P)
            [あまのがわ (mogiroomazi) (P); あまのかわ (mogiroomazi)]
            (n) Milky Way; (P)"""))
        yield self.assert_reply(collapse(u"""\
            天の川銀河
            [あまのがわぎんが (mogiroomazi); あまのかわぎんが (mogiroomazi)]
            (n) Milky Way Galaxy"""))
