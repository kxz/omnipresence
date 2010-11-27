from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import IHandler

from twisted.python import log

import logging
import logging.handlers
import os
import time

MESSAGE_FORMAT = '[%(asctime)s]  %(message)s'
DATE_FORMAT = '%d-%b-%Y %H:%M:%S'


class ChannelLogger(object):
    implements(IPlugin, IHandler)
    name = 'chanlog'
    
    handlers = {}
    # Hold on to our own hostmask, because we don't get one when we quit.
    hostmask = ''
    
    def log(self, channel, msg, args):
        if channel not in self.handlers:
            return
        
        self.handlers[channel].emit(logging.LogRecord('chanlog',
                                                      logging.NOTSET, __file__,
                                                      0, msg, args, None))
    
    def registered(self):
        self.log_directory = self.factory.config.get('chanlog', 'directory')
    
    def connectionLost(self, bot, reason):
        self.quit(bot, reason.getErrorMessage() if reason else None)
        
    def privmsg(self, bot, user, channel, message):
        user = user.split('!', 1)[0]
        self.log(channel, '<%s> %s', (user, message))
        
    def joined(self, bot, prefix, channel):
        handler = logging.handlers.WatchedFileHandler(os.path.join(self.log_directory, channel))
        handler.setFormatter(logging.Formatter(MESSAGE_FORMAT, DATE_FORMAT))
        self.handlers[channel] = handler
        
        nick, hostmask = prefix.split('!', 1)
        self.hostmask = hostmask
        self.log(channel, '*** %s <%s> has joined %s',
                 (bot.nickname, hostmask, channel))
        log.msg('Starting logging for channel %s.' % channel)
    
    def left(self, bot, prefix, channel):
        self.log(channel, '*** %s <%s> has left %s',
                 (bot.nickname, channel))
        log.msg('Stopping logging for channel %s.' % channel)
        del self.handlers[channel]
    
    def noticed(self, bot, user, channel, message):
        user = user.split('!', 1)[0]
        self.log(channel, '-%s- %s', (user, message))
    
    def modeChanged(self, bot, user, channel, set, modes, args):
        user = user.split('!', 1)[0]
        flag = '+' if set else '-'
        self.log(channel, '*** %s sets mode: %s%s %s',
                 (user, flag, modes, ' '.join(args)))
    
    def kickedFrom(self, bot, channel, kicker, message):
        self.userKicked(bot, self.nickname, channel, kicker, message)
        log.msg('Stopping logging for channel %s.' % channel)
        del self.handlers[channel]
    
    def nickChanged(self, bot, nick):
        self.userRenamed(bot, self.nickname, nick)
    
    def userJoined(self, bot, user, channel):
        nick, hostmask = user.split('!', 1)
        self.log(channel, '*** %s <%s> has joined %s',
                 (nick, hostmask, channel))
    
    def userLeft(self, bot, user, channel):
        nick, hostmask = user.split('!', 1)
        self.log(channel, '*** %s <%s> has left %s', (nick, hostmask, channel))
    
    def userQuit(self, bot, user, quitMessage):
        nick, hostmask = user.split('!', 1)
        for channel in bot.channel_names:
            if nick in bot.channel_names[channel]:
                if quitMessage:
                    self.log(channel, '*** %s <%s> has quit IRC (%s)',
                             (nick, hostmask, quitMessage))
                else:
                    self.log(channel, '*** %s <%s> has quit IRC',
                             (nick, hostmask))

    def userKicked(self, bot, kickee, channel, kicker, message):
        kickee = kickee.split('!', 1)[0]
        kicker = kicker.split('!', 1)[0]
        
        if message:
            self.log(channel, '*** %s was kicked by %s (%s)',
                     (kickee, kicker, message))
        else:
            self.log(channel, '*** %s was kicked by %s', (kickee, kicker))

    def action(self, bot, user, channel, data):
        user = user.split('!', 1)[0]
        self.log(channel, '* %s %s', (user, data))

    def topicUpdated(self, bot, user, channel, newTopic):
        user = user.split('!', 1)[0]
        self.log(channel, '*** %s changes topic to %s', (user, newTopic))
    
    def userRenamed(self, bot, oldname, newname):
        for channel in bot.channel_names:
            if oldname in bot.channel_names[channel]:
                self.log(channel, '*** %s is now known as %s',
                         (oldname, newname))

    def kick(self, bot, channel, user, reason):
        self.userKicked(bot, user, channel, bot.nickname, reason)

    def topic(self, bot, channel, topic):
        if topic is not None:
            self.topicUpdated(bot, bot.nickname, channel, topic)
    
    def mode(self, bot, chan, set, modes, limit, user, mask):
        args = []
        
        if limit is not None:
            args.append(limit)
        elif user is not None:
            args.append(user)
        elif mask is not None:
            args.append(mask)
        
        self.modeChanged(bot, bot.nickname, chan, set, modes, args)
    
    def msg(self, bot, user, message):
        self.privmsg(bot, bot.nickname, user, message)

    def notice(self, bot, user, message):
        self.noticed(bot, bot.nickname, user, message)
    
    def setNick(self, bot, nickname):
        self.userRenamed(bot, bot.nickname, nickname)
    
    def quit(self, bot, message):
        self.userQuit(bot, bot.nickname + '!' + self.hostmask, message)
        log.msg('Stopping logging for all channels.')
        self.handlers = {}
    
    def me(self, bot, channel, action):
        self.action(bot, bot.nickname, channel, action)


channellogger = ChannelLogger()