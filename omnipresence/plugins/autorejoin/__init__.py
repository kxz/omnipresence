"""Event plugins for automatically rejoining channels after kicks."""


from ...plugin import EventPlugin


class Default(EventPlugin):
    def on_kick(self, msg):
        if msg.target == msg.connection.nickname:
            self.log.info('Kicked from {venue} by {actor}; rejoining',
                          venue=msg.venue, actor=msg.actor)
            msg.connection.join(msg.venue)
