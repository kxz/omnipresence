"""Unit tests for configuration file parsing."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from ..message import Message
from ..settings import BotSettings, ConnectionSettings
from .helpers import DummyConnection


DUMMY_CONNECTION = DummyConnection()
CONNECTION_MESSAGE = Message(DUMMY_CONNECTION, False, 'privmsg')
PRIVATE_MESSAGE = CONNECTION_MESSAGE._replace(venue='foo')
CHANNEL_MESSAGE = CONNECTION_MESSAGE._replace(venue='#foo')


class SettingsTestCase(unittest.TestCase):
    def test_fail_incorrect_type(self):
        self.assertRaises(TypeError, BotSettings, 'just a string')

    def test_fail_invalid_keys(self):
        cases = [
            {'connection': None},
            {'connection name extra_arg': None},
            {'connection test': {'channel': None}},
            {'connection test': {'channel name extra_arg': None}},
            {'connection test': {'private extra_arg': None}},
            {'set': None},
            {'plugin': None},
            {'ignore': None},
            {'set variable extra_arg': None},
            {'plugin name extra_arg': None},
            {'ignore name extra_arg': None},
            {'host extra_arg': None},
            {'port extra_arg': None},
            {'ssl extra_arg': None},
            {'autojoin extra_arg': None},
            {'i_am_a_banana': None}]
        for case in cases:
            self.assertRaises(ValueError, BotSettings, case)
    test_fail_invalid_keys.todo = 'unimplemented'

    def test_fail_invalid_nesting(self):
        cases = [
            # XXX:  Ensure connections have a host and port.
            {'connection test': {
                'host': 'irc.foo.example', 'port': 6667,
                'connection nested_connection': None}},
            {'channel outside_of_connection': None},
            {'private': None},
            {'connection test': {
                'host': 'irc.foo.example', 'port': 6667,
                'channel test': {
                    'connection inside_channel': None}}},
            {'connection test': {
                'host': 'irc.foo.example', 'port': 6667,
                'channel test': {
                    'channel inside_channel': None}}},
            {'host': 'irc.foo.example'},
            {'port': 6667},
            {'ssl': True},
            {'connection test': {
                'channel test': {'host': 'irc.foo.example'}}},
            {'connection test': {
                'channel test': {'port': 6667}}},
            {'connection test': {
                'channel test': {'ssl': True}}},
            {'autojoin': False},
            {'connection test': {'autojoin': False}}]
        for case in cases:
            self.assertRaises(ValueError, BotSettings, case)
    test_fail_invalid_nesting.todo = 'unimplemented'

    def test_fail_invalid_connections(self):
        self.assertRaises(ValueError, BotSettings, {
            'connection missing_host': None})
    test_fail_invalid_connections.todo = 'unimplemented'

    def test_fail_invalid_ignores(self):
        self.assertRaises(TypeError, BotSettings, {
            'ignore empty': None})
        self.assertRaises(ValueError, BotSettings, {
            'ignore test': {'invalid_key': None}})
        self.assertRaises(ValueError, BotSettings, {
            'ignore both_ex_and_include': {'exclude': None, 'include': None}})
        self.assertRaises(TypeError, BotSettings, {
            'ignore test': {'hostmasks': 'whoops_a_string'}})
        self.assertRaises(TypeError, BotSettings, {
            'ignore test': {'hostmasks': [], 'exclude': 'whoops_a_string'}})
        self.assertRaises(TypeError, BotSettings, {
            'ignore test': {'hostmasks': [], 'include': 'whoops_a_string'}})
    test_fail_invalid_ignores.todo = 'unimplemented'

    def test_fail_invalid_plugins(self):
        self.assertRaises(TypeError, BotSettings, {
            'plugin test': 'whoops_a_string'})
    test_fail_invalid_plugins.todo = 'unimplemented'

    def test_autojoin_channels(self):
        settings_dict = {'channel foo': None,
                         'channel bar': {'autojoin': False},
                         'channel &baz': None}
        self.assertEqual(
            ConnectionSettings(settings_dict).autojoin_channels(),
            set('#foo', '&baz'))
    test_autojoin_channels.todo = 'unimplemented'

    def test_warn_connection_mismatch(self):
        # XXX:  Warn if the connection used for ConnectionSettings and
        # the connection in a scope message are different.
        pass
    test_warn_connection_mismatch.skip = 'empty stub test'

    # TODO:  Case mapping tests.

    def test_connections(self):
        settings = BotSettings({
            'connection foo': {
                'host': 'irc.foo.example', 'port': 6667},
            'connection bar': {
                'host': 'irc.bar.example', 'port': 6697, 'ssl': True}})
        foo_settings = settings.connections['foo']
        self.assertEqual(foo_settings.host, 'irc.foo.example')
        self.assertEqual(foo_settings.port, 6667)
        self.assertFalse(foo_settings.ssl)
        bar_settings = settings.connections['bar']
        self.assertEqual(bar_settings.host, 'irc.bar.example')
        self.assertEqual(bar_settings.port, 6697)
        self.assertTrue(bar_settings.ssl)
    test_connections.todo = 'unimplemented'

    def test_variable_inheritance(self):
        settings = BotSettings({
            'set spam': 'global',
            'set ham': 'global',
            'set eggs': 'global',
            'connection foo': {
                'set ham': 'connection',
                'set eggs': 'connection',
                'private': {'set eggs': 'private'},
                'channel bar': {'set eggs': 'channel'}}})
        self.assertEqual(settings.get('spam'), 'global')
        self.assertEqual(settings.get('ham'), 'global')
        self.assertEqual(settings.get('eggs'), 'global')
        foo_settings = settings.connections['foo']
        self.assertEqual(foo_settings.get('spam'), 'global')
        self.assertEqual(foo_settings.get('ham'), 'connection')
        self.assertEqual(foo_settings.get('eggs'), 'connection')
        self.assertEqual(foo_settings.get('spam', scope=PRIVATE_MESSAGE),
                         'global')
        self.assertEqual(foo_settings.get('ham', scope=PRIVATE_MESSAGE),
                         'connection')
        self.assertEqual(foo_settings.get('eggs', scope=PRIVATE_MESSAGE),
                         'private')
        self.assertEqual(foo_settings.get('spam', scope=CHANNEL_MESSAGE),
                         'global')
        self.assertEqual(foo_settings.get('ham', scope=CHANNEL_MESSAGE),
                         'connection')
        self.assertEqual(foo_settings.get('eggs', scope=CHANNEL_MESSAGE),
                         'channel')
    test_variable_inheritance.todo = 'unimplemented'

    def test_plugin_inheritance(self):
        # XXX:  Include ignore rules.
        pass
    test_plugin_inheritance.skip = 'empty stub test'
