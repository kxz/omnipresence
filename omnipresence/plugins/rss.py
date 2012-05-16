import feedparser
from twisted.internet import defer, task
from twisted.plugin import IPlugin
from twisted.python import log
from twisted.words.protocols import irc
from zope.interface import implements

from omnipresence.iomnipresence import IHandler
from omnipresence.web import request


class RSSNotifier(object):
    """Fetches a set of RSS feeds at a regular interval, and broadcasts
    any updates to channels."""
    implements(IPlugin, IHandler)
    name = 'rss'
    
    """A dictionary of configured feed URLs, each mapped to a set of
    channels on which to broadcast their respective updates."""
    feeds = {}
    
    """A set of tuples containing the feed URL and ID of feed items that
    have already been seen by the updater."""
    seen_items = set()
    
    """The time between feed updates, in minutes."""
    update_interval = 10
    
    """The `LoopingCall` instance used to schedule updates."""
    scheduler = None
    
    # Ick.
    _bot = None
    
    def _maybe_encode(self, s):
        if isinstance(s, unicode):
            return s.encode(self.factory.encoding)
        return s
    
    def connectionMade(self, bot):
        self._bot = bot
        if self.factory.config.has_section('rss'):
            initializers = []
            for k, v in self.factory.config.items('rss'):
                if k == 'update_interval':
                    self.update_interval = int(v, 10)
                    continue
                feed_url, channels = v.split(None, 1)
                # Populate the plugin's "feeds" dictionary.
                self.feeds[feed_url] = set()
                for channel in channels.split():
                    if channel[0] not in irc.CHANNEL_PREFIXES:
                        channel = '#%s' % channel
                    self.feeds[feed_url].add(channel)
                # Make the initial update request.
                d = request('GET', feed_url)
                d.addCallback(self.initialize, feed_url)
                d.addErrback(self.error, feed_url)
                initializers.append(d)
            self.scheduler = task.LoopingCall(self.update)
            l = defer.DeferredList(initializers)
            l.addCallback(lambda x: self.scheduler.start(
                                      self.update_interval * 60, now=False))
            return l
    
    def initialize(self, (headers, content), feed_url):
        feed = feedparser.parse(content)
        # Mark all of the items currently in the feed as seen.
        for item in feed.entries:
            if hasattr(item, 'id'):
                self.seen_items.add((feed_url, item.id))
        log.msg('Found %d entries in feed %s' % (len(feed.entries), feed_url))
    
    def update(self):
        log.msg('Updating RSS feeds')
        for feed_url in self.feeds:
            d = request('GET', feed_url)
            d.addCallback(self.broadcast, feed_url)
            d.addErrback(self.error, feed_url)
    
    def broadcast(self, (headers, content), feed_url):
        feed = feedparser.parse(content)
        feed_title = self._maybe_encode(feed.feed.title)
        for item in feed.entries:
            if not hasattr(item, 'id'):
                continue
            if (feed_url, item.id) not in self.seen_items:
                self.seen_items.add((feed_url, item.id))
                title = self._maybe_encode(item.title)
                url = self._maybe_encode(item.link)
                msg = ('RSS update from \x02{0}\x02: \x02{1}\x02' +
                       u' \u2014 '.encode(self.factory.encoding) +
                       '{2}').format(feed_title, title, url)
                for channel in self.feeds[feed_url]:
                    if channel in self._bot.channel_names:
                        self._bot.reply(None, channel, msg)

    def error(self, failure, feed_url):
        log.err(failure, 'Error updating feed %s' % feed_url)


default = RSSNotifier()
