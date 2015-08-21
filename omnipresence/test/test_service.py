"""Unit tests for Twisted services."""
# pylint: disable=missing-docstring,too-few-public-methods


import os.path
from signal import signal, getsignal, SIGUSR1

from twisted.internet import ssl
from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase

from ..service import Options, SSLBotService, TCPBotService, makeService


class DummyConnection(object):
    def __init__(self):
        self.has_quit = False

    def quit(self):
        self.has_quit = True


class DummyFactory(object):
    def __init__(self, protocol):
        self.protocol = protocol

    def buildProtocol(self):
        return self.protocol

    @property
    def protocols(self):
        return [self.protocol]


class GracefulShutdownTestCase(TestCase):
    def setUp(self):
        self.connection = DummyConnection()
        self.factory = DummyFactory(self.connection)

    def assert_service_quit(self, service_class, *args):
        self.service = service_class(*args)
        self.service.reactor = Clock()
        finished = self.service.stopService()
        self.service.reactor.advance(5)
        finished.addCallback(
            lambda _: self.assertTrue(self.connection.has_quit))
        return finished

    def test_ssl_client(self):
        return self.assert_service_quit(
            SSLBotService, '127.0.0.1', 6667, self.factory,
            ssl.ClientContextFactory())

    def test_tcp_client(self):
        return self.assert_service_quit(
            TCPBotService, '127.0.0.1', 6667, self.factory)


class ServiceMakerTestCase(TestCase):
    def setUp(self):
        self.old_signal_handler = getsignal(SIGUSR1)

    @staticmethod
    def options(settings_name):
        opts = Options()
        opts.parseArgs(os.path.join(
            os.path.dirname(__file__), 'fixtures', 'settings',
            settings_name + '.yaml'))
        return opts

    def test_nonexistent(self):
        self.assertRaises(SystemExit, makeService, self.options(''))

    def test_blank(self):
        self.assertRaises(SystemExit, makeService, self.options('blank'))

    def test_invalid(self):
        self.assertRaises(SystemExit, makeService, self.options('invalid'))

    def test_minimal(self):
        service = makeService(self.options('minimal'))
        self.assertIsInstance(service, TCPBotService)

    def test_ssl(self):
        service = makeService(self.options('ssl'))
        self.assertIsInstance(service, SSLBotService)

    def tearDown(self):
        if self.old_signal_handler is not None:
            signal(SIGUSR1, self.old_signal_handler)
