# -*- coding: utf-8
"""Unit tests for the anidb event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...message import collapse
from ...test.helpers import CommandTestMixin

from . import Default


class AniDBTestCase(CommandTestMixin, TestCase):
    command_class = Default

    @CommandTestMixin.use_cassette('anidb/no-results')
    @inlineCallbacks
    def test_no_results(self):
        yield self.send_command('slartibartfast')
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('anidb/single-result')
    @inlineCallbacks
    def test_single_result(self):
        yield self.send_command('bakemonogatari')
        yield self.assert_reply(collapse(u"""\
            http://anidb.net/a6327 —
            \x02Bakemonogatari\x02 —
            TV Series, 12 episodes from 2009-07-03 to 2009-09-25 —
            rated 8.43 (7443)"""))
        yield self.assert_no_replies()

    @CommandTestMixin.use_cassette('anidb/multiple-results')
    @inlineCallbacks
    def test_multiple_results(self):
        yield self.send_command('suzumiya')
        yield self.assert_reply(collapse(u"""\
            http://anidb.net/a3651 —
            \x02Suzumiya Haruhi no Yuuutsu\x02 —
            TV Series, 14 episodes from 2006-04-03 to 2006-07-03 —
            rated 8.16 (13583)"""))
        yield self.assert_reply(collapse(u"""\
            http://anidb.net/a6367 —
            \x02Suzumiya Haruhi no Yuuutsu (2009)\x02 —
            TV Series, 28 episodes from 2009-04-03 to 2009-10-09 —
            rated 5.18 (4482)"""))
        yield self.assert_reply(collapse(u"""\
            http://anidb.net/a7221 —
            \x02Suzumiya Haruhi no Shoushitsu\x02 —
            Movie, 1 episode on 2010-02-06 —
            rated 9.41 (4208)"""))
        yield self.assert_reply(collapse(u"""\
            http://anidb.net/a5335 —
            \x02Suzumiya Haruhi-chan no Yuuutsu\x02 —
            Web, 25 episodes from 2009-02-14 to 2009-05-08 —
            rated 5.32 (1635)"""))
        yield self.assert_no_replies()
