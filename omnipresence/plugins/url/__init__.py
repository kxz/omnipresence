# -*- coding: utf-8 -*-
import cgi
import re
import socket
import struct
import urllib
import urlparse

from twisted.internet import defer, error, threads
from twisted.plugin import getPlugins, pluginPackagePaths, IPlugin
from twisted.python import log
from twisted.web import error as tweberror
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

# Based on django.utils.html.urlize from the Django project.
TRAILING_PUNCTUATION = ['.', ',', ':', ';']
WRAPPING_PUNCTUATION = [('(', ')'), ('<', '>')]

word_split_re = re.compile(r'(\s+)')
simple_url_re = re.compile(r'^https?://\w', re.IGNORECASE)

def extract_urls(text):
    """Return an iterator yielding URLs contained in *text*."""
    for word in word_split_re.split(text):
        if '.' in word or ':' in word:
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
            if simple_url_re.match(middle):
                yield middle

def is_private_host(hostname):
    """Check if the given host corresponds to a private network, as
    specified by RFC 1918.  Only supports IPv4."""
    addr = socket.gethostbyname(hostname)
    addr = struct.unpack('!I', socket.inet_aton(addr))[0]
    if ((addr >> 24 == 0x00  )   # 0.0.0.0/8
     or (addr >> 24 == 0x0A  )   # 10.0.0.0/8
     or (addr >> 24 == 0x7F  )   # 127.0.0.0/8
     or (addr >> 16 == 0xA9DE)   # 169.254.0.0/16
     or (addr >> 20 == 0xAC1 )   # 172.16.0.0/12
     or (addr >> 16 == 0xC0A8)): # 192.168.0.0/16
        return True
    return False

#
# Plugin interfaces and helper classes
#

class Redirect(object):
    """Returned by title processors to indicate a "soft" redirect, such
    as an HTML ``<meta>`` refresh.  The *location* parameter indicates
    the new URL to fetch."""

    def __init__(self, location):
        self.location = location


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

    title_processors = {}

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
                log.msg('Could not extract hostname from URL {0}; '
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
    def get_title(self, url, hostname, redirect_count=0):
        # Twisted Names is full of headaches.  socket is easier.
        private = yield threads.deferToThread(is_private_host,
                                              hostname.encode('utf8'))
        if private:
            # Pretend that the given host just doesn't exist.
            raise error.TimeoutError()

        # Fetch the title from a title processor if one is available for
        # the response's Content-Type, or craft a default one.
        hostname_tag = None
        title = u'No title found.'
        headers, content = yield web.request('GET', url.encode('utf8'),
                                             max_bytes=MAX_DOWNLOAD_SIZE)
        ctype, cparams = cgi.parse_header(headers.get('Content-Type', ''))
        if ctype in self.title_processors:
            title_processor = self.title_processors[ctype]
            processed = yield threads.deferToThread(
                                title_processor.process, headers, content)
            if isinstance(processed, Redirect):
                if redirect_count < MAX_SOFT_REDIRECTS:
                    # Join the new location with the current URL, in
                    # order to handle relative URIs.
                    location = urlparse.urljoin(url, processed.location)
                    hostname_tag, processed = yield self.get_title(
                                                      location, hostname,
                                                      redirect_count + 1)
                else:
                    raise tweberror.InfiniteRedirection(
                            599, 'Too many soft redirects',
                            location=processed.location)
            title = processed or title
        else:
            title = u'{0} document'.format(ctype or u'Unknown')
            clength = headers.get('X-Omni-Length')
            if clength:
                try:
                    clength = int(clength, 10)
                except ValueError:
                    # Couldn't parse the content-length string.
                    pass
                else:
                    title += u' ({0})'.format(add_si_prefix(clength, 'byte'))

        # Add a hostname tag to the returned title, indicating any
        # redirects to a different host that occurred.
        final_hostname = hostname
        if hostname_tag:
            # Some soft redirection occurred during title processing.
            final_hostname = hostname_tag.split()[-1]
        else:
            location = headers.get('X-Omni-Location')
            if location:
                final_hostname = urlparse.urlparse(location).hostname
        if final_hostname is not None and hostname != final_hostname:
            hostname_tag = u'{0} \u2192 {1}'.format(hostname, final_hostname)
        else:
            hostname_tag = hostname

        defer.returnValue((hostname_tag, title))

    def make_error_reply(self, failure, hostname):
        log.err(failure, 'Encountered an error in URL processing.')
        return (hostname, u'Error: {0:s}'.format(failure.value))

    def reply(self, results, bot, prefix, channel):
        for i, result in enumerate(results):
            success, value = result

            if success:
                hostname, title = value
                title = u'[{0}] {1}'.format(hostname, title)
            else:
                # This should only happen if make_reply() bombs.
                log.err(value, 'Encountered an error in URL processing.')
                title = u'Error: \x02{0:s}\x02.'.format(value.value)

            if len(title) >= 140:
                title = u'{0}…{1}'.format(title[:64], title[-64:])

            if len(results) > 1:
                message = u'URL ({0}/{1}): {2}'.format(i + 1, len(results),
                                                       title)
            else:
                message = u'URL: {0}'.format(title)

            # In the event that we're enabled for private messages...
            if channel == bot.nickname:
                bot.reply(prefix, channel, message)
            else:
                bot.reply(None, channel, message)


url = URLTitleFetcher()
