"""Unit test helpers."""
# pylint: disable=missing-docstring,too-few-public-methods


from base64 import b64decode, b64encode
import errno
from email.utils import formatdate
from functools import wraps
import gc
from io import BytesIO
import json
import os.path
from urlparse import urlparse, urlunparse

from twisted.internet import reactor
from twisted.internet.defer import (maybeDeferred, succeed,
                                    inlineCallbacks, returnValue)
from twisted.internet.task import Clock
from twisted.trial import unittest
from twisted.web.client import (
    FileBodyProducer, URI, readBody,
    Agent, ContentDecoderAgent, RedirectAgent, GzipDecoder)
from twisted.web.http_headers import Headers
from twisted.web.test.test_agent import AbortableStringTransport
from twisted.web._newclient import Request, Response
from twisted.words.protocols.irc import CHANNEL_PREFIXES

from .. import __version__
from ..connection import Connection
from ..hostmask import Hostmask
from ..message import Message
from ..plugin import EventPlugin, UserVisibleError
from ..web.http import IdentifyingAgent


#
# Helper objects
#

CASSETTE_LIBRARY = os.path.join(os.path.dirname(__file__),
                                'fixtures', 'cassettes')


class CassetteAgent(object):
    """A Twisted Web `Agent` that reconstructs a `Response` object from
    a recorded HTTP response in JSON-serialized VCR cassette format, or
    records a new cassette if none exists."""
    # TODO:  Split this out into its own library and give it some tests.

    version = 'Omnipresence {} Stenographer'.format(__version__)

    def __init__(self, agent, cassette_name):
        self.agent = agent
        self.interactions = []
        self.recording = True
        self.cassette_path = os.path.join(
            CASSETTE_LIBRARY, cassette_name + '.json')
        try:
            with open(self.cassette_path) as cassette_file:
                cassette = json.load(cassette_file)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise
        else:
            self.interactions = cassette['http_interactions']
            self.recording = False
            self.request = self.replay_request

    @staticmethod
    def _body_of(message):
        """Return the decoded body of a recorded *message*."""
        body = message['body']
        if 'base64_string' in body:
            return b64decode(body['base64_string'])
        return body['string'].encode(body['encoding'])

    @staticmethod
    def _make_body(string, headers=None):
        """Return a VCR-style body dict from *body_string*."""
        body = {'encoding': 'utf-8'}
        if (headers and
                'gzip' in headers.getRawHeaders('content-encoding', [])):
            body['base64_string'] = b64encode(string)
        else:
            body['string'] = string
        return body

    @inlineCallbacks
    def request(self, method, uri, headers=None, bodyProducer=None):
        """Make and record an actual HTTP request."""
        if bodyProducer:
            body_length = body_producer.length
            transport = AbortableStringTransport()
            yield body_producer.startProducing(transport)
            body_string = transport.value()
            body = CassetteAgent._make_body(body_string, headers)
            # Create a new BodyProducer that looks like the old one.
            bodyProducer = FileBodyProducer(BytesIO(body_string))
            bodyProducer.length = body_length
        else:
            body = {'encoding': 'utf-8', 'string': ''}
        rq = {
            'method': method, 'uri': uri, 'body': body,
            'headers': {k: v for k, v in headers.getAllRawHeaders()}}
        response = yield self.agent.request(method, uri, headers, bodyProducer)
        body_string = yield readBody(response)
        rp = {
            'http_version': '1.1',  # only thing Twisted Web supports
            'status': {'code': response.code, 'message': response.phrase},
            'headers': {k: v for k, v in response.headers.getAllRawHeaders()},
            'body': CassetteAgent._make_body(body_string, response.headers)}
        self.interactions.append({'request': rq, 'response': rp,
                                  'recorded_at': formatdate()})
        # Make a new Response on which deliverBody can still be called,
        # and return that instead of the original Response.
        response = Response._construct(
            response.version, response.code, response.phrase,
            response.headers, AbortableStringTransport(), response.request)
        response._bodyDataReceived(body_string)
        response._bodyDataFinished()
        returnValue(response)

    def replay_request(self, method, uri, headers=None, bodyProducer=None):
        """Replay a recorded HTTP request.  Raise `IOError` if the
        recorded request does not match the one being made, like VCR's
        ``once`` record mode."""
        try:
            interaction = self.interactions.pop(0)
        except IndexError:
            raise IOError('no more saved interactions for current {} '
                          'request for {}'.format(method, uri))
        rq = interaction['request']
        # TODO:  Implement looser request matching.
        if not (method == rq['method'] and uri == rq['uri']):
            raise IOError('current {} request for {} differs from '
                          'saved {} request for {}'.format(
                method, uri, rq['method'], rq['uri']))
        # Overwrite the scheme and netloc, leaving just the part of the
        # URI that would be sent in a real request.
        relative_uri = urlunparse(('', '') + urlparse(rq['uri'])[2:])
        request = Request._construct(
            rq['method'], relative_uri, Headers(rq['headers']),
            FileBodyProducer(BytesIO(CassetteAgent._body_of(rq))),
            False, URI.fromBytes(rq['uri'].encode('utf-8')))
        rp = interaction['response']
        response = Response._construct(
            ('HTTP', 1, 1), rp['status']['code'], rp['status']['message'],
            Headers(rp['headers']), AbortableStringTransport(), request)
        response._bodyDataReceived(CassetteAgent._body_of(rp))
        response._bodyDataFinished()
        return succeed(response)

    def save(self):
        if not self.recording:
            return
        cassette = {'http_interactions': self.interactions,
                    'recorded_with': self.version}
        with open(self.cassette_path, 'w') as cassette_file:
            json.dump(cassette, cassette_file)


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

    def send_command(self, *args, **kwargs):
        return maybeDeferred(self.command.respond_to,
                             self.command_message(*args, **kwargs))

    def assert_reply(self, content, expected, **kwargs):
        deferred = self.send_command(content, **kwargs)
        deferred.addCallback(self.assertEqual, expected)
        return deferred

    def assert_error(self, content, expected, **kwargs):
        deferred = self.send_command(content, **kwargs)
        failed = self.assertFailure(deferred, UserVisibleError)
        failed.addCallback(lambda e: self.assertEqual(str(e), expected))
        return failed


class AbstractCassetteTestCase(AbstractCommandTestCase):
    @staticmethod
    def use_cassette(cassette_name):
        cassette_agent = CassetteAgent(Agent(reactor), cassette_name)

        def save_cassette(result):
            cassette_agent.save()
            return result

        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                self.command.agent = IdentifyingAgent(ContentDecoderAgent(
                    RedirectAgent(cassette_agent), [('gzip', GzipDecoder)]))
                finished = maybeDeferred(func, self, *args, **kwargs)
                finished.addBoth(save_cassette)
                return finished
            return wrapper

        return decorator
