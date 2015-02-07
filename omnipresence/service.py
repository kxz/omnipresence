"""Twisted service definitions."""
# Twisted and pylint get along like oil and water:
#
# pylint: disable=arguments-differ,invalid-name,missing-docstring
# pylint: disable=no-name-in-module,too-few-public-methods


import os

from twisted.application.internet import SSLClient, TCPClient
from twisted.internet import ssl
from twisted.python import usage

from .config import ConfigParser
from .connection import ConnectionFactory


class Options(usage.Options):
    def parseArgs(self, config_path):
        self['config_path'] = config_path


def makeService(options):
    """Return a Twisted service object attaching a `ConnectionFactory`
    instance to an appropriate TCP or SSL transport."""
    config = ConfigParser()
    config.read(os.path.join(os.getcwd(), options['config_path']))
    factory = ConnectionFactory(config)
    server = config.get('core', 'server')
    port = config.getint('core', 'port')
    if config.getboolean('core', 'ssl'):
        return SSLClient(server, port, factory, ssl.ClientContextFactory())
    return TCPClient(server, port, factory)
