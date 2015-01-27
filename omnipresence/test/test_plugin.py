"""Unit tests for event plugin discovery."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from ..plugin import EventPlugin, load_plugin


default     = EventPlugin()
alternative = EventPlugin()
nonplugin   = 'foobar'


class PluginDiscoveryTestCase(unittest.TestCase):
    def _test_working_load(self, name, expected_plugin):
        plugin = load_plugin(name)
        self.assertIs(plugin, expected_plugin)
        self.assertEqual(plugin.name, 'plugin ' + name)

    def test_load_default(self):
        self._test_working_load(__name__, default)

    def test_load_member(self):
        self._test_working_load(__name__ + '/alternative', alternative)

    def test_raise_missing_module(self):
        self.assertRaises(ImportError, load_plugin, __name__ + '.missing')

    def test_raise_missing_member(self):
        self.assertRaises(AttributeError, load_plugin, __name__ + '/missing')

    def test_raise_incorrect_type(self):
        self.assertRaises(TypeError, load_plugin, __name__ + '/nonplugin')
