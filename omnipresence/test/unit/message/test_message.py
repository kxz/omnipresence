"""Unit tests for the `Message` class."""
# pylint: disable=missing-docstring,too-few-public-methods


from twisted.trial.unittest import TestCase

from ....message import Message


class MessageTestCase(TestCase):
    def test_invalid_action(self):
        self.assertRaises(ValueError, Message, None, False, 'foo')
