# -*- test-case-name: omnipresence.plugins.url.test_url
import cgi
from collections import namedtuple
import re
import socket
import sys
import urllib
import urlparse

import ipaddress
from twisted.internet import defer, reactor, protocol, threads
from twisted.internet.error import ConnectError, DNSLookupError
from twisted.plugin import getPlugins, pluginPackagePaths, IPlugin
from twisted.python import log
from twisted.python.failure import Failure
from twisted.web.client import (IAgent, Agent, ContentDecoderAgent,
                                RedirectAgent, GzipDecoder, ResponseFailed)
from twisted.web.error import InfiniteRedirection
from twisted.web.iweb import UNKNOWN_LENGTH
from zope.interface import implements, Interface, Attribute

from omnipresence import plugins, web
from omnipresence.iomnipresence import IHandler


# Make twisted.plugin.getPlugins() look for plug-ins in this module.
__path__.extend(pluginPackagePaths(__name__))
__all__ = []


"""The maximum number of bytes the fetcher will download for a single
title fetch request."""
MAX_DOWNLOAD_SIZE = 65536

"""The maximum number of "soft" redirects that will be followed."""
MAX_SOFT_REDIRECTS = 2


#
# Utility methods
#

def add_si_prefix(number, unit, plural_unit=None):
    """Returns a string containing an approximate representation of the
    given number and unit, using a decimal SI prefix.  *number* is
    assumed to be a positive integer. If *plural_unit* is not specified,
    it defaults to *unit* with an "s" appended."""
    if not plural_unit:
        plural_unit = unit + 's'

    if number == 1:
        return '{0:n} {1}'.format(number, unit)

    prefix = ''
    for prefix in ('', 'kilo', 'mega', 'giga', 'tera',
                   'exa', 'peta', 'zetta', 'yotta'):
        if number < 1000:
            break

        number /= 1000.0

    if prefix:
        return '{0:.3n} {1}{2}'.format(number, prefix, plural_unit)

    return '{0:n} {1}'.format(number, plural_unit)


#
# Utility methods
#

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


#
# Twisted HTTP machinery
#

class TruncatingReadBodyProtocol(protocol.Protocol):
    """A protocol that collects data sent to it up to a maximum of
    *max_bytes*, then discards the rest."""

    def __init__(self, status, message, finished, max_bytes=None):
        self.status = status
        self.message = message
        self.finished = finished
        self.data_buffer = []
        self.remaining = max_bytes or sys.maxsize

    def dataReceived(self, data):
        if self.remaining > 0:
            to_buffer = data[:self.remaining]
            self.data_buffer.append(to_buffer)
            self.remaining -= len(to_buffer)
        if self.remaining <= 0:
            self.transport.loseConnection()

    def connectionLost(self, reason):
        if not self.finished.called:
            self.finished.callback(''.join(self.data_buffer))


class BlacklistedHost(Exception):
    """Raised when a `BlacklistingAgent` attempts to request a
    blacklisted resource."""

    def __init__(self, hostname, ip):
        self.hostname = hostname
        self.ip = ip

    def __str__(self):
        return 'host {} corresponds to blacklisted IP {}'.format(
            self.hostname, self.ip)


class BlacklistingAgent(object):
    """An `~twisted.web.client.Agent` wrapper that forbids requests to
    loopback, private, and internal IP addresses."""
    implements(IAgent)

    def __init__(self, agent, resolve=None):
        self.agent = agent
        self.resolve = resolve or reactor.resolve

    @defer.inlineCallbacks
    def request(self, method, uri, headers=None, bodyProducer=None):
        """Issue a request to the server indicated by *uri*."""
        hostname = urlparse.urlparse(uri).hostname
        ip_str = yield self.resolve(hostname)
        # `ipaddress` takes a Unicode string and I don't really care to
        # handle `UnicodeDecodeError` separately.
        ip = ipaddress.ip_address(ip_str.decode('ascii', 'replace'))
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise BlacklistedHost(hostname, ip)
        response = yield self.agent.request(method, uri, headers, bodyProducer)
        defer.returnValue(response)

agent = ContentDecoderAgent(
    RedirectAgent(BlacklistingAgent(Agent(reactor))),
    [('gzip', GzipDecoder)])


#
# Plugin interfaces and helper classes
#

#: Returned by title processors to indicate a "soft" redirect, such as
#: an HTML ``<meta>`` refresh.  The *location* parameter indicates the
#: new URL to fetch.
Redirect = namedtuple('Redirect', ['location'])


