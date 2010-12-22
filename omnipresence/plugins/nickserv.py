from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import IHandler

from twisted.internet import reactor
from twisted.python import log
from twisted.words.protocols import irc

import re

class NickServHandler(object):
    implements(IPlugin, IHandler)
    name = 'nickserv'

    nick_change_call = None
    signed_on = False
    reset_at_signon = False

    def registered(self):
        # Grab some options from the configuration file.
        self.configured_nick = self.factory.config.get('core', 'nickname')
        self.password = self.factory.config.get('nickserv', 'password')

        self.suspend_joins = self.factory.config.getboolean('nickserv', 'suspend_joins')
        self.kill_ghosts = self.factory.config.getboolean('nickserv', 'kill_ghosts')

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
        if self.reset_at_signon:
            self.reset_nick(bot)

    def noticed(self, bot, prefix, channel, message):
        # Make sure that this is a private notice coming from NickServ.
        if channel[0] in irc.CHANNEL_PREFIXES or prefix != self.mask:
            return

        if self.identify_re.search(message):
            # We're being asked to identify for this nick by NickServ, so send 
            # it our password.
            log.msg('Received NickServ authentication request; sending password.')
            bot.msg(prefix.split('!', 1)[0], 'identify %s' % self.password)
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

            if self.nick_change_call:
                self.nick_change_call.cancel()

            bot.setNick(self.configured_nick)
            return

    def irc_ERR_NICKNAMEINUSE(self, bot):
        # The bot's usual nick is in use by someone else.  If ghost-killing is 
        # enabled, ask NickServ to ghost the other user after we've finished 
        # signing on.
        log.msg('Nick in use by another user.')
        if self.signed_on:
            self.reset_nick(bot)
        else:
            self.reset_at_signon = True

    def reset_nick(self, bot):
        if self.kill_ghosts:
            log.msg('Asking NickServ to kill ghost with configured nick.')
            bot.msg(self.mask.split('!', 1)[0],
                    'ghost %s %s' % (self.configured_nick, self.password))
       
        log.msg('Changing to configured nick in 10 seconds.')
        self.nick_change_call = reactor.callLater(10, bot.setNick,
                                                  self.configured_nick)


nickservhandler = NickServHandler()
