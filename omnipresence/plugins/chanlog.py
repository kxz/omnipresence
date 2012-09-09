from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import IHandler

from twisted.python import log

import logging
import logging.handlers
import os
import time

from omnipresence import ircutil

MESSAGE_FORMAT = '[%(asctime)s]  %(message)s'
DATE_FORMAT = '%d-%b-%Y %H:%M:%S'


class ChannelLogger(object):
    implements(IPlugin, IHandler)
    name = 'chanlog'

    handlers = None
    # Hold on to our own hostmask, because we don't get one when we quit.
    hostmask = None

    def __init__(self):
        self.handlers = {}
        self.hostmask = ''

    def log(self, channel, msg, args):
        channel = ircutil.canonicalize(channel)

        if channel not in self.handlers:
            return

        self.handlers[channel].emit(logging.LogRecord('chanlog',
                                                      logging.NOTSET, __file__,
                                                      0, msg, args, None))

    def registered(self):
        self.log_directory = self.factory.config.get('chanlog', 'directory')

    def connectionLost(self, bot, reason):
        self.quit(bot, reason.getErrorMessage() if reason else None)

    def privmsg(self, bot, prefix, channel, message):
        nick = prefix.split('!', 1)[0]
        self.log(channel, '<%s> %s', (nick, message))

    def joined(self, bot, prefix, channel):
        handler = logging.handlers.WatchedFileHandler(
                      os.path.join(self.log_directory,
                                   ircutil.canonicalize(channel)[1:]))
        handler.setFormatter(logging.Formatter(MESSAGE_FORMAT, DATE_FORMAT))
        self.handlers[ircutil.canonicalize(channel)] = handler

        nick, hostmask = prefix.split('!', 1)
        self.hostmask = hostmask
        self.log(channel, '*** %s <%s> has joined %s',
                 (bot.nickname, hostmask, channel))
        log.msg('Starting logging for channel %s.' % channel)

    def left(self, bot, prefix, channel):
        self.log(channel, '*** %s <%s> has left %s',
                 (bot.nickname, self.hostmask, channel))
        log.msg('Stopping logging for channel %s.' % channel)
        del self.handlers[ircutil.canonicalize(channel)]

    def noticed(self, bot, prefix, channel, message):
        nick = prefix.split('!', 1)[0]
        self.log(channel, '-%s- %s', (nick, message))

    def modeChanged(self, bot, prefix, channel, set, modes, args):
        nick = prefix.split('!', 1)[0]
        self.log(channel, '*** %s sets mode: %s',
                 (nick, ircutil.mode_string(set, modes, args)))

    def kickedFrom(self, bot, channel, kicker, message):
        self.userKicked(bot, bot.nickname, channel, kicker, message)
        log.msg('Stopping logging for channel %s.' % channel)
        del self.handlers[ircutil.canonicalize(channel)]

    def nickChanged(self, bot, nick):
        self.userRenamed(bot, bot.nickname, nick)

    def userJoined(self, bot, prefix, channel):
        nick, hostmask = prefix.split('!', 1)
        self.log(channel, '*** %s <%s> has joined %s',
                 (nick, hostmask, channel))

    def userLeft(self, bot, prefix, channel):
        nick, hostmask = prefix.split('!', 1)
        self.log(channel, '*** %s <%s> has left %s', (nick, hostmask, channel))

    def userQuit(self, bot, prefix, quitMessage):
        nick, hostmask = prefix.split('!', 1)
        for channel in bot.channel_names:
            if nick in bot.channel_names[channel]:
                if quitMessage:
                    self.log(channel, '*** %s <%s> has quit IRC (%s)',
                             (nick, hostmask, quitMessage))
                else:
                    self.log(channel, '*** %s <%s> has quit IRC',
                             (nick, hostmask))

    def userKicked(self, bot, kickee, channel, kicker, message):
        if message:
            self.log(channel, '*** %s was kicked by %s (%s)',
                     (kickee, kicker, message))
        else:
            self.log(channel, '*** %s was kicked by %s', (kickee, kicker))

    def action(self, bot, prefix, channel, data):
        nick = prefix.split('!', 1)[0]
        self.log(channel, '* %s %s', (nick, data))

    def topicUpdated(self, bot, nick, channel, newTopic):
        self.log(channel, '*** %s changes topic to %s', (nick, newTopic))

    def userRenamed(self, bot, oldname, newname):
        for channel in bot.channel_names:
            if oldname in bot.channel_names[channel]:
                self.log(channel, '*** %s is now known as %s',
                         (oldname, newname))

    def kick(self, bot, channel, nick, reason):
        self.userKicked(bot, nick, channel, bot.nickname, reason)

    def topic(self, bot, channel, topic):
        # Topic changes get echoed back to us by the server, which
        # triggers topicUpdated above, so we don't log them here.
        pass

    def mode(self, bot, chan, set, modes, limit, user, mask):
        # Same as with topics; modeChanged gets called on the echo.
        pass

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
