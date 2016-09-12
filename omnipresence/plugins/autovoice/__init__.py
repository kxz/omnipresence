# -*- test-case-name: omnipresence.plugins.autovoice.test_autovoice
"""An event plugin that automatically voices users as they join a
channel, unless that channel is moderated."""


from collections import defaultdict

from ...plugin import EventPlugin


class Default(EventPlugin):
    """Automatically voice users as they enter a channel, unless
    moderation is set with the ``+m`` channel mode.  Useful for managing
    a sudden influx of new users.

    Note that Omnipresence almost certainly has to have channel operator
    privileges (``+o``) in order for this plugin to work.
    """

    def on_join(self, msg):
        if msg.private:
            return
        venue_info = msg.connection.venues.get(msg.venue)
        if venue_info is None or venue_info.modes['m']:
            return
        msg.connection.mode(msg.venue, True, 'v', user=msg.actor.nick)
