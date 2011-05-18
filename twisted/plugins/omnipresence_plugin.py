import locale
import os

from twisted.application import internet
from twisted.application.service import IServiceMaker
from twisted.internet import ssl
from twisted.plugin import IPlugin
from twisted.python import usage
from zope.interface import implements

from omnipresence import IRCClientFactory
from omnipresence.config import OmnipresenceConfigParser


class Options(usage.Options):
    def parseArgs(self, config_file):
        self['config_file'] = config_file


class ServiceMaker(object):
    implements(IPlugin, IServiceMaker)
    tapname = 'omnipresence'
    description = 'Omnipresence IRC utility bot.'
    options = Options

    def makeService(self, options):
        """
        Construct a TCP or SSL client from IRCClientFactory, using the options 
        in the given configuration file.
        """

        locale.setlocale(locale.LC_ALL, '')

        config = OmnipresenceConfigParser()
        config.read(os.path.join(os.getcwd(), options['config_file']))
        
        factory = IRCClientFactory(config)

        server = config.get('core', 'server')
        port = config.getint('core', 'port')

        if config.getboolean('core', 'ssl'):
            contextFactory = ssl.ClientContextFactory()
            return internet.SSLClient(server, port, factory, contextFactory)

        return internet.TCPClient(server, port, factory)


serviceMaker = ServiceMaker()
