from twisted.plugin import IPlugin
from twisted.python import log
from zope.interface import implements

from omnipresence.iomnipresence import IHandler


class AutoRejoiner(object):
    implements(IPlugin, IHandler)
    name = 'autorejoin'

    def kickedFrom(self, bot, channel, kicker, message):
        log.msg('Kicked from channel %s by %s; attempting to auto-rejoin.'
                 % (channel, kicker))
        bot.join(channel)


autorejoin = AutoRejoiner()
