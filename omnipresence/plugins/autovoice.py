from twisted.plugin import IPlugin
from twisted.python import log
from zope.interface import implements

from omnipresence.iomnipresence import IHandler


class AutoVoicer(object):
    implements(IPlugin, IHandler)
    name = 'autovoice'

    def __init__(self):
        self.moderated = {}

    def joined(self, bot, prefix, channel):
        self.moderated[channel] = False

    def modeChanged(self, bot, prefix, channel, set, modes, args):
        nick = prefix.split('!', 1)[0]
        if 'm' in modes:
            if set:
                log.msg('%s enabled channel moderation on %s.'
                         % (nick, channel))
                self.moderated[channel] = True
            else:
                log.msg('%s disabled channel moderation on %s.'
                         % (nick, channel))
                self.moderated[channel] = False

    def userJoined(self, bot, prefix, channel):
        if not self.moderated[channel]:
            nick = prefix.split('!', 1)[0]
            log.msg('Attempting to voice %s on channel %s.' % (nick, channel))
            bot.mode(channel, True, 'v', user=nick)


autovoice = AutoVoicer()
