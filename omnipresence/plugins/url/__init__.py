# -*- test-case-name: omnipresence.plugins.url.test_url
"""Event plugins for previewing the content of mentioned URLs."""


import re
import sys
from urlparse import urlparse

import ipaddress
from twisted.internet import defer, reactor, protocol
from twisted.web.client import IAgent
from zope.interface import implements


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
        hostname = urlparse(uri).hostname
        ip_str = yield self.resolve(hostname)
        # `ipaddress` takes a Unicode string and I don't really care to
        # handle `UnicodeDecodeError` separately.
        ip = ipaddress.ip_address(ip_str.decode('ascii', 'replace'))
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise BlacklistedHost(hostname, ip)
        response = yield self.agent.request(method, uri, headers, bodyProducer)
        defer.returnValue(response)
