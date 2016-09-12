# -*- test-case-name: omnipresence.plugins.more.test_more
"""Event plugins for reading command reply buffers."""


from collections import Sequence
from itertools import tee

from ...message import collapse
from ...message.buffering import ReplyBuffer
from ...plugin import EventPlugin, UserVisibleError
from ...settings import PRIVATE_CHANNEL


class Default(EventPlugin):
    """Show additional text from a user's reply buffer.

    :brian: count
    :bot: 1
    :brian: more
    :bot: 2
    :brian: more
    :bot: 3

    In public channels, an optional argument can be passed to view the
    contents of another user's reply buffer.

    :alice: count
    :bot: alice: 1
    :brian: more alice
    :bot: brian: 2
    """

    def on_command(self, msg):
        venue = PRIVATE_CHANNEL if msg.private else msg.venue
        source = msg.content or msg.actor.nick
        try:
            buf = msg.connection.venues[venue].nicks[source].reply_buffer
        except KeyError:
            buf = ReplyBuffer([])
        if msg.connection.case_mapping.equates(source, msg.actor.nick):
            return buf
        if msg.private:
            raise UserVisibleError("You cannot read another user's "
                                   "private reply buffer.")
        # The original iterator can no longer be advanced after using
        # `tee`, so we place one of the children back into the buffer
        # instead.
        one, two = buf.tee()
        msg.connection.venues[venue].add_nick(source)
        msg.connection.venues[venue].nicks[source].reply_buffer = one
        return two

    def on_cmdhelp(self, msg):
        return collapse("""\
            [\x1Fnick\x1F] - Return the next message in \x1Fnick\x1F's
            command reply buffer, or your own if no nick is specified.
            """)
