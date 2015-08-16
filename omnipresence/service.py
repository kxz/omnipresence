"""Twisted service definitions."""
# Twisted and pylint get along like oil and water:
#
# pylint: disable=arguments-differ,invalid-name,missing-docstring
# pylint: disable=no-name-in-module,too-few-public-methods


from signal import signal, SIGUSR1

from twisted.application.internet import SSLClient, TCPClient
from twisted.internet import reactor, ssl
from twisted.python import usage
import yaml

from .connection import ConnectionFactory
from .settings import ConnectionSettings


class Options(usage.Options):
    def parseArgs(self, settings_path):
        self['settings_path'] = settings_path


def makeService(options):
    """Return a Twisted service object attaching a `ConnectionFactory`
    instance to an appropriate TCP or SSL transport."""
    factory = ConnectionFactory()
    def reload_settings():
        with open(options['settings_path']) as settings_file:
            factory.reload_settings(yaml.load(settings_file))
    reload_settings()
    signal(SIGUSR1, lambda s, f: reactor.callFromThread(reload_settings))
    if factory.settings.ssl:
        return SSLClient(factory.settings.host, factory.settings.port,
                         factory, ssl.ClientContextFactory())
    return TCPClient(factory.settings.host, factory.settings.port, factory)
