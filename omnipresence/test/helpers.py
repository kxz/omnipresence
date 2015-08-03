"""Unit test helpers."""
# pylint: disable=missing-docstring,too-few-public-methods


import gc

from twisted.internet.task import Clock
from twisted.trial import unittest
from twisted.web.test.test_agent import AbortableStringTransport
from twisted.words.protocols.irc import CHANNEL_PREFIXES

from ..connection import Connection
from ..hostmask import Hostmask
from ..message import Message
from ..plugin import EventPlugin, UserVisibleError


#
# Helper objects
#

class DummyConnection(object):
    """A class that simulates the behavior of a live connection."""

    def is_channel(self, venue):
        return venue[0] in CHANNEL_PREFIXES


#
# Basic event plugins
#

class NoticingPlugin(EventPlugin):
    """An event plugin that caches incoming events."""

    def __init__(self):
        self.seen = []

    def on_privmsg(self, msg):
        self.seen.append(msg)

    on_connected = on_disconnected = on_privmsg
    on_command = on_notice = on_join = on_quit = on_privmsg

    @property
    def last_seen(self):
        return self.seen[-1]


class OutgoingPlugin(NoticingPlugin):
    """An event plugin that caches incoming and outgoing events."""

    def on_privmsg(self, msg):
        super(OutgoingPlugin, self).on_privmsg(msg)
    on_privmsg.outgoing = True

    on_command = on_notice = on_join = on_quit = on_privmsg


#
# Abstract test cases
#

class AbstractConnectionTestCase(unittest.TestCase):
    other_user = Hostmask('other', 'user', 'host')
    sign_on = True

    def setUp(self):
        self.transport = AbortableStringTransport()
        self.connection = Connection()
        self.connection.settings.set('command_prefixes', ['!'])
        self.connection.reactor = Clock()
        self.connection.makeConnection(self.transport)
        if self.sign_on:
            # The heartbeat is started here, not in signedOn().
            self.connection.irc_RPL_WELCOME('remote.test', [])

    def receive(self, line):
        """Simulate receiving a line from the IRC server."""
        return self.connection._lineReceived(':{!s} {}'.format(
            self.other_user, line))

    def echo(self, line):
        """Simulate receiving an echoed action from the IRC server."""
        return self.connection._lineReceived(':{}!user@host {}'.format(
            self.connection.nickname, line))

    def assertLoggedErrors(self, number):
        """Assert that *number* errors have been logged."""
        # <http://stackoverflow.com/a/3252306>
        gc.collect()
        self.assertEqual(len(self.flushLoggedErrors()), number)


class AbstractCommandTestCase(AbstractConnectionTestCase):
    command_class = None

    def setUp(self):
        super(AbstractCommandTestCase, self).setUp()
        self.default_venue = self.connection.nickname
        name = self.command_class.name
        self.keyword = name.rsplit('/', 1)[-1].rsplit('.', 1)[-1].lower()
        self.command = self.connection.settings.enable(name, [self.keyword])

    def command_message(self, content, **kwargs):
        kwargs.setdefault('actor', self.other_user)
        kwargs.setdefault('subaction', self.keyword)
        kwargs.setdefault('venue', self.default_venue)
        return Message(self.connection, False, 'command',
                       content=content, **kwargs)

    def assert_reply(self, content, expected, **kwargs):
        msg = self.command_message(content, **kwargs)
        self.assertEqual(self.command.respond_to(msg), expected)

    def assert_error(self, content, expected, **kwargs):
        msg = self.command_message(content, **kwargs)
        e = self.assertRaises(UserVisibleError, self.command.respond_to, msg)
        self.assertEqual(str(e), expected)
