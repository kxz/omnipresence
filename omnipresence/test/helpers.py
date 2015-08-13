"""Unit test helpers."""
# pylint: disable=too-few-public-methods


from functools import wraps
import gc
import os.path

from stenographer import CassetteAgent
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, maybeDeferred
from twisted.internet.task import Clock
from twisted.python.failure import Failure
from twisted.web.client import (Agent, ContentDecoderAgent,
                                RedirectAgent, GzipDecoder)
from twisted.web.test.test_agent import AbortableStringTransport
from twisted.words.protocols.irc import CHANNEL_PREFIXES

from ..connection import Connection
from ..hostmask import Hostmask
from ..message import Message, ReplyBuffer
from ..plugin import EventPlugin, UserVisibleError
from ..web.http import IdentifyingAgent


CASSETTE_LIBRARY = os.path.join(os.path.dirname(__file__),
                                'fixtures', 'cassettes')


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
# Test case mixins
#

class ConnectionTestMixin(object):
    """A test case mixin that sets up a `Connection` object before each
    test, and provides constants for mock users and channels."""

    #: A sequence of `Hostmask` objects representing mock users.
    other_users = (
        Hostmask('alice', 'athena', 'ankara.test'),
        Hostmask('bob', 'bellerophon', 'berlin.test'),
        Hostmask('charlie', 'cronus', 'chongqing.test'))

    #: A sequence of mock channel names, as strings.
    channels = ('#foo', '#bar', '&baz')

    #: Whether this test case's `Connection` should receive a sign-on
    #: event during setup.
    sign_on = True

    def setUp(self):
        super(ConnectionTestMixin, self).setUp()
        self.transport = AbortableStringTransport()
        self.connection = Connection()
        self.connection.settings.set('command_prefixes', ['!'])
        self.connection.reactor = Clock()
        self.connection.makeConnection(self.transport)
        if self.sign_on:
            # The heartbeat is started here, not in signedOn().
            self.connection.irc_RPL_WELCOME('irc.server.test', [])

    def receive(self, line):
        """Simulate receiving a line from the IRC server."""
        return self.connection._lineReceived(':{!s} {}'.format(
            self.other_users[0], line))

    def echo(self, line):
        """Simulate receiving an echoed action from the IRC server."""
        return self.connection._lineReceived(':{}!user@host {}'.format(
            self.connection.nickname, line))

    def assertLoggedErrors(self, number):
        """Assert that *number* errors have been logged."""
        # <http://stackoverflow.com/a/3252306>
        gc.collect()
        self.assertEqual(len(self.flushLoggedErrors()), number)


class CommandTestMixin(ConnectionTestMixin):
    """A subclass of `ConnectionTestMixin` that also sets up a command
    plugin in addition to a connection and transport."""

    #: The command plugin class to test.
    command_class = None

    def setUp(self):
        super(CommandTestMixin, self).setUp()
        self.default_venue = self.connection.nickname
        name = self.command_class.name
        self.keyword = name.rsplit('/', 1)[-1].rsplit('.', 1)[-1].lower()
        self.command = self.connection.settings.enable(name, [self.keyword])

    def command_message(self, content, **kwargs):
        kwargs.setdefault('actor', self.other_users[0])
        kwargs.setdefault('subaction', self.keyword)
        kwargs.setdefault('venue', self.default_venue)
        return Message(self.connection, False, 'command',
                       content=content, **kwargs)

    @inlineCallbacks
    def send_command(self, content, **kwargs):
        request = self.command_message(content, **kwargs)
        try:
            response = yield self.command.respond_to(request)
        except UserVisibleError:
            self.failure = Failure()
        else:
            self.reply_buffer = ReplyBuffer(response, request)

    def assert_reply(self, expected):
        finished = maybeDeferred(next, self.reply_buffer, None)
        finished.addCallback(self.assertEqual, expected)
        return finished

    def assert_no_replies(self):
        finished = maybeDeferred(next, self.reply_buffer, None)
        finished.addCallback(self.assertIsNone)
        return finished

    def assert_error(self, expected):
        self.assertIsNotNone(self.failure.check(UserVisibleError))
        self.assertEqual(self.failure.getErrorMessage(), expected)

    @staticmethod
    def use_cassette(cassette_name):
        cassette_path = os.path.join(CASSETTE_LIBRARY, cassette_name + '.json')
        cassette_agent = CassetteAgent(Agent(reactor), cassette_path)
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                self.command.agent = IdentifyingAgent(ContentDecoderAgent(
                    RedirectAgent(cassette_agent), [('gzip', GzipDecoder)]))
                finished = maybeDeferred(func, self, *args, **kwargs)
                finished.addCallback(cassette_agent.save)
                return finished
            return wrapper
        return decorator
