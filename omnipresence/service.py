"""Twisted service definitions."""
# Twisted and pylint get along like oil and water:
#
# pylint: disable=arguments-differ,invalid-name,missing-docstring
# pylint: disable=no-name-in-module,too-few-public-methods


from signal import signal, SIGUSR1

from twisted.application.internet import SSLClient, TCPClient
from twisted.internet import reactor, ssl
from twisted.python import usage

from .connection import ConnectionFactory
from .settings import ConnectionSettings


class Options(usage.Options):
    def parseArgs(self, settings_path):
        self['settings_path'] = settings_path


def makeService(options):
    """Return a Twisted service object attaching a `ConnectionFactory`
    instance to an appropriate TCP or SSL transport."""
    factory = ConnectionFactory()
    def reload_settings(signum=None, frame=None):
        with open(options['settings_path']) as settings_file:
            factory.settings = ConnectionSettings.from_yaml(settings_file)
            reactor.callFromThread(factory.reload_settings)
    reload_settings()
    signal(SIGUSR1, reload_settings)
    if factory.settings.ssl:
        return SSLClient(factory.settings.host, factory.settings.port,
                         factory, ssl.ClientContextFactory())
    return TCPClient(factory.settings.host, factory.settings.port, factory)
