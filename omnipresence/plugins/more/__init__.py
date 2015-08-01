# -*- test-case-name: omnipresence.plugins.help.test_more
"""Event plugins for reading command reply buffers."""


from ...message import collapse
from ...plugin import EventPlugin


class Default(EventPlugin):
    def on_command(self, msg):
        msg.connection.reply_from_buffer(msg.content or msg.actor.nick,
                                         msg, reply_when_empty=True)

    def on_cmdhelp(self, msg):
        return collapse("""\
            [\x1Fnick\x1F] - Return the next message in \x1Fnick\x1F's
            command reply buffer, or your own if no nick is specified.
            """)
