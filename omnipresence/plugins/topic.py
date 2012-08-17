from twisted.plugin import IPlugin
from twisted.words.protocols import irc
from zope.interface import implements

from omnipresence import util
from omnipresence.iomnipresence import ICommand, IHandler


# TODO: Make these configurable.
MAX_MESSAGE_LENGTH = 64
MAX_TOPIC_CHAR_LENGTH = 192
MAX_TOPIC_BYTE_LENGTH = 384


class TopicUpdater(object):
    """
    \x02%s\x02 \x1Fstring\x1F - Add something to the channel topic,
    assuming the bot has permission to do so.
    """
    implements(IPlugin, ICommand, IHandler)
    name = 'topic'

    topics = {}
    prefixes = {}

    def registered(self):
        if self.factory.config.has_section('topic'):
            for (channel, prefix) in self.factory.config.items('topic'):
                if channel[0] not in irc.CHANNEL_PREFIXES:
                    channel = '#%s' % channel
                self.prefixes[channel] = prefix

    def topicUpdated(self, bot, nick, channel, newTopic):
        self.topics[channel] = newTopic

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)

        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a message to add.')
            return

        if channel not in self.topics:
            bot.reply(prefix, channel, 'Topic messages are not being tracked '
                                       'in %s.' % channel)
            return

        message = ''

        try:
            message = self.topics[channel].decode(self.factory.encoding)
        except UnicodeDecodeError:
            pass

        try:
            new_message = args[1].decode(self.factory.encoding)
        except UnicodeDecodeError:
            bot.reply(prefix, channel, 'Topic messages must use the "%s" '
                                       'character encoding. Check your '
                                       'client settings and try again.'
                                        % self.factory.encoding)
            return

        if len(new_message) > MAX_MESSAGE_LENGTH:
            bot.reply(prefix, channel, 'Topic messages may not exceed %d '
                                       'characters in length.'
                                        % MAX_MESSAGE_LENGTH)
            return

        messages = []

        if message:
            messages = message.split(u' | ')

        messages.insert(0, u'%s (%s)' % (new_message,
                                         prefix.split('!', 1)[0]))

        if channel in self.prefixes:
            while self.prefixes[channel] in messages:
                messages.remove(self.prefixes[channel])
            messages.insert(0, self.prefixes[channel])

        topic = u' | '.join(messages)
        encoded_topic = topic.encode(self.factory.encoding)
        truncated_topic = util.truncate_unicode(topic,
                                                MAX_TOPIC_CHAR_LENGTH,
                                                MAX_TOPIC_BYTE_LENGTH,
                                                self.factory.encoding)

        if encoded_topic != truncated_topic:
            truncated_topic = '%s...' % truncated_topic

        bot.topic(channel, truncated_topic)


topic = TopicUpdater()
