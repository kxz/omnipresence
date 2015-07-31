"""Omnipresence plugins for URL title fetching."""
# -*- test-case-name: omnipresence.plugins.url.test_url


import re
import urllib
from urlparse import urlparse, urldefrag

from littlebrother import fetch_title, BlacklistedHost
from twisted.internet.defer import DeferredList, inlineCallbacks, returnValue
from twisted.internet.error import ConnectError, DNSLookupError
from twisted.plugin import IPlugin
from twisted.python import log
from twisted.web.client import ResponseFailed
from twisted.web.error import InfiniteRedirection
from zope.interface import implements

from ...iomnipresence import IHandler


# Based on django.utils.html.urlize from the Django project.
TRAILING_PUNCTUATION = ['.', ',', ':', ';', '.)', '"', "'", '!']
WRAPPING_PUNCTUATION = [('(', ')'), ('<', '>'), ('[', ']'),
                        ('"', '"'), ("'", "'")]
WORD_SPLIT_RE = re.compile(r'''([\s<>"']+)''')
SIMPLE_URL_RE = re.compile(r'^https?://\[?\w', re.IGNORECASE)


def extract_urls(text):
    """Return an iterator yielding URLs contained in *text*."""
    for word in WORD_SPLIT_RE.split(text):
        if not ('.' in word or ':' in word):
            continue
        # Deal with punctuation.
        lead, middle, trail = '', word, ''
        for punctuation in TRAILING_PUNCTUATION:
            if middle.endswith(punctuation):
                middle = middle[:-len(punctuation)]
                trail = punctuation + trail
        for opening, closing in WRAPPING_PUNCTUATION:
            if middle.startswith(opening):
                middle = middle[len(opening):]
                lead = lead + opening
            # Keep parentheses at the end only if they're balanced.
            if (middle.endswith(closing)
                    and middle.count(closing) == middle.count(opening) + 1):
                middle = middle[:-len(closing)]
                trail = closing + trail
        # Yield the resulting URL.
        if SIMPLE_URL_RE.match(middle):
            yield middle


class URLTitleFetcher(object):
    """Reply to messages containing URLs with an appropriate title (the
    contents of the <title> element for HTML pages, the first line for
    plain text documents, and so forth.)"""
    implements(IPlugin, IHandler)
    name = 'url'

    def __init__(self):
        self.ignore_list = []

    def registered(self):
        self.ignore_list = self.factory.config.getspacelist(
            'url', 'ignore_messages_from')

    def privmsg(self, bot, prefix, channel, message):
        nick = prefix.split('!', 1)[0]
        if nick in self.ignore_list:
            return
        fetchers = []
        for url in extract_urls(message):
            # Perform some basic URL format sanity checks.
            parsed = urlparse(url)
            hostname = parsed.hostname
            if hostname is None:
                log.msg('Could not extract hostname from URL {}; '
                        'ignoring' % url)
                continue
            log.msg('Saw URL %s from %s in channel %s' %
                    (url, prefix, channel))
            url, frag = urldefrag(url)
            # Look for "crawlable" AJAX URLs with fragments that begin
            # with "#!", and transform them to use "_escaped_fragment_".
            #
            # <http://code.google.com/web/ajaxcrawling/>
            if frag.startswith('!'):
                url += ('&' if '?' in url else '?' +
                        '_escaped_fragment_=' + urllib.quote(frag[1:]))
            d = self.get_title(url, hostname)
            d.addErrback(self.make_error_reply, hostname)
            fetchers.append(d)
        l = DeferredList(fetchers)
        l.addCallback(self.reply, bot, prefix, channel)
        return l

    action = privmsg

    @inlineCallbacks
    def get_title(self, url, hostname):
        response, title = yield fetch_title(url, with_response=True)
        # Add a hostname tag to the returned title, indicating any
        # redirects to a different host that occurred.
        final_hostname = urlparse(response.request.absoluteURI).hostname
        if hostname != final_hostname:
            hostname_tag = u'{} \u2192 {}'.format(hostname, final_hostname)
        else:
            hostname_tag = hostname
        returnValue((hostname_tag, title))

    def make_error_reply(self, failure, hostname):
        message = None
        if failure.check(ResponseFailed):
            if any(f.check(InfiniteRedirection)
                   for f in failure.value.reasons):
                message = u'Encountered too many redirects.'
            else:
                message = u'Received incomplete response from server.'
        elif failure.check(ConnectError, DNSLookupError, BlacklistedHost):
            message = u'Could not connect to server.'
        else:
            log.err(failure, 'Encountered an error in URL processing.')
        return (hostname, u'Error: {:s}'.format(message or failure.value))

    def reply(self, results, bot, prefix, channel):
        for i, result in enumerate(results):
            success, value = result
            if success:
                hostname, title = value
                title = u'[{}] {}'.format(hostname, title)
            else:
                log.err(value, 'Encountered an error in URL processing.')
                title = u'Error: \x02{:s}\x02.'.format(value.value)
            if len(title) >= 140:
                title = u'{}\u2026{}'.format(title[:64], title[-64:])
            if len(results) > 1:
                message = u'URL ({}/{}): {}'.format(i + 1, len(results), title)
            else:
                message = u'URL: {}'.format(title)
            if channel == bot.nickname:
                bot.reply(prefix, channel, message)
            else:
                bot.reply(None, channel, message)


default = URLTitleFetcher()
