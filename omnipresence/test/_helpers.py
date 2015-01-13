"""Unit test helpers."""
# pylint: disable=missing-docstring,too-few-public-methods


from collections import defaultdict

from twisted.test.proto_helpers import StringTransport
from twisted.trial import unittest
from twisted.words.protocols.irc import CHANNEL_PREFIXES

from .. import IRCClient
from ..config import OmnipresenceConfigParser


#
# Helper objects
#

class AbortableStringTransport(StringTransport):
    """A StringTransport that supports abortConnection()."""
    # <https://twistedmatrix.com/trac/ticket/6530>

    def abortConnection(self):
        self.loseConnection()


class DummyFactory(object):
    """A class that simulates the behavior of an IRCClientFactory."""
    # TODO:  Refactor IRCClient/Connection so that this isn't necessary
    # for connection tests.

    def __init__(self):
        self.handlers = defaultdict(list)
        self.config = OmnipresenceConfigParser()
        self.config.add_section('core')
        self.config.set('core', 'nickname', 'Omnipresence')
        self.config.set('core', 'database', 'sqlite:/:memory:')
        self.config.set('core', 'command_prefixes', '')
        self.config.add_section('channels')
        self.config.set('channels', '@', '')
        self.config.add_section('commands')
        self.config.set('commands', 'more', 'more')
        self.config.set('commands', 'help', 'help')

    def resetDelay(self):
        pass


class DummyConnection(object):
    """A class that simulates the behavior of a live connection."""

    def is_channel(self, venue):
        return venue[0] in CHANNEL_PREFIXES


#
# Abstract test cases
#

class AbstractConnectionTestCase(unittest.TestCase):
    def setUp(self):
        self.transport = AbortableStringTransport()
        self.connection = IRCClient()
        self.connection.factory = DummyFactory()
        self.connection.nickname = 'nick'
        self.connection.makeConnection(self.transport)
