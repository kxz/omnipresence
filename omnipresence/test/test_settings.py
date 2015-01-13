"""Unit tests for configuration file parsing."""
# pylint: disable=missing-docstring,too-few-public-methods


import os.path

from twisted.trial import unittest

from ..settings import Settings


class V2FileTestCase(unittest.TestCase):
    def setUp(self):
        v2_path = os.path.join(os.path.dirname(__file__), 'data', 'v2.cfg')
        with open(v2_path) as v2_file:
            self.settings = Settings.from_v2_file(v2_file)

    def _variable(self, key, value, scope):
        # XXX:  scope = Message(connection=fake_connection)
        self.assertEqual(self.settings.get(key, scope=scope), value)

    def test_connection(self):
        self.assertEqual(len(self.settings.connections()), 1)
        self.assertEqual(self._variable('host'), 'irc.example.com')
        self.assertEqual(self._variable('port'), 6667)
        self.assertTrue(self._variable('ssl'))
        self.assertEqual(self._variable('nickname'), 'nick')
        self.assertEqual(self._variable('password'), 'pass')
        self.assertEqual(self._variable('realname'), 'real')
        self.assertEqual(self._variable('username'), 'user')
        self.assertEqual(self._variable('encoding'), 'utf-8')
        self.assertEqual(self._variable('command_prefixes'), ['@', '!'])
        self.assertEqual(self._variable('database'), 'sqlite:/:memory:')

    def test_handlers(self):
        # XXX:  scope = Message(connection, venue='nick')
        self.assertEqual(self.settings.enabled(scope).items(),
                         ['.foo', '.bar'])
        # XXX:  scope = Message(connection, venue='#lorem')
        self.assertEqual(self.settings.enabled(scope).items(), ['.foo'])
        # XXX:  scope = Message(connection, venue='#ipsum')
        self.assertEqual(self.settings.enabled(scope).items(), ['.bar'])

    def test_commands(self):
        # XXX:  scope = Message(connection=fake_connection)
        self.assertEqual(self.settings.enabled(scope)['spam'], ['spam'])
        self.assertEqual(self.settings.enabled(scope)['ham'], ['spam'])
        self.assertEqual(self.settings.enabled(scope)['eggs'], ['eggs'])

    def test_variables(self):
        # XXX:  scope = Message(connection=fake_connection)
        self.assertEqual(self._variable('foo.var1'), 'one')
        self.assertEqual(self._variable('foo.var2'), 'two')
        self.assertEqual(self._variable('bar.var3'), 'three')
