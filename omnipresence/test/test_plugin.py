"""Unit tests for event plugin discovery."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial import unittest

from ..plugin import EventPlugin, plugin_class_by_name


class Default(EventPlugin):
    pass

class Alternative(EventPlugin):
    pass

class NonPlugin(object):
    pass


class PluginDiscoveryTestCase(unittest.TestCase):
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
