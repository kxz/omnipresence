# -*- test-case-name: omnipresence.plugins.help.test
"""Event plugins for reading command reply buffers."""


from ...plugin import EventPlugin


class Default(EventPlugin):
    def on_command(self, msg):
        msg.connection.reply_from_buffer(msg.content or msg.actor.nick,
                                         msg, reply_when_empty=True)

    def on_cmdhelp(self, msg):
        return
