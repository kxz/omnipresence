# -*- coding: utf-8
"""Unit tests for the vndb event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from ...message import collapse
from ...test.helpers import AbstractCassetteTestCase

from . import Default


class VNDBTestCase(AbstractCassetteTestCase):
    command_class = Default

    @AbstractCassetteTestCase.use_cassette('vndb/no-results')
    def test_no_results(self):
        return self.assert_error(
            'slartibartfast',
            'No results found for \x02slartibartfast\x02.')

    @AbstractCassetteTestCase.use_cassette('vndb/single-result')
    def test_single_result(self):
        return self.assert_reply(
            'muv-luv alternative total eclipse',
            [collapse(u"""\
                https://vndb.org/v7052 —
                \x02Muv-Luv Alternative - Total Eclipse\x02
                (\x02マブラヴ オルタネイティヴ トータル・イクリプス\x02),
                first release 2007-08-31 — rated 7.27 (40)""")])

    @AbstractCassetteTestCase.use_cassette('vndb/multiple-results')
    def test_multiple_results(self):
        return self.assert_reply('ever17', map(collapse, [
            u"""https://vndb.org/v17 —
                \x02Ever17 -The Out of Infinity-\x02,
                first release 2002-08-29 — rated 8.71 (3763)""",
            u"""https://vndb.org/v3794 —
                \x02Ever17 CrossOver Impression\x02,
                first release 2005-12-30 — rated 6.20 (3)"""]))
