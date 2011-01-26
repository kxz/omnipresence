import datetime

import sqlobject
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import ircutil, util
from omnipresence.iomnipresence import ICommand, IHandler


class SeenUser(sqlobject.SQLObject):
    canonicalizedNick = sqlobject.StringCol(length=64, unique=True,
                                            alternateID=True, notNone=True)
    nick = sqlobject.StringCol(length=64, notNone=True)
    lastActivity = sqlobject.DateTimeCol(notNone=True,
                                         default=sqlobject.DateTimeCol.now)
    action = sqlobject.StringCol(length=16, notNone=True)
    actor = sqlobject.StringCol(length=64)
    channel = sqlobject.StringCol(length=64)
    data = sqlobject.UnicodeCol()


class Watcher(object):
    implements(IPlugin, IHandler)
    name = 'seen'
    
    def registered(self):
        SeenUser.createTable(ifNotExists=True)
    
    def _update_record(self, nick, action, actor=None, channel=None, data=None):
        canonicalized_nick = ircutil.canonicalize(nick)
        
        try:
            record = SeenUser.byCanonicalizedNick(canonicalized_nick)
            record.nick = nick
            record.action = action
            record.actor = actor
            record.channel = channel
            record.data = data
        except sqlobject.main.SQLObjectNotFound:
            record = SeenUser(canonicalizedNick=canonicalized_nick, nick=nick,
                              action=action, actor=actor, channel=channel,
                              data=data)
    
    def privmsg(self, bot, prefix, channel, message):
        nick = prefix.split('!', 1)[0]
        self._update_record(nick, 'privmsg', channel=channel, data=message)

    def joined(self, bot, prefix, channel):
        self.userJoined(bot, prefix, channel)
    
    def left(self, bot, prefix, channel):
        self.userLeft(bot, prefix, channel)
    
    def noticed(self, bot, prefix, channel, msg):
        nick = prefix.split('!', 1)[0]
        self._update_record(nick, 'noticed', channel=channel, data=msg)
    
    def modeChanged(self, bot, prefix, channel, set, modes, args):
        nick = prefix.split('!', 1)[0]
        flags = (('+' if set else '-') +
                 modes + (' ' + ' '.join(args) if args else ''))
        self._update_record(nick, 'modeChanged', channel=channel, data=flags)
    
    def kickedFrom(self, bot, channel, kicker, message):
        self.userKicked(bot, bot.nickname, channel, kicker, message)
    
    def nickChanged(self, bot, nick):
        self.userRenamed(bot, bot.nickname, nick)
    
    def userJoined(self, bot, prefix, channel):
        nick = prefix.split('!', 1)[0]
        self._update_record(nick, 'userJoined', channel=channel)

    def userLeft(self, bot, prefix, channel):
        nick = prefix.split('!', 1)[0]
        self._update_record(nick, 'userLeft', channel=channel)
    
    def userQuit(self, bot, prefix, quitMessage):
        nick = prefix.split('!', 1)[0]
        self._update_record(nick, 'userQuit', data=quitMessage)

    def userKicked(self, bot, kickee, channel, kicker, msg):
        kickee = kickee.split('!', 1)[0]
        kicker = kicker.split('!', 1)[0]
        self._update_record(kickee, 'userKicked', actor=kicker,
                            channel=channel, data=msg)
        self._update_record(kicker, 'userKickedBy', actor=kickee,
                            channel=channel, data=msg)
    
    def action(self, bot, prefix, channel, data):
        nick = prefix.split('!', 1)[0]
        self._update_record(nick, 'action', channel=channel, data=data)
 
    def topicUpdated(self, bot, prefix, channel, newTopic):
        nick = prefix.split('!', 1)[0]
        self._update_record(nick, 'topicUpdated', channel=channel,
                            data=newTopic)
    
    def userRenamed(self, bot, oldname, newname):
        self._update_record(oldname, 'userRenamed', data=newname)
        self._update_record(newname, 'userRenamedFrom', data=oldname)

    def kick(self, bot, channel, nick, reason):
        self.userKicked(bot, nick, channel, bot.nickname, reason)

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
    
    def msg(self, bot, channel, msg):
        self.privmsg(bot, bot.nickname, channel, msg)
    
    def notice(self, bot, nick, msg):
        self.noticed(bot, bot.nickname, nick, msg)
    
    def setNick(self, bot, nickname):
        self.userRenamed(bot, bot.nickname, nickname)
    
    def quit(self, bot, message):
        self.userQuit(bot, bot.nickname, message)
    
    def me(self, bot, channel, action):
        self.action(bot, bot.nickname, channel, action)


