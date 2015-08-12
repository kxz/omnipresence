"""Unit tests for the help event plugin."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...message import collapse
from ...plugin import EventPlugin
from ...test.helpers import CommandTestMixin

from . import Default


class HelplessPlugin(EventPlugin):
    pass


class HelpTestCase(CommandTestMixin, TestCase):
    command_class = Default

    def setUp(self):
        super(HelpTestCase, self).setUp()
        self.connection.settings.enable(HelplessPlugin.name, ['helpless'])

    @inlineCallbacks
    def test_no_arguments(self):
        yield self.send_command('')
        yield self.assert_reply(collapse("""\
            Available commands: \x02{0}\x02, \x02helpless\x02. For
            further help, use \x02{0}\x02 \x1Fkeyword\x1F. To redirect
            a command reply to another user, use \x1Fcommand\x1F
            \x02>\x02 \x1Fnick\x1F.""".format(self.keyword)))

    @inlineCallbacks
    def test_missing_command(self):
        yield self.send_command('lorem')
        yield self.assert_reply(collapse(
            'There is no command with the keyword \x02lorem\x02.'))

    @inlineCallbacks
    def test_missing_help(self):
        yield self.send_command('helpless')
        yield self.assert_reply(collapse(
            'There is no further help available for \x02helpless\x02.'))

    @inlineCallbacks
    def test_own_help(self):
        yield self.send_command(self.keyword)
        yield self.assert_reply(collapse("""\
            \x02{}\x02 [\x1Fkeyword\x1F] - List available command
            keywords, or, given a keyword, get detailed help on a
            specific command.""".format(self.keyword)))
