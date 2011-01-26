from zope.interface import implements

from twisted.application.service import IServiceMaker
from twisted.application import internet
from twisted.internet import ssl
from twisted.python import usage
from twisted.plugin import IPlugin

import os

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
