import datetime

import sqlobject
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import ircutil, util
from omnipresence.iomnipresence import ICommand, IHandler


DEFAULT_LOOKUP_DURATION = '365d'


class ChannelPeak(sqlobject.SQLObject):
    channel = sqlobject.StringCol(notNone=True, length=64)
    number_of_users = sqlobject.IntCol(notNone=True)
    timestamp = sqlobject.DateTimeCol(notNone=True,
                                      default=sqlobject.DateTimeCol.now)
    joiner = sqlobject.StringCol(notNone=True, length=64)
    channel_count_index = sqlobject.DatabaseIndex('channel', 'number_of_users',
                                                  unique=True)
    timestamp_index = sqlobject.DatabaseIndex('timestamp')


class PeakWatcher(object):
    """
    \x02%s\x02 [\x1Fchannel\x1F]
    [\x1Fweeks\x1F\x02W\x02][\x1Fdays\x1F\x02D\x02][\x1Fhours\x1F\x02H\x02][\x1Fminutes\x1F\x02M\x02][\x1Fseconds\x1F\x02S\x02]
    - Return the highest number of users recently seen in the given
    channel, or the channel in which the command is executed if no
    channel is given. If a duration is specified, only look for peaks
    that occurred less than that duration ago.
    """
    implements(IPlugin, ICommand, IHandler)
    name = 'peak'
    
    def registered(self):
        ChannelPeak.createTable(ifNotExists=True)
        self.default_lookup_duration = \
          self.factory.config.getdefault('peak', 'default_lookup_duration',
                                         DEFAULT_LOOKUP_DURATION)
    
    def _update_record(self, bot, prefix, channel):
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
        
        joiner = prefix.split('!', 1)[0]
        
        try: 
            record = ChannelPeak.selectBy(channel=canonicalized_channel,
                                          number_of_users=number_of_users)[0]
        except IndexError:
            ChannelPeak(channel=canonicalized_channel,
                        number_of_users=number_of_users,
                        joiner=joiner)
            return
        
        record.timestamp = sqlobject.DateTimeCol.now()
        record.joiner = joiner
    
    def endNames(self, bot, channel):
        self._update_record(bot, None, channel)
    
    def userJoined(self, bot, prefix, channel):
        self._update_record(bot, prefix, channel)

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split()
        
        requested_channel = channel
        lookup_duration = self.default_lookup_duration
        
        if len(args) == 2:
            lookup_duration = args[1]
            
            if not util.duration_to_timedelta(lookup_duration):
                requested_channel = args[1]
                lookup_duration = self.default_lookup_duration
        elif len(args) > 2:
            requested_channel = args[1]
            lookup_duration = args[2]
            
            if not util.duration_to_timedelta(lookup_duration):
                bot.reply(prefix, channel, 'Invalid duration \x02%s\x02.'
                                            % lookup_duration)
        
        if channel == bot.nickname and requested_channel == channel:
            bot.reply(prefix, channel, 'You must specify a channel name to '
                                       'look up channel peak information '
                                       'through private messages.')
            return
        
#        if (requested_channel not in self.factory.handlers or
#            not filter(lambda x: isinstance(x, PeakWatcher),
#                       self.factory.handlers[requested_channel])):
#            bot.reply(prefix, channel, 'Channel peaks are not being tracked '
#                                       'in %s.' % requested_channel)
#            return
        
        timestamp_threshold = (datetime.datetime.now() -
                               util.duration_to_timedelta(lookup_duration))
        where = sqlobject.AND(ChannelPeak.q.channel
                                ==ircutil.canonicalize(requested_channel),
                              ChannelPeak.q.timestamp>=timestamp_threshold)
        
        try:
            record = ChannelPeak.select(where, orderBy=['-number_of_users',
                                                        '-timestamp'])[0]
                                                        # just in case
        except IndexError:
            bot.reply(prefix, channel, 'There are no channel peak records for '
                                       '%s within the past %s.'
                                        % (requested_channel,
                                           util.readable_duration(lookup_duration)))
            return

        bot.reply(reply_target, channel, 'The most recent channel peak for %s '
                                         'within the past %s was %d users, '
                                         'after %s joined %s.'
                                          % (requested_channel,
                                             util.readable_duration(lookup_duration),
                                             record.number_of_users,
                                             record.joiner,
                                             util.ago(record.timestamp)))


peak = PeakWatcher()