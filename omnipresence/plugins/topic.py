from twisted.plugin import IPlugin
from twisted.words.protocols import irc
from zope.interface import implements

from omnipresence import util
from omnipresence.iomnipresence import ICommand


# TODO: Make this configurable.
MAX_MESSAGE_LENGTH = 72


class TopicUpdater(object):
    """
    \x02%s\x02 \x1Fstring\x1F - Change the channel topic.
    """
    implements(IPlugin, ICommand)
    name = 'topic'

    """Stores the format strings for each channel."""
    formats = None

    def __init__(self):
        self.formats = {}

    def registered(self):
        if self.factory.config.has_section('topic'):
            for (channel, format) in self.factory.config.items('topic'):
                if channel[0] not in irc.CHANNEL_PREFIXES:
                    channel = '#%s' % channel
                self.formats[channel] = format

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)

        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a message.')
            return

        if channel not in self.formats:
            bot.reply(prefix, channel, 'Topic changes are not enabled in %s.'
                                        % channel)
            return

        try:
            message = args[1].decode(self.factory.encoding)
        except UnicodeDecodeError:
            bot.reply(prefix, channel, 'Topic messages must use the "%s" '
                                       'character encoding. Check your '
                                       'client settings and try again.'
                                        % self.factory.encoding)
            return

        message = u'<%s> %s' % (prefix.split('!', 1)[0], message)

        if len(message) > MAX_MESSAGE_LENGTH:
            bot.reply(prefix, channel, 'Topic messages may not exceed %d '
                                       'characters in length.'
                                        % MAX_MESSAGE_LENGTH)
            return

        topic = self.formats[channel] % message
        bot.topic(channel, topic.encode(self.factory.encoding))


topic = TopicUpdater()
