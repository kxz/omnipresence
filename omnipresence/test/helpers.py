"""Unit test helpers."""
# pylint: disable=missing-docstring,too-few-public-methods


import gc

from twisted.internet.task import Clock
from twisted.test.proto_helpers import StringTransport
from twisted.trial import unittest
from twisted.words.protocols.irc import CHANNEL_PREFIXES

from ..config import ConfigParser
from ..connection import Connection
from ..hostmask import Hostmask


#
# Helper objects
#

class AbortableStringTransport(StringTransport):
    """A StringTransport that supports abortConnection()."""
    # <https://twistedmatrix.com/trac/ticket/6530>

    def abortConnection(self):
        self.loseConnection()


class DummyFactory(object):
    """A class that simulates the behavior of a ConnectionFactory."""
    # TODO:  Refactor Connection so that this isn't necessary for
    # connection tests.

    def __init__(self):
        self.config = ConfigParser()
        self.config.add_section('core')
        self.config.set('core', 'database', 'sqlite:/:memory:')
        self.config.set('core', 'command_prefixes', '!')
        self.config.add_section('channels')
        self.encoding = 'utf-8'

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
    other_user = Hostmask('other', 'user', 'host')
    sign_on = True

    def setUp(self):
        self.transport = AbortableStringTransport()
        self.connection = Connection(DummyFactory())
        self.connection.reactor = Clock()
        self.connection.makeConnection(self.transport)
        if self.sign_on:
            # The heartbeat is started here, not in signedOn().
            self.connection.irc_RPL_WELCOME('remote.test', [])

    def receive(self, line):
        """Simulate receiving a line from the IRC server."""
        return self.connection.lineReceived(':{!s} {}'.format(
            self.other_user, line))

    def echo(self, line):
        """Simulate receiving an echoed action from the IRC server."""
        return self.connection.lineReceived(':{}!user@host {}'.format(
            self.connection.nickname, line))

    def assertLoggedErrors(self, number):
        """Assert that *number* errors have been logged."""
        # <http://stackoverflow.com/a/3252306>
        gc.collect()
        self.assertEqual(len(self.flushLoggedErrors()), number)
