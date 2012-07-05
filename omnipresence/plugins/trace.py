from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import ircutil, util
from omnipresence.iomnipresence import ICommand, IHandler


class NickTracer(object):
    """
    \x02%s\x02 \x1Fnick\x1F - List the other nicks that the user with
    the given nick has been seen using since the bot's or that user's
    last join, whichever comes later.
    """
    implements(IPlugin, IHandler, ICommand)
    name = 'trace'

    traces = {}

    def endNames(self, bot, channel):
        for name in bot.channel_names[channel]:
            self.userJoined(bot, name, channel)

    def userRenamed(self, bot, oldname, newname):
        c_oldname = ircutil.canonicalize(oldname)
        c_newname = ircutil.canonicalize(newname)

        if c_oldname not in self.traces:
            self.traces[c_oldname] = set()

        if c_oldname != c_newname:
            self.traces[c_newname] = self.traces[c_oldname]
            self.traces[c_newname].add(oldname)
            self.traces[c_newname].discard(newname)
            del self.traces[c_oldname]

    def userJoined(self, bot, prefix, channel):
        nick = prefix.split('!', 1)[0]
        c_nick = ircutil.canonicalize(nick)

        # Make sure that the user isn't already in self.traces, in
        # case said user is already in another channel where nick
        # tracing is enabled.
        if c_nick not in self.traces:
            self.traces[c_nick] = set()

    def joined(self, bot, prefix, channel):
        self.userJoined(bot, bot.nickname, channel)

    def userKicked(self, bot, kickee, channel, kicker, msg):
        self.userLeft(bot, kickee, channel)

    def userLeft(self, bot, prefix, channel):
        nick = prefix.split('!', 1)[0]

        # Is the departing user left in any other channels?
        # If not, delete that user's record.
        if not filter(lambda x: x[0] != channel and nick in x[1],
                      bot.channel_names.iteritems()):
            del self.traces[ircutil.canonicalize(nick)]

    def userQuit(self, bot, prefix, quitMessage):
        c_nick = ircutil.canonicalize(prefix.split('!', 1)[0])
        del self.traces[c_nick]


    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)

        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a nickname to look up.')
            return

        nick = args[1]
        canonicalized_nick = ircutil.canonicalize(nick)

        if canonicalized_nick == ircutil.canonicalize(bot.nickname):
            bot.reply(prefix, channel, '{0} is right here responding to your '
                                       'queries!'.format(bot.nickname))
            return

        if canonicalized_nick not in self.traces:
            bot.reply(prefix, channel, 'No user with the nick {0} is currently '
                                       'visible.'.format(nick))
            return

        trace = self.traces[canonicalized_nick]

        if len(trace) == 0:
            bot.reply(reply_target, channel, '{0} has not changed nick since '
                                             'first being seen.'.format(nick))
            return

        message = '{0} has also used the nick'.format(nick)
        if len(trace) > 1:
            message += 's'
        message += ' ' + util.andify(['\x02{0}\x02'.format(nick)
                                      for nick in sorted(trace)])

        bot.reply(reply_target, channel, message + '.')


default = NickTracer()
