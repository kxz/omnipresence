# -*- test-case-name: omnipresence.plugins.more.test_more
"""Event plugins for reading command reply buffers."""


from ...message import collapse
from ...plugin import EventPlugin
from ...settings import PRIVATE_CHANNEL


class Default(EventPlugin):
    def on_command(self, msg):
        venue = PRIVATE_CHANNEL if msg.private else msg.venue
        response = msg.connection.copy_buffer(
            venue, msg.content or msg.actor.nick, msg.actor.nick)
        return response

    def on_cmdhelp(self, msg):
        return collapse("""\
            [\x1Fnick\x1F] - Return the next message in \x1Fnick\x1F's
            command reply buffer, or your own if no nick is specified.
            """)