class ITitleProcessor(Interface):
    """A plugin that can retrieve the title of a given Web document."""

    supported_content_types = Attribute("""
        An iterable containing the MIME content types that this title
        processor supports; for example, ``('image/gif', 'text/xml')``.
        """)

    def process(self, headers, content):
        """Implement this method in your title processor class.  The
        *headers* and *content* arguments are in the format returned by
        :py:meth:`omnipresence.web.request()`.

        This method should either return a Unicode string containing the
        extracted title, or a :py:class:`Redirect` object pointing at a
        new URL from which to fetch a document title.
        """

#
# Actual handler plugin
#

class URLTitleFetcher(object):
    """
    Reply to messages containing URLs with an appropriate title (the
    contents of the <title> element for HTML pages, the first line for
    plain text documents, and so forth.)
    """
    implements(IPlugin, IHandler)
    name = 'url'

    def __init__(self):
        self.ignore_list = []
        self.title_processors = {}

    def registered(self):
        self.ignore_list = self.factory.config.getspacelist(
                             'url', 'ignore_messages_from')
        for title_processor in getPlugins(ITitleProcessor, plugins.url):
            for content_type in title_processor.supported_content_types:
                self.title_processors[content_type] = title_processor

    def privmsg(self, bot, prefix, channel, message):
        nick = prefix.split('!', 1)[0]

        if nick in self.ignore_list:
            return

        # Everything in here is Unicode.
        message = message.decode(self.factory.encoding, 'ignore')
        fetchers = []
        for url in extract_urls(message):
            # Perform some basic URL format sanity checks.
            parsed = urlparse.urlparse(url)
            # Make sure we have a valid hostname.
            hostname = parsed.hostname
            if hostname is None:
                log.msg('Could not extract hostname from URL {}; '
                        'ignoring.'.format(url.encode('utf8')))
                continue

            # Okay, everything looks good.  Log the seen URL.
            log.msg('Saw URL %s from %s in channel %s.'
                    % (url.encode('utf8'), prefix, channel))

            # Strip the fragment portion of the URL, if present.
            url, frag = urlparse.urldefrag(url)

            # Look for "crawlable" AJAX URLs with fragments that begin
            # with "#!", and transform them to use "_escaped_fragment_".
            #
            # <http://code.google.com/web/ajaxcrawling/>
            if frag.startswith('!'):
                url += (u'&' if u'?' in url else u'?' +
                        u'_escaped_fragment_=' +
                        urllib.quote(frag[1:].encode('utf8')))

            # Make the actual request.
            d = self.get_title(url, hostname)
            d.addErrback(self.make_error_reply, hostname)
            fetchers.append(d)

        l = defer.DeferredList(fetchers)
        l.addCallback(self.reply, bot, prefix, channel)
        return l

    action = privmsg

    @defer.inlineCallbacks
    def get_title(self, url, hostname):
        # Fetch the title from a title processor if one is available for
        # the response's Content-Type, or craft a default one.
        title = None
        for _ in xrange(MAX_SOFT_REDIRECTS):
            response = yield agent.request('GET', url.encode('utf8'))
            clength = response.length
            headers = {k: v[0] for k, v in response.headers.getAllRawHeaders()}
            headers['X-Omni-Length'] = str(clength)
            finished = defer.Deferred()
            response.deliverBody(TruncatingReadBodyProtocol(
                response.code, response.phrase, finished, MAX_DOWNLOAD_SIZE))
            content = yield finished
            ctype, cparams = cgi.parse_header(headers.get('Content-Type', ''))
            if ctype in self.title_processors:
                title_processor = self.title_processors[ctype]
                processed = yield threads.deferToThread(
                    title_processor.process, headers, content)
                if isinstance(processed, Redirect):
                    # Join the new location with the current URL, in
                    # order to handle relative URLs.
                    url = urlparse.urljoin(url, processed.location)
                    continue
                title = processed
            # The only case where we'd want to loop again is when the
            # response returned is a soft redirect.
            break
        else:
            raise ResponseFailed([Failure(InfiniteRedirection(
                599, 'Too many soft redirects', location=url))])
        if title is None:
            title = u'{} document'.format(ctype or u'Unknown')
            if clength is not UNKNOWN_LENGTH:
                title += u' ({})'.format(add_si_prefix(clength, 'byte'))

        # Add a hostname tag to the returned title, indicating any
        # redirects to a different host that occurred.
        final_hostname = urlparse.urlparse(
            response.request.absoluteURI).hostname
        if hostname != final_hostname:
            hostname_tag = u'{} \u2192 {}'.format(hostname, final_hostname)
        else:
            hostname_tag = hostname

        defer.returnValue((hostname_tag, title))

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

            # In the event that we're enabled for private messages...
            if channel == bot.nickname:
                bot.reply(prefix, channel, message)
            else:
                bot.reply(None, channel, message)


url = URLTitleFetcher()
