"""Twisted service definitions."""
# Twisted and pylint get along like oil and water:
#
# pylint: disable=arguments-differ,invalid-name,missing-docstring
# pylint: disable=no-name-in-module,too-few-public-methods


import os

from twisted.application.internet import SSLClient, TCPClient
from twisted.internet import ssl
from twisted.python import usage

from .connection import ConnectionFactory
from .settings import ConnectionSettings


class Options(usage.Options):
    def parseArgs(self, config_path):
        self['config_path'] = config_path


def makeService(options):
    """Return a Twisted service object attaching a `ConnectionFactory`
    instance to an appropriate TCP or SSL transport."""
    factory = ConnectionFactory()
    settings = ConnectionSettings.from_yaml(options['config_path'])
    factory.settings = settings
    if settings.ssl:
        return SSLClient(settings.server, settings.port, factory,
                         ssl.ClientContextFactory())
    return TCPClient(settings.server, settings.port, factory)
