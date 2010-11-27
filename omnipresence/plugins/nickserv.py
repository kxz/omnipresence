from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import IHandler

from twisted.internet import reactor
from twisted.python import log

import re

class NickServHandler(object):
    implements(IPlugin, IHandler)
    name = 'nickserv'

    signed_on = False
    nick_in_use = False

    def registered(self):
        # Grab some options from the configuration file.
        self.configured_nick = self.factory.config.get('core', 'nickname')
        self.password = self.factory.config.get('nickserv', 'password')

        self.suspend_joins = self.factory.config.getboolean('nickserv', 'suspend_joins')
        self.kill_ghosts = self.factory.config.getboolean('nickserv', 'kill_ghosts')
        self.change_when_available = self.factory.config.getboolean('nickserv', 'change_when_available')

        self.mask = self.factory.config.get('nickserv', 'mask')
        self.identify_re = re.compile(self.factory.config.get('nickserv', 'identify_re'))
        self.identified_re = re.compile(self.factory.config.get('nickserv', 'identified_re'))

        if self.kill_ghosts:
            self.ghost_killed_re = re.compile(self.factory.config.get('nickserv', 'ghost_killed_re'))

    def connectionMade(self, bot):
        if self.suspend_joins:
            bot.suspend_joins()

    def signedOn(self, bot):
        self.signed_on = True

        if self.nick_in_use and self.kill_ghosts:
            log.msg('Asking NickServ to kill ghost with configured nick.')
            bot.msg(self.mask.split('!', 1)[0],
                    'ghost %s %s' % (self.configured_nick, self.password))

    def noticed(self, bot, user, channel, message):
        # Make sure that this is a private notice coming from NickServ.
        if not (channel == bot.nickname and user == self.mask):
            return

        if self.identify_re.search(message):
            # We're being asked to identify for this nick by NickServ, so send 
            # it our password.
            log.msg('Received NickServ authentication request; sending password.')
            bot.msg(user.split('!', 1)[0], 'identify %s' % self.password)
            return

        if self.identified_re.search(message):
            # We've successfully identified to the server, so we can now join 
            # channels as usual.
            log.msg('Successfully identified to NickServ.')
            bot.resume_joins()
            return

        if self.kill_ghosts and self.ghost_killed_re.search(message):
            # We've gotten the ghost out of the way, so change to our usual 
            # nick and wait for an authentication request.
            log.msg('Successfully killed ghost; changing nick.')
            self.reset_nick(bot)
            return

    def irc_ERR_NICKNAMEINUSE(self, bot):
        # The bot's usual nick is in use by someone else.  If ghost-killing is 
        # enabled, ask NickServ to ghost the other user after we've finished 
        # signing on.  If polling for nick availability is enabled, try to 
        # reset our nick.
        log.msg('Nick in use by another user.')
        if self.kill_ghosts:
            if self.signed_on:
                self.reset_nick(bot)
            else:
                self.nick_in_use = True
        elif self.change_when_available:
            self.reset_nick(bot)

    def reset_nick(self, bot):
        if bot.nickname != self.configured_nick:
            bot.setNick(self.configured_nick)
            if self.change_when_available:
                reactor.callLater(60, self.reset_nick)


nickservhandler = NickServHandler()
