"""Fetches a set of RSS feeds at a regular interval, and broadcasts any
updates to channels."""
import datetime
from time import mktime

import feedparser
from twisted.internet import defer, task
from twisted.plugin import IPlugin
from twisted.python import log
from twisted.words.protocols import irc
from zope.interface import implements

from omnipresence.iomnipresence import ICommand, IHandler
from omnipresence.util import ago
from omnipresence.web import request


def st_ago(time):
    """`ago` for `struct_time` tuples."""
    return ago(datetime.datetime.fromtimestamp(mktime(time)))


"""Holds cached feed information."""
class Feed(object):
    url = None
    channels = None
    seen_items = None
    parsed = None
    
    def __init__(self, url):
        self.url = url
        self.channels = set()
        self.seen_items = set()


class RSSNotifier(object):
    """
    \x02%s\x02 [\x1Ffeed_name\x1F [\x1Fitem_number\x1F]] - Without a
    \x1Ffeed_name\x1F, list the RSS feeds whose updates are available
    in this channel.  With a \x1Ffeed_name\x1F, show information about
    the feed, or, if an \x1Fitem_number\x1F is specified, show details
    about the specified item.
    """
    implements(IPlugin, ICommand, IHandler)
    name = 'rss'
    
    """A dictionary mapping feed identifiers to a `Feed` instance."""
    feeds = {}
    
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
            for identifier, value in self.factory.config.items('rss'):
                if identifier == 'update_interval':
                    self.update_interval = int(value, 10)
                    continue
                feed_url, channels = value.split(None, 1)
                # Populate the plugin's "feeds" dictionary.
                self.feeds[identifier] = Feed(feed_url)
                for channel in channels.split():
                    if channel[0] not in irc.CHANNEL_PREFIXES:
                        channel = '#%s' % channel
                    self.feeds[identifier].channels.add(channel)
                # Make the initial update request.
                d = request('GET', feed_url)
                d.addCallback(self.initialize, identifier)
                d.addErrback(self.error, identifier)
                initializers.append(d)
            self.scheduler = task.LoopingCall(self.update)
            l = defer.DeferredList(initializers)
            l.addCallback(lambda x: self.scheduler.start(
                                      self.update_interval * 60, now=False))
            return l
    
    def initialize(self, (headers, content), identifier):
        feed = feedparser.parse(content)
        self.feeds[identifier].parsed = feed
        # Mark all of the items currently in the feed as seen.
        for item in feed.entries:
            if hasattr(item, 'id'):
                self.feeds[identifier].seen_items.add(item.id)
        log.msg('Found %d items in feed %s' % (len(feed.entries), identifier))
    
    def update(self):
        log.msg('Updating RSS feeds')
        for identifier, feed in self.feeds.iteritems():
            d = request('GET', feed.url)
            d.addCallback(self.broadcast, identifier)
            d.addErrback(self.error, identifier)
    
    def broadcast(self, (headers, content), identifier):
        feed = feedparser.parse(content)
        self.feeds[identifier].parsed = feed
        feed_title = self._maybe_encode(feed.feed.title)
        
        msg = None
        additional_updates = 0
        for item in feed.entries:
            if not hasattr(item, 'id'):
                continue
            if item.id not in self.feeds[identifier].seen_items:
                self.feeds[identifier].seen_items.add(item.id)
                if not msg:
                    title = self._maybe_encode(item.title)
                    url = self._maybe_encode(item.link)
                    msg = ('RSS update from \x02{0}\x02: \x02{1}\x02' +
                           u' \u2014 '.encode(self.factory.encoding) +
                           '{2}').format(feed_title, title, url)
                else:
                    additional_updates += 1
        if msg:
            if additional_updates:
                msg += ' (+{0} more)'.format(additional_updates)
            for channel in self.feeds[identifier].channels:
                if channel in self._bot.channel_names:
                    self._bot.reply(None, channel, msg)

    def error(self, failure, identifier):
        log.err(failure, 'Error updating feed %s' % identifier)
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split()
        available_feeds = filter(lambda x: channel in self.feeds[x].channels,
                                 self.feeds)
        
        if len(args) < 2:
            if available_feeds:
                bot.reply(reply_target, channel,
                          'Available feeds: \x02{0}\x02. For further '
                          'details, use \x02{1}\x02 \x1Ffeed_name\x1F.'.format(
                            '\x02, \x02'.join(sorted(available_feeds)),
                                              args[0]))
            else:
                bot.reply(reply_target, channel,
                          'No feeds available in this channel.')
            return
        
        identifier = args[1]
        if identifier not in available_feeds:
            bot.reply(prefix, channel, 'Unrecognized feed identifier '
                                       '\x02{0}\x02.'.format(identifier))
            return
        if not self.feeds[identifier].parsed:
            bot.reply(prefix, channel, 'No updates for the feed '
                                       '\x02{0}\x02 have been retrieved '
                                       'yet.'.format(identifier))
            return
        feed = self.feeds[identifier].parsed
        
        if len(args) == 2:
            msg = u' \u2014 '.encode(self.factory.encoding).join(
                    ['RSS: \x02{0}\x02',
                     'Home page: {1}',
                     'Feed URL: {2}']
                  ).format(self._maybe_encode(feed.feed.title),
                           self._maybe_encode(feed.feed.link),
                           self.feeds[identifier].url)
            if feed.entries:
                msg += (u' \u2014 '.encode(self.factory.encoding) +
                        'Last update: \x02{0}\x02 ({1})'.format(
                          self._maybe_encode(feed.entries[0].title),
                          st_ago(feed.entries[0].published_parsed)))
                if len(feed.entries) > 1:
                    msg += ' (+{0} more)'.format(len(feed.entries) - 1)
            bot.reply(reply_target, channel, msg)
            return
        
        item = None
        try:
            item_number = int(args[2], 10)
            item = feed.entries[item_number - 1]
        except IndexError:
            pass
        except ValueError:
            pass
        
        if item_number < 1 or not item:
            bot.reply(prefix, channel,
                      'Invalid item number \x02{0}\x02 for feed \x02{1}\x02 '
                      '(valid values: \x021\x02 through \x02{2}\x02).' \
                       .format(args[2], identifier, len(feed.entries)))
            return
        
        bot.reply(reply_target, channel,
                  ('RSS: \x02{0}\x02 item #{1}: \x02{2}\x02' +
                   u' \u2014 '.encode(self.factory.encoding) +
                   '{3} ({4})').format(self._maybe_encode(feed.feed.title),
                                       item_number,
                                       self._maybe_encode(item.title),
                                       self._maybe_encode(item.link),
                                       st_ago(item.published_parsed)))



default = RSSNotifier()
