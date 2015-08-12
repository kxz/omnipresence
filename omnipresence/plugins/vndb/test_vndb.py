# -*- coding: utf-8
"""Unit tests for the vndb event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...message import collapse
from ...test.helpers import CommandTestMixin

from . import Default


class VNDBTestCase(CommandTestMixin, TestCase):
    command_class = Default

    @CommandTestMixin.use_cassette('vndb/no-results')
    @inlineCallbacks
    def test_no_results(self):
        yield self.send_command('slartibartfast')
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('vndb/single-result')
    @inlineCallbacks
    def test_single_result(self):
        yield self.send_command('muv-luv alternative total eclipse')
        yield self.assert_reply(collapse(u"""\
            https://vndb.org/v7052 —
            \x02Muv-Luv Alternative - Total Eclipse\x02
            (\x02マブラヴ オルタネイティヴ トータル・イクリプス\x02),
            first release 2007-08-31 — rated 7.27 (40)"""))
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('vndb/multiple-results')
    @inlineCallbacks
    def test_multiple_results(self):
        yield self.send_command('ever17')
        yield self.assert_reply(collapse(u"""\
            https://vndb.org/v17 —
            \x02Ever17 -The Out of Infinity-\x02,
            first release 2002-08-29 — rated 8.71 (3763)"""))
        yield self.assert_reply(collapse(u"""\
            https://vndb.org/v3794 —
            \x02Ever17 CrossOver Impression\x02,
            first release 2005-12-30 — rated 6.20 (3)"""))
        yield self.assert_no_replies()
