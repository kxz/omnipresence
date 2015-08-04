# -*- coding: utf-8
"""Unit tests for the vndb event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.web.client import ContentDecoderAgent, RedirectAgent, GzipDecoder

from ...message import collapse
from ...test.helpers import AbstractCommandTestCase, CassetteAgent

from . import Default


class VNDBTestCase(AbstractCommandTestCase):
    command_class = Default

    @staticmethod
    def make_agent(*args, **kwargs):
        return ContentDecoderAgent(
            RedirectAgent(CassetteAgent(*args, **kwargs)),
            [('gzip', GzipDecoder)])

    def test_no_results(self):
        self.command.agent = self.make_agent('vndb/no-results')
        return self.assert_error(
            'slartibartfast',
            'No results found for \x02slartibartfast\x02.')

    def test_single_result(self):
        self.command.agent = self.make_agent('vndb/single-result')
        return self.assert_reply(
            'muv-luv alternative total eclipse',
            [collapse(u"""\
                https://vndb.org/v7052 —
                \x02Muv-Luv Alternative - Total Eclipse\x02
                (\x02マブラヴ オルタネイティヴ トータル・イクリプス\x02),
                first release 2007-08-31 — rated 7.27 (38)""")])

    def test_multiple_results(self):
        self.command.agent = self.make_agent('vndb/multiple-results')
        return self.assert_reply('ever17', map(collapse, [
            u"""https://vndb.org/v17 —
                \x02Ever17 -The Out of Infinity-\x02,
                first release 2002-08-29 — rated 8.71 (3757)""",
            u"""https://vndb.org/v3794 —
                \x02Ever17 CrossOver Impression\x02,
                first release 2005-12-30 — rated 6.20 (3)"""]))