class SeenCommand(object):
    """
    \x02%s\x02 [\x1Fnick\x1F] - Report the last action that the user 
    with the given nick was seen doing, along with how long ago it 
    occurred.  An asterisk (\x02*\x02) can be used as a wildcard to 
    match arbitrary parts of names, given that there are also at least 
    three non-wildcard characters in the search.
    """
    implements(IPlugin, ICommand)
    name = 'seen'
    
    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a nickname to look up.')
            return
        
        nick = args[1]
        canonicalized_nick = ircutil.canonicalize(nick)
        
        if canonicalized_nick == ircutil.canonicalize(bot.nickname):
            bot.reply(prefix, channel,
                      '%s is right here responding to your queries!'
                       % bot.nickname)
            return
        
        if canonicalized_nick == ircutil.canonicalize(prefix.split('!', 1)[0]):
            bot.reply(prefix, channel,
                      'I hope you know the answer to that question already!')
            return
        
        if '*' in nick:
            if len(nick.replace('*', '')) < 3:
                bot.reply(prefix, channel,
                          'Searches for seen users require at least three '
                          'non-wildcard characters.')
                return
            
            records = SeenUser.select(sqlobject.LIKE(SeenUser.q.canonicalizedNick,
                                                     canonicalized_nick.replace('_', r'\_').replace('%', r'\%').replace('*', '%')),
                                      orderBy='-last_activity')
            matches = ['\x02%s\x02 (seen %s)' % (record.nick,
                                                 util.ago(record.lastActivity))
                       for record in records]
            
            if len(matches) < 1:
                bot.reply(prefix, channel,
                          'No users with nicks matching the pattern '
                          '\x02%s\x02 have been seen.' % nick)
                return
            
            bot.reply(prefix, channel, 'Found %s.' % ', '.join(matches))
            return
        
        try:
            record = SeenUser.byCanonicalizedNick(canonicalized_nick)
        except sqlobject.main.SQLObjectNotFound:
            bot.reply(prefix, channel, 'No user with the nick \x02%s\x02 has '
                                       'been seen recently.' % nick)
            return
        
        if record.action in ('privmsg', 'noticed'):
            message = (' saying \x02%s\x02 to %s'
                        % (record.data, record.channel))
        elif record.action == 'action':
            message = (' performing the action \x02%s\x02 in %s'
                        % (record.data, record.channel))
        elif record.action == 'userRenamed':
            message = ' changing nick to %s' % record.data
        elif record.action == 'userRenamedFrom':
            message = ' changing nick from %s' % record.data
        elif record.action == 'userJoined':
            message = ' joining %s' % record.channel
        elif record.action == 'userKicked':
            message = (' being kicked from %s by %s'
                        % (record.channel, record.actor))
            if record.data:
                message += ' with the message \x02%s\x02' % record.data
        elif record.action == 'userKickedBy':
            message = ' kicking %s from %s' % (record.actor, record.channel)
            if record.data:
                message += ' with the message \x02%s\x02' % record.data
        elif record.action == 'userLeft':
            message = ' leaving %s' % record.channel
        elif record.action == 'topicUpdated':
            message = (' changing the topic of %s to \x02%s\x02'
                        % (record.channel, record.data))
        elif record.action == 'userQuit':
            message = ' quitting IRC'
            if record.data:
                message += ' with the message \x02%s\x02' % record.data
        elif record.action == 'modeChanged':
            message = (' setting mode \x02%s\x02 in %s'
                        % (record.data, record.channel))
        else:
            message = ''
        
        bot.reply(prefix, channel, ('%s was last seen %s%s.'
                                     % (record.nick,
                                        util.ago(record.lastActivity),
                                        message)) \
                                    .encode(self.factory.encoding))
            

seen_h = Watcher()
seen_c = SeenCommand()
