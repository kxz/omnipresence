from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence.iomnipresence import ICommand
from omnipresence import util

class More(object):
    """
    \x02%s\x02 - Retrieve text from your message buffer.
    """
    implements(IPlugin, ICommand)
    name = 'more'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        nick = prefix.split('!', 1)[0].strip()
        buffer_channel = '@' if channel == bot.nickname else channel
        try:
            buffer = bot.message_buffers[channel][nick]
        except KeyError:
            buffer = None
        
        bot.reply(reply_target, channel, buffer or 'No text in buffer.')

default = More()
