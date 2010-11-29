from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand, IHandler

import sqlobject

from omnipresence import util


class ChannelPeak(sqlobject.SQLObject):
    channel = sqlobject.StringCol(notNone=True, length=64)
    number_of_users = sqlobject.IntCol(notNone=True)
    timestamp = sqlobject.TimestampCol(notNone=True, default=sqlobject.sqlbuilder.func.NOW())
    joiner = sqlobject.StringCol(notNone=True, length=64)


class PeakHandler(object):
    implements(IPlugin, IHandler)
    name = 'peak'
    
    def registered(self):
        ChannelPeak.createTable(ifNotExists=True)
    
    def _add_record(self, bot, user, channel):
        canonicalized_channel = util.canonicalize(channel)
        
        if canonicalized_channel not in bot.channel_names:
            return
        
        number_of_users = len(bot.channel_names[canonicalized_channel])
        
        if user is None:
            # We were called via endNames, so assume the bot just joined.
            user = bot.nickname
        else:
            # userJoined is invoked before the bot updates its channel_names
            # records, so we must add 1 to the size of the set here.
            number_of_users += 1
        
        ChannelPeak(channel=canonicalized_channel,
                    number_of_users=number_of_users,
                    joiner=user.split('!', 1)[0])
    
    def endNames(self, bot, channel):
        self._add_record(bot, None, channel)
    
    def userJoined(self, bot, user, channel):
        self._add_record(bot, user, channel)


class PeakCommand(object):
    """
    \x02%s\x02 [\x1Fchannel\x1F] - Return the highest number of users seen in 
    the given channel, or the channel in which the command is executed if no 
    channel is given.
    """
    implements(IPlugin, ICommand)
    name = 'peak'
    
    def execute(self, bot, user, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            requested_channel = channel
        else:
            requested_channel = args[1]
        
        if channel == bot.nickname and requested_channel == channel:
            bot.reply(user, channel, 'You must specify a channel name to look '
                                     'up channel peak information through '
                                     'private messages.')
            return
        
        record = ChannelPeak.select(ChannelPeak.q.channel
                                      ==util.canonicalize(requested_channel),
                                    orderBy=['-number_of_users',
                                             '-timestamp'])

        if record.count() < 1:
            bot.reply(user, channel, 'There are no channel peak records for '
                                     '%s.' % requested_channel)
            return

        bot.reply(user, channel, 'The most recent channel peak for %s was %d '
                                 'users, after %s joined %s.'
                                  % (requested_channel,
                                     record[0].number_of_users,
                                     record[0].joiner,
                                     util.ago(record[0].timestamp)))
            

peakcommand = PeakCommand()
peakhandler = PeakHandler()