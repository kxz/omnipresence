# -*- coding: utf-8
"""Unit tests for the anidb event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from ...message import collapse
from ...test.helpers import AbstractCassetteTestCase

from . import Default


class AniDBTestCase(AbstractCassetteTestCase):
    command_class = Default

    @AbstractCassetteTestCase.use_cassette('anidb/no-results')
    def test_no_results(self):
        return self.assert_error(
            'slartibartfast',
            'No results found for \x02slartibartfast\x02.')

    @AbstractCassetteTestCase.use_cassette('anidb/single-result')
    def test_single_result(self):
        return self.assert_reply(
            'bakemonogatari',
            [collapse(u"""\
                http://anidb.net/a6327 —
                \x02Bakemonogatari\x02 —
                TV Series, 12 episodes from 2009-07-03 to 2009-09-25 —
                rated 8.43 (7443)""")])

    @AbstractCassetteTestCase.use_cassette('anidb/multiple-results')
    def test_multiple_results(self):
        return self.assert_reply('suzumiya', map(collapse, [
            u"""http://anidb.net/a3651 —
                \x02Suzumiya Haruhi no Yuuutsu\x02 —
                TV Series, 14 episodes from 2006-04-03 to 2006-07-03 —
                rated 8.16 (13583)""",
            u"""http://anidb.net/a6367 —
                \x02Suzumiya Haruhi no Yuuutsu (2009)\x02 —
                TV Series, 28 episodes from 2009-04-03 to 2009-10-09 —
                rated 5.18 (4482)""",
            u"""http://anidb.net/a7221 —
                \x02Suzumiya Haruhi no Shoushitsu\x02 —
                Movie, 1 episode on 2010-02-06 —
                rated 9.41 (4208)""",
            u"""http://anidb.net/a5335 —
                \x02Suzumiya Haruhi-chan no Yuuutsu\x02 —
                Web, 25 episodes from 2009-02-14 to 2009-05-08 —
                rated 5.32 (1635)"""]))
