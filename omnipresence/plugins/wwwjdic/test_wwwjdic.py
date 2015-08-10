# -*- coding: utf-8
"""Unit tests for the wwwjdic event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from ...message import collapse
from ...test.helpers import AbstractCassetteTestCase

from . import Default


class WWWJDICTestCase(AbstractCassetteTestCase):
    command_class = Default

    @staticmethod
    def romanize(string):
        return 'mogiroomazi'

    def setUp(self):
        super(WWWJDICTestCase, self).setUp()
        self.command.romanize = WWWJDICTestCase.romanize

    @AbstractCassetteTestCase.use_cassette('wwwjdic/no-results')
    def test_no_results(self):
        return self.assert_error(
            'slartibartfast',
            'No results found for \x02slartibartfast\x02.')

    @AbstractCassetteTestCase.use_cassette('wwwjdic/some-results')
    def test_some_results(self):
        return self.assert_reply('amanogawa', map(collapse, [
            u"""天の川(P);天の河(P)
                [あまのがわ (mogiroomazi) (P); あまのかわ (mogiroomazi)]
                (n) Milky Way; (P)""",
            u"""天の川銀河
                [あまのがわぎんが (mogiroomazi); あまのかわぎんが (mogiroomazi)]
                (n) Milky Way Galaxy"""]))
