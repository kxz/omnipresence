"""Unit tests for configuration file parsing."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from ...case_mapping import CaseMapping, KNOWN_CASE_MAPPINGS
from ...hostmask import Hostmask
from ...message import Message
from ...plugin import EventPlugin
from ...settings import ConnectionSettings
from ..helpers import DummyConnection
from .test_case_mapping import EXPECTED as CASE_MAPPING_EXPECTED


DUMMY_CONNECTION = DummyConnection()
CONNECTION_MESSAGE = Message(DUMMY_CONNECTION, False, 'privmsg',
                             actor=Hostmask('nick', 'user', 'host'))
PRIVATE_MESSAGE = CONNECTION_MESSAGE._replace(venue='foo')
CHANNEL_MESSAGE = CONNECTION_MESSAGE._replace(venue='#foo')


class PluginA(EventPlugin): pass
class PluginB(EventPlugin): pass
class PluginC(EventPlugin): pass


class SettingsTestCase(unittest.TestCase):
    def test_fail_incorrect_type(self):
        self.assertRaises(TypeError, ConnectionSettings, 'just a string')

    def test_fail_invalid_directives(self):
        cases = [
            {'': None},
            {'"': None},
            {'set': None},
            {'plugin': None},
            {'ignore': None},
            {'channel': None},
            {'set name extra_arg': None},
            {'plugin name extra_arg': None},
            {'ignore name extra_arg': None},
            {'channel name extra_arg': None},
            {'private extra_arg': None},
            {'host extra_arg': None},
            {'port extra_arg': None},
            {'ssl extra_arg': None},
            {'nickname extra_arg': None},
            {'username extra_arg': None},
            {'password extra_arg': None},
            {'realname extra_arg': None},
            {'userinfo extra_arg': None},
            {'enabled extra_arg': None},
            {'i_am_a_banana': None}]
        for case in cases:
            self.assertRaises(ValueError, ConnectionSettings, case)

    def test_fail_invalid_nesting(self):
        cases = [
            {'channel test': {'channel inside_channel': None}},
            {'channel test': {'private': None}},
            {'channel test': {'host': 'irc.foo.example'}},
            {'channel test': {'port': 6667}},
            {'channel test': {'ssl': True}},
            {'private': {'enabled': True}},
            {'enabled': False}]
        for case in cases:
            self.assertRaises(ValueError, ConnectionSettings, case)

    def test_fail_invalid_ignores(self):
        self.assertRaises(TypeError, ConnectionSettings, {
            'ignore empty': None})
        self.assertRaises(ValueError, ConnectionSettings, {
            'ignore test': {'invalid_key': None}})
        self.assertRaises(ValueError, ConnectionSettings, {
            'ignore both_ex_and_include': {'exclude': None, 'include': None}})
        self.assertRaises(ValueError, ConnectionSettings, {
            'ignore without_plugins': {'hostmasks': []}})
        self.assertRaises(TypeError, ConnectionSettings, {
            'ignore test': {'hostmasks': 'whoops_a_string', 'include': []}})
        self.assertRaises(TypeError, ConnectionSettings, {
            'ignore test': {'hostmasks': [], 'exclude': 'whoops_a_string'}})
        self.assertRaises(TypeError, ConnectionSettings, {
            'ignore test': {'hostmasks': [], 'include': 'whoops_a_string'}})

    def test_fail_invalid_plugins(self):
        self.assertRaises(TypeError, ConnectionSettings, {
            'plugin test': 'whoops_a_string'})

    def test_autojoin_channels(self):
        settings = ConnectionSettings({
            'channel foo': {},
            'channel bar': {'enabled': False},
            'channel #baz': {'enabled': 'soft'},
            'channel &quux': {}})
        self.assertItemsEqual(settings.autojoin_channels, ['#foo', '&quux'])
        self.assertItemsEqual(settings.autopart_channels, ['#bar'])

    def test_minimal_connection(self):
        settings = ConnectionSettings({'host': 'irc.foo.test'})
        self.assertEqual(settings.host, 'irc.foo.test')
        self.assertEqual(settings.port, 6667)
        self.assertFalse(settings.ssl)

    def test_maximal_connection(self):
        settings = ConnectionSettings({
            'host': 'irc.foo.test', 'port': 6697, 'ssl': True})
        self.assertEqual(settings.host, 'irc.foo.test')
        self.assertEqual(settings.port, 6697)
        self.assertTrue(settings.ssl)

    def test_variable_inheritance(self):
        settings = ConnectionSettings({
            'set spam': 'connection',
            'set ham': 'connection',
            'set eggs': 'connection',
            'channel foo': {
                'set ham': 'channel',
                'set eggs': 'channel'},
            'private': {'set eggs': 'private'}})
        self.assertEqual(settings.get('spam'), 'connection')
        self.assertEqual(settings.get('ham'), 'connection')
        self.assertEqual(settings.get('eggs'), 'connection')
        self.assertEqual(settings.get('spam', message=CHANNEL_MESSAGE),
                         'connection')
        self.assertEqual(settings.get('ham', message=CHANNEL_MESSAGE),
                         'channel')
        self.assertEqual(settings.get('eggs', message=CHANNEL_MESSAGE),
                         'channel')
        self.assertEqual(settings.get('spam', message=PRIVATE_MESSAGE),
                         'connection')
        self.assertEqual(settings.get('ham', message=PRIVATE_MESSAGE),
                         'connection')
        self.assertEqual(settings.get('eggs', message=PRIVATE_MESSAGE),
                         'private')

    def test_case_mapping(self):
        for (a, b), equal_case_mappings in CASE_MAPPING_EXPECTED.iteritems():
            settings = ConnectionSettings({
                'set spam': 'connection',
                # Escape backslashes for shlex.split.
                'channel {}'.format(a.replace('\\', '\\\\')): {
                    'set spam': 'channel'}})
            for name in KNOWN_CASE_MAPPINGS:
                settings.set_case_mapping(CaseMapping.by_name(name))
                self.assertEqual(
                    settings.get('spam', message=CHANNEL_MESSAGE._replace(
                        venue='#{}'.format(b))),
                    'channel' if name in equal_case_mappings else 'connection')

    def assert_plugins_with_keywords(self, actual, expected):
        self.assertEqual({type(plugin).name: keywords for plugin, keywords
                          in actual.iteritems()}, expected)

    def test_plugins_and_ignores(self):
        settings = ConnectionSettings({
            'plugin ..test.unit.test_settings/PluginA': [],
            'plugin ..test.unit.test_settings/PluginB': ['foo', 'bar'],
            'ignore test': {
                'hostmasks': ['nick!*@*'],
                'include': ['..test.unit.test_settings/PluginA']},
            'channel foo': {
                'plugin ..test.unit.test_settings/PluginB': False,
                'ignore test': {  # overrides root rule with same name
                    'hostmasks': ['other!*@*'],
                    'exclude': ['..test.unit.test_settings/PluginA']}},
            'private': {
                'plugin ..test.unit.test_settings/PluginB': ['baz'],
                'plugin ..test.unit.test_settings/PluginC': True,
                'ignore test': False}})
        self.assert_plugins_with_keywords(settings.active_plugins(), {
            PluginA.name: [],
            PluginB.name: ['foo', 'bar']})
        self.assert_plugins_with_keywords(
            settings.active_plugins(message=CHANNEL_MESSAGE),
            {PluginA.name: []})
        other_message = CHANNEL_MESSAGE._replace(
            actor=Hostmask('other', 'user', 'host'))
        self.assert_plugins_with_keywords(
            settings.active_plugins(message=other_message),
            {PluginA.name: []})
        bar_message = CHANNEL_MESSAGE._replace(venue='#bar')
        self.assert_plugins_with_keywords(
            settings.active_plugins(message=bar_message),
            {PluginB.name: ['foo', 'bar']})
        self.assert_plugins_with_keywords(
            settings.active_plugins(message=PRIVATE_MESSAGE), {
                PluginA.name: [],
                PluginB.name: ['baz'],
                PluginC.name: []})
        self.assertEqual(settings.plugins_by_keyword('foo'),
                         settings.plugins_by_keyword('bar'))
        self.assertEqual(
            settings.plugins_by_keyword('bar', message=PRIVATE_MESSAGE),
            [])
        self.assertEqual(
            settings.plugins_by_keyword('foo'),
            settings.plugins_by_keyword('baz', message=PRIVATE_MESSAGE))

    def test_ignore_precedence(self):
        settings = ConnectionSettings({
            'plugin ..test.unit.test_settings/PluginA': [],
            'plugin ..test.unit.test_settings/PluginB': [],
            'ignore include': {'hostmasks': ['nick!*@*'], 'include': [
                '..test.unit.test_settings/PluginA']},
            'ignore exclude1': {'hostmasks': ['*!*@host'], 'exclude': []},
            'ignore exclude2': {'hostmasks': ['*!*@host'], 'exclude': [
                '..test.unit.test_settings/PluginB']}})
        self.assert_plugins_with_keywords(
            settings.active_plugins(message=PRIVATE_MESSAGE),
            {PluginB.name: []})

    def test_ignore_hostmasks_case_mapping(self):
        for (a, b), equal_case_mappings in CASE_MAPPING_EXPECTED.iteritems():
            settings = ConnectionSettings({
                'plugin ..test.unit.test_settings/PluginA': True,
                'ignore test': {
                    'hostmasks': [a],
                    'exclude': []}})
            for name in KNOWN_CASE_MAPPINGS:
                settings.set_case_mapping(CaseMapping.by_name(name))
                self.assert_plugins_with_keywords(
                    settings.active_plugins(message=CHANNEL_MESSAGE._replace(
                        actor=Hostmask(b, 'user', 'host'))),
                    {} if name in equal_case_mappings else {PluginA.name: []})

    def test_empty_exclude(self):
        settings = ConnectionSettings({
            'plugin ..test.unit.test_settings/PluginA': [],
            'plugin ..test.unit.test_settings/PluginB': [],
            'ignore all': {'hostmasks': ['nick!*@*'], 'exclude': []}})
        self.assert_plugins_with_keywords(
            settings.active_plugins(message=PRIVATE_MESSAGE), {})

    def test_data(self):
        # Implicitly assert that no errors are raised.
        ConnectionSettings({
            'data': {
                'channel i_can_do_whatever': {
                    'private i_want': {}},
                'hello world': 225555}})
