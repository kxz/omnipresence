# -*- test-case-name: omnipresence.plugins.more.test_more
"""Event plugins for reading command reply buffers."""


from collections import Sequence
from itertools import tee

from ...message import ReplyBuffer, collapse
from ...plugin import EventPlugin, UserVisibleError
from ...settings import PRIVATE_CHANNEL


class Default(EventPlugin):
    def on_command(self, msg):
        venue = PRIVATE_CHANNEL if msg.private else msg.venue
        source = msg.content or msg.actor.nick
        buf = msg.connection.message_buffers[venue].get(
            source, ReplyBuffer([]))
        if msg.connection.case_mapping.equates(source, msg.actor.nick):
            return buf
        if msg.private:
            raise UserVisibleError("You cannot read another user's "
                                   "private reply buffer.")
        # The original iterator can no longer be advanced after using
        # `tee`, so we place one of the children back into the buffer
        # instead.
        one, two = buf.tee()
        msg.connection.message_buffers[venue][source] = one
        return two

    def on_cmdhelp(self, msg):
        return collapse("""\
            [\x1Fnick\x1F] - Return the next message in \x1Fnick\x1F's
            command reply buffer, or your own if no nick is specified.
            """)
