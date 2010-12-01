from twisted.plugin import IPlugin
from twisted.python import log
from zope.interface import implements

from omnipresence import util
from omnipresence.iomnipresence import IHandler


class AutoVoicer(object):
    implements(IPlugin, IHandler)
    name = 'autovoice'
    
    moderated = {}

    def joined(self, bot, prefix, channel):
        self.moderated[channel] = False

    def modeChanged(self, bot, user, channel, set, modes, args):
        if 'm' in modes:
            if set:
                log.msg('%s enabled channel moderation on %s.'
                         % (user, channel))
                self.moderated[channel] = True
            else:
                log.msg('%s disabled channel moderation on %s.'
                         % (user, channel))
                self.moderated[channel] = False

    def userJoined(self, bot, user, channel):
        if not self.moderated[channel]:
            user = user.split('!', 1)[0]
            log.msg('Attempting to voice %s on channel %s.' % (user, channel))
            bot.mode(channel, True, 'v', user=user)
            

autovoice = AutoVoicer()