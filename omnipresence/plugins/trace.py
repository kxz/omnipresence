import datetime

from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import util
from omnipresence.iomnipresence import ICommand, IHandler


class NickTracer(object):
    implements(IPlugin, IHandler)
    name = 'trace'
    
    traces = {}
    
    def endNames(self, bot, channel):
        for user in bot.channel_names[channel]:
            self.userJoined(bot, user, channel)
    
    def userRenamed(self, bot, oldname, newname):
        c_oldname = util.canonicalize(oldname)
        c_newname = util.canonicalize(newname)
        
        self.traces[c_newname] = self.traces[c_oldname]
        self.traces[c_newname].append((newname, datetime.datetime.now()))
        del self.traces[c_oldname]
    
    def userJoined(self, bot, user, channel):
        user = user.split('!', 1)[0]
        c_user = util.canonicalize(user)
        
        # Make sure that the user isn't already in self.traces, in 
        # case said user is already in another channel where nick 
        # tracing is enabled.
        if c_user not in self.traces:
            self.traces[c_user] = [(user, datetime.datetime.now())]

    def joined(self, bot, prefix, channel):
        self.userJoined(bot, bot.nickname, channel)

    def userKicked(self, bot, kickee, channel, kicker, msg):
        self.userLeft(bot, kickee, channel)

    def userLeft(self, bot, user, channel):
        user = user.split('!', 1)[0]
        
        # Is the leaving user left in any other channels?  If not, 
        # delete that user's record.
        if not filter(lambda x: x[0] != channel and user in x[1],
                      bot.channel_names.iteritems()):
            del self.traces[util.canonicalize(user)]
    
    def userQuit(self, bot, user, quitMessage):
        user = util.canonicalize(user.split('!', 1)[0])
        del self.traces[user]


class TraceCommand(object):
    """
    \x02%s\x02 \x1Fnick\x1F - List the other nicks that the user with 
    the given nick has been seen using since the bot's or that user's 
    last join, whichever comes later.
    """
    implements(IPlugin, ICommand)
    name = 'trace'
    
    def execute(self, bot, user, channel, args):
        # Try to latch on to a NickTracer instance.
        tracer = []
        
        if channel in self.factory.handlers:
            tracer = filter(lambda x: isinstance(x, NickTracer),
                            self.factory.handlers[channel])
        
        if not tracer:
            bot.reply(user, channel, 'User nicknames are not being tracked in '
                                     '%s.' % channel)
            return
        
        tracer = tracer[0]
        
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(user, channel, 'Please specify a nickname to look up.')
            return
        
        nick = args[1]
        canonicalized_nick = util.canonicalize(nick)
        
        if canonicalized_nick == util.canonicalize(bot.nickname):
            bot.reply(user, channel,
                      '%s is right here responding to your queries!'
                       % bot.nickname)
            return
        
        if canonicalized_nick not in tracer.traces:
            bot.reply(user, channel, 'No user with the nick %s is currently '
                                     'visible.' % nick)
            return
        
        trace = tracer.traces[canonicalized_nick]
        
        if len(trace) == 1:
            bot.reply(user, channel, '%s has not changed nick since first '
                                     'being seen %s.'
                                      % (trace[0][0], util.ago(trace[0][1])))
            return
        
        messages = [
            '%s changed to that nick %s' % (trace[-1][0],
                                            util.ago(trace[-1][1])),
            'was first seen with the nick %s %s' % (trace[0][0],
                                                    util.ago(trace[0][1]))
        ]
        
        if len(trace) > 2:
            trace_messages = []
        
            # [-2:0:-1]: start with the previous nick (-1 is current nick, -2
            # is the one before it), and stop before reaching the first nick.
            for record in trace[-2:0:-1]:
                trace_messages.append('%s (changed to %s)'
                                       % (record[0], util.ago(record[1])))
            
            trace_message = 'has additionally used the nick'
            if len(trace_messages) > 1:
                trace_message += 's'
            trace_message += ' ' + util.andify(trace_messages)
            messages.append(trace_message)
        
        bot.reply(user, channel, util.andify(messages, True) + '.')
            

trace_h = NickTracer()
trace_c = TraceCommand()