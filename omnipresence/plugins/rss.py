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


def force_unicode(s):
    if isinstance(s, unicode):
        return s
    return s.decode('utf8', 'replace')

def st_ago(time):
    """`ago` for `struct_time` tuples."""
    return ago(datetime.datetime.fromtimestamp(mktime(time)))

def format_item(item, show_date=False):
    messages = []
    if 'link' in item:
        messages.append(force_unicode(item['link']))
    if 'title' in item:
        messages.append(u'\x02{0}\x02'.format(force_unicode(item['title'])))
    if 'author' in item:
        messages.append(u'Author: {0}'.format(force_unicode(item['author'])))
    msg = u' \u2014 '.join(messages)
    date = item.get('published_parsed', item.get('updated_parsed'))
    if date and show_date:
        msg += u' ({0})'.format(st_ago(date))
    return msg


"""Holds cached feed information."""
class Feed(object):
    url = None
    channels = None
    seen_items = None
    last_update = None
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
    feeds = None
    
    """The time between feed updates, in minutes."""
    update_interval = 10
    
    """The `LoopingCall` instance used to schedule updates."""
    scheduler = None
    
    # Ick.
    _bot = None
    
    def __init__(self):
        self.feeds = {}
    
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
        if not self.scheduler:
            self.scheduler = task.LoopingCall(self.update)
            l = defer.DeferredList(initializers)
            l.addCallback(lambda x: self.scheduler.start(
                                      self.update_interval * 60, now=False))
            return l
    
    def update(self):
        log.msg('Updating RSS feeds')
        for identifier, feed in self.feeds.iteritems():
            d = request('GET', feed.url)
            d.addCallback(self.initialize, identifier)
            d.addCallback(self.broadcast, identifier)
            d.addErrback(self.error, identifier)
    
    def initialize(self, (headers, content), identifier):
        feed = feedparser.parse(content)
        self.feeds[identifier].parsed = feed
        self.feeds[identifier].last_update = datetime.datetime.now()
        new_items = filter(lambda x: x.get('id') not in \
                                     self.feeds[identifier].seen_items,
                           feed.entries)
        self.feeds[identifier].seen_items.update(x.get('id') for x in \
                                                 feed.entries)
        if new_items:
            log.msg('Found %d new items in feed %s' % (len(new_items),
                                                       identifier))
        return new_items
    
    def broadcast(self, new_items, identifier):
        if new_items:
            feed_title = force_unicode(self.feeds[identifier].parsed.feed.get(
                                         'title', identifier))
            msg = (u'RSS update from \x02{0}\x02: {1}' \
                     .format(feed_title, format_item(new_items[0])))
            if len(new_items) > 1:
                msg += u' (+{0} more)'.format(len(new_items) - 1)
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
        feed_title = force_unicode(feed.feed.get('title', identifier))
        
        if len(args) == 2:
            messages = [u'RSS: \x02{0}\x02'.format(feed_title)]
            if 'link' in feed.feed:
                messages.append(u'Home page: {0}'.format(
                                  force_unicode(feed.feed['link'])))
            messages.append(u'Feed URL: {0}'.format(
                              force_unicode(self.feeds[identifier].url)))
            messages.append(u'Last updated: {0}'.format(
                              ago(self.feeds[identifier].last_update)))
            messages.append(u'{0} items'.format(len(feed.entries)))
            bot.reply(reply_target, channel, u' \u2014 '.join(messages))
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
                  u'RSS: \x02{0}\x02 item #{1}: {2}'.format(
                    feed_title, item_number, format_item(item, show_date=True)))


default = RSSNotifier()
