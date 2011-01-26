from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand, IHandler

import sqlobject

from omnipresence import ircutil, util


class ChannelPeak(sqlobject.SQLObject):
    channel = sqlobject.StringCol(notNone=True, length=64)
    number_of_users = sqlobject.IntCol(notNone=True)
    timestamp = sqlobject.DateTimeCol(notNone=True,
                                      default=sqlobject.DateTimeCol.now)
    joiner = sqlobject.StringCol(notNone=True, length=64)


class PeakHandler(object):
    implements(IPlugin, IHandler)
    name = 'peak'
    
    def registered(self):
        ChannelPeak.createTable(ifNotExists=True)
    
    def _add_record(self, bot, prefix, channel):
        canonicalized_channel = ircutil.canonicalize(channel)
        
        if canonicalized_channel not in bot.channel_names:
            return
        
        number_of_users = len(bot.channel_names[canonicalized_channel])
        
        if prefix is None:
            # We were called via endNames, so assume the bot just joined.
            prefix = bot.nickname
        else:
            # userJoined is invoked before the bot updates its channel_names
            # records, so we must add 1 to the size of the set here.
            number_of_users += 1
        
        ChannelPeak(channel=canonicalized_channel,
                    number_of_users=number_of_users,
                    joiner=prefix.split('!', 1)[0])
    
    def endNames(self, bot, channel):
        self._add_record(bot, None, channel)
    
    def userJoined(self, bot, prefix, channel):
        self._add_record(bot, prefix, channel)


class PeakCommand(object):
    """
    \x02%s\x02 [\x1Fchannel\x1F] - Return the highest number of users seen in 
    the given channel, or the channel in which the command is executed if no 
    channel is given.
    """
    implements(IPlugin, ICommand)
    name = 'peak'
    
    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            requested_channel = channel
        else:
            requested_channel = args[1]
        
        if channel == bot.nickname and requested_channel == channel:
            bot.reply(prefix, channel, 'You must specify a channel name to '
                                       'look up channel peak information '
                                       'through private messages.')
            return
        
        if (requested_channel not in self.factory.handlers or
            not filter(lambda x: isinstance(x, PeakHandler),
                       self.factory.handlers[requested_channel])):
            bot.reply(prefix, channel, 'Channel peaks are not being tracked '
                                       'in %s.' % requested_channel)
            return
        
        record = ChannelPeak.select(ChannelPeak.q.channel
                                      ==ircutil.canonicalize(requested_channel),
                                    orderBy=['-number_of_users',
                                             '-timestamp'])

        if record.count() < 1:
            bot.reply(prefix, channel, 'There are no channel peak records for '
                                       '%s.' % requested_channel)
            return

        bot.reply(prefix, channel, 'The most recent channel peak for %s was '
                                   '%d users, after %s joined %s.'
                                    % (requested_channel,
                                       record[0].number_of_users,
                                       record[0].joiner,
                                       util.ago(record[0].timestamp)))
            

peakcommand = PeakCommand()
peakhandler = PeakHandler()