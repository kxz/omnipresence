"""Integration tests for connection and channel state tracking."""


from twisted.trial.unittest import TestCase

from ...hostmask import Hostmask
from ..helpers import ConnectionTestMixin


class ModeTestCase(ConnectionTestMixin, TestCase):
    def setUp(self):
        super(ModeTestCase, self).setUp()
        self.connection.joined('#foo')

    def test_voice(self):
        self.assertFalse(self.connection.venues[self.channels[0]].modes['m'])
        self.receive('MODE {} +m'.format(self.channels[0]))
        self.assertTrue(self.connection.venues[self.channels[0]].modes['m'])
        self.receive('MODE {} -m'.format(self.channels[0]))
        self.assertFalse(self.connection.venues[self.channels[0]].modes['m'])

    def test_limit(self):
        self.assertFalse(self.connection.venues[self.channels[0]].modes['l'])
        self.receive('MODE {} +l 50'.format(self.channels[0]))
        self.assertEqual(
            self.connection.venues[self.channels[0]].modes['l'], 50)
        self.receive('MODE {} -l'.format(self.channels[0]))
        self.assertFalse(self.connection.venues[self.channels[0]].modes['l'])
    test_limit.todo = 'mode argument tracking not implemented'

    def test_key(self):
        self.assertFalse(self.connection.venues[self.channels[0]].modes['k'])
        self.receive('MODE {} +k mombasa'.format(self.channels[0]))
        self.assertEqual(
            self.connection.venues[self.channels[0]].modes['k'], 'mombasa')
        self.receive('MODE {} -k'.format(self.channels[0]))
        self.assertFalse(self.connection.venues[self.channels[0]].modes['k'])
    test_key.todo = 'mode argument tracking not implemented'

    def test_ban(self):
        self.assertFalse(self.connection.venues[self.channels[0]].modes['b'])
        self.receive('MODE {} +b *!*@*.test'.format(self.channels[0]))
        self.assertSetEqual(
            self.connection.venues[self.channels[0]].modes['b'],
            {Hostmask('*', '*', '*.test'),})
        self.receive('MODE {} -b'.format(self.channels[0]))
        self.assertSetEqual(
            self.connection.venues[self.channels[0]].modes['b'],
            {Hostmask('*', '*', '*.test'),})
        self.receive('MODE {} -b *!*@*.test'.format(self.channels[0]))
        self.assertSetEqual(
            self.connection.venues[self.channels[0]].modes['b'],
            set())
    test_ban.todo = 'mode argument tracking not implemented'

    def test_op_after_join(self):
        # Should verify that user doesn't have op on join and that
        # user's venue state gets updated when "+o user" is received.
        raise NotImplementedError
    test_op_after_join.todo = 'test not implemented'

    def test_op_on_join(self):
        # Should verify that user has op on join and that user's venue
        # state gets updated when "-o user" is received.
        raise NotImplementedError
    test_op_on_join.todo = 'test not implemented'
