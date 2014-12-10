from twisted.plugin import IPlugin
from twisted.words.protocols import irc
from zope.interface import implements

from omnipresence import util
from omnipresence.iomnipresence import ICommand


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
        self.ignore_list = set()
        self.max_message_length = 96

    def registered(self):
        if self.factory.config.has_section('topic'):
            for (key, value) in self.factory.config.items('topic'):
                if key == '$max_message_length':
                    self.max_message_length = int(value)
                    continue
                if key == '$ignore_messages_from':
                    self.ignore_list = set(value.split())
                    continue
                if key[0] not in irc.CHANNEL_PREFIXES:
                    key = '#%s' % key
                self.formats[key] = value

    def execute(self, bot, prefix, reply_target, channel, args):
        nick = prefix.split('!', 1)[0]

        if nick in self.ignore_list:
            return

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

        message = u'<%s> %s' % (nick, message)

        if len(message) > self.max_message_length:
            bot.reply(prefix, channel, 'Topic messages may not exceed %d '
                                       'characters in length.'
                                        % self.max_message_length)
            return

        topic = self.formats[channel] % message
        bot.topic(channel, topic.encode(self.factory.encoding))


topic = TopicUpdater()
