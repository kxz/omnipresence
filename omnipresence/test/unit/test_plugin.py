"""Unit tests for event plugin discovery and base classes."""
# pylint: disable=missing-docstring,too-few-public-methods

from mock import Mock
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from ...message import Message
from ...plugin import (EventPlugin, SubcommandEventPlugin,
                       plugin_class_by_name, UserVisibleError)


#
# Plugin loading
#

class Default(EventPlugin):
    pass

class Alternative(EventPlugin):
    pass

class NonPlugin(object):
    pass


class PluginDiscoveryTestCase(TestCase):
    def _test_working_load(self, name, expected_plugin):
        plugin = plugin_class_by_name(name)
        self.assertIs(plugin, expected_plugin)
        self.assertEqual(plugin.name, name)

    def test_load_default(self):
        self._test_working_load(__name__, Default)

    def test_load_member(self):
        self._test_working_load(__name__ + '/Alternative', Alternative)

    def test_raise_missing_module(self):
        self.assertRaises(ImportError,
                          plugin_class_by_name, __name__ + '.missing')

    def test_raise_missing_member(self):
        self.assertRaises(AttributeError,
                          plugin_class_by_name, __name__ + '/Missing')

    def test_raise_incorrect_type(self):
        self.assertRaises(TypeError,
                          plugin_class_by_name, __name__ + '/NonPlugin')


#
# SubcommandEventPlugin convenience class
#

class SubcommandTestCase(TestCase):
    def setUp(self):
        self.plugin = SubcommandEventPlugin()
        self.plugin.on_subcommand_spam = Mock(return_value='spam')
        self.plugin.on_subcmdhelp_spam = Mock(return_value='- help')

    def _send(self, action, args):
        self.msg = Message(None, False, action, subaction='foo', content=args)
        return self.plugin.respond_to(self.msg)

    @inlineCallbacks
    def test_default_empty_subcommand(self):
        with self.assertRaisesRegexp(UserVisibleError, 'Please.*spam'):
            yield self._send('command', '')

    @inlineCallbacks
    def test_default_empty_subcmdhelp(self):
        reply = yield self._send('cmdhelp', '')
        self.assertTrue('spam' in reply)

    @inlineCallbacks
    def test_default_invalid_subcommand(self):
        with self.assertRaisesRegexp(UserVisibleError, 'Unrecognized.*spam'):
            yield self._send('command', 'ham')

    @inlineCallbacks
    def test_default_invalid_subcmdhelp(self):
        reply = yield self._send('cmdhelp', 'ham')
        self.assertTrue('spam' in reply)

    @inlineCallbacks
    def test_valid_subcommand(self):
        reply = yield self._send('command', 'spam')
        self.plugin.on_subcommand_spam.assert_called_with(self.msg, '')
        self.assertEqual(reply, 'spam')

    @inlineCallbacks
    def test_valid_subcommand_with_more_arguments(self):
        reply = yield self._send('command', 'spam 1 2 3')
        self.plugin.on_subcommand_spam.assert_called_with(self.msg, '1 2 3')
        self.assertEqual(reply, 'spam')

    @inlineCallbacks
    def test_valid_subcmdhelp(self):
        reply = yield self._send('cmdhelp', 'spam')
        self.plugin.on_subcmdhelp_spam.assert_called_with(self.msg)
        self.assertEqual(reply, '\x02spam\x02 - help')
