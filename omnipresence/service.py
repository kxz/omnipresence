"""Twisted service definitions."""
# Twisted and pylint get along like oil and water:
#
# pylint: disable=arguments-differ,invalid-name,missing-docstring
# pylint: disable=no-name-in-module,too-few-public-methods


from signal import signal, SIGUSR1
import sys

from twisted.application.internet import SSLClient, TCPClient
from twisted.internet import reactor, ssl
from twisted.internet.task import deferLater
from twisted.python import usage
import yaml

from .connection import ConnectionFactory


def indent(string):
    return '\n'.join('    ' + line for line in string.splitlines())


#
# Service classes
#

class GracefulShutdownMixin(object):
    """A service mixin that sends an IRC quit message on stop."""

    def __init__(self, host, port, factory, *args, **kwargs):
        super(GracefulShutdownMixin, self).__init__(
            host, port, factory, *args, **kwargs)
        self.factory = factory
        self.reactor = reactor

    def stopService(self):
        for protocol in self.factory.protocols:
            protocol.quit()
        return deferLater(self.reactor, 1,
                          super(GracefulShutdownMixin, self).stopService)


class SSLBotService(GracefulShutdownMixin, SSLClient):
    pass


class TCPBotService(GracefulShutdownMixin, TCPClient):
    pass


#
# ServiceMaker hooks
#

class Options(usage.Options):
    longdesc = ('Pass the path to the Omnipresence settings file as '
                'the sole argument.')

    def parseArgs(self, settings_path):
        self['settings_path'] = settings_path


def makeService(options):
    """Return a Twisted service object attaching a `ConnectionFactory`
    instance to an appropriate TCP or SSL transport."""
    factory = ConnectionFactory()
    def reload_settings():
        with open(options['settings_path']) as settings_file:
            factory.reload_settings(yaml.load(settings_file))
    try:
        reload_settings()
    except IOError:
        sys.exit('The given settings file does not exist or cannot be '
                 'opened.\nPlease check the path and try again.')
    except (TypeError, ValueError, yaml.parser.ParserError) as e:
        sys.exit('There was a problem parsing the settings file:\n{}\n'
                 'Please check your configuration and try again.'
                 .format(indent(str(e))))
    if factory.settings.host is None:
        sys.exit('The "host" directive is missing from the settings '
                 'file.\nPlease check your configuration and try again.')
    signal(SIGUSR1, lambda s, f: reactor.callFromThread(reload_settings))
    if factory.settings.ssl:
        return SSLBotService(factory.settings.host, factory.settings.port,
                             factory, ssl.ClientContextFactory())
    return TCPBotService(factory.settings.host, factory.settings.port, factory)
