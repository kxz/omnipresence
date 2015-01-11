"""Unit test helpers."""


from twisted.words.protocols.irc import CHANNEL_PREFIXES


class DummyConnection(object):
    """A class that simulates the behavior of a live connection."""

    def is_channel(self, venue):
        return venue[0] in CHANNEL_PREFIXES
