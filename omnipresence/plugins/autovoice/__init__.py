# -*- test-case-name: omnipresence.plugins.autovoice.test_autovoice
"""An event plugin that automatically voices users as they join a
channel, unless that channel is moderated."""


from collections import defaultdict

from ...plugin import EventPlugin


class Default(EventPlugin):
    def on_join(self, msg):
        if msg.private:
            return
        venue_info = msg.connection.venues.get(msg.venue)
        if venue_info is None or venue_info.modes['m']:
            return
        msg.connection.mode(msg.venue, True, 'v', user=msg.actor.nick)
