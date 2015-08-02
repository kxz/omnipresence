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
    def parseArgs(self, settings_path):
        self['settings_path'] = settings_path


def makeService(options):
    """Return a Twisted service object attaching a `ConnectionFactory`
    instance to an appropriate TCP or SSL transport."""
    factory = ConnectionFactory()
    with open(options['settings_path']) as settings_file:
        settings = ConnectionSettings.from_yaml(settings_file)
    factory.settings = settings
    if settings.ssl:
        return SSLClient(settings.host, settings.port, factory,
                         ssl.ClientContextFactory())
    return TCPClient(settings.host, settings.port, factory)
