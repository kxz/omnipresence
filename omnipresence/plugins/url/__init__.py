# -*- test-case-name: omnipresence.plugins.url.test_url
"""Event plugins for previewing the content of mentioned URLs."""


import re

from littlebrother import TitleFetcher
from twisted.internet.defer import DeferredList

from ...plugin import EventPlugin
from ...web.http import IdentifyingAgent


# Based on django.utils.html.urlize from the Django project.
TRAILING_PUNCTUATION = [u'.', u',', u':', u';', u'.)', u'"', u"'", u'!']
WRAPPING_PUNCTUATION = [(u'(', u')'), (u'<', u'>'), (u'[', u']'),
                        (u'"', u'"'), (u"'", u"'")]
WORD_SPLIT_RE = re.compile(ur"""([\s<>"']+)""")
SIMPLE_URL_RE = re.compile(ur'^https?://\[?\w', re.IGNORECASE | re.UNICODE)


def extract_iris(text):
    """Return an iterator yielding IRIs from a Unicode string."""
    for word in WORD_SPLIT_RE.split(text):
        if not (u'.' in word or u':' in word):
            continue
        # Deal with punctuation.
        lead, middle, trail = u'', word, u''
        for punctuation in TRAILING_PUNCTUATION:
            if middle.endswith(punctuation):
                middle = middle[:-len(punctuation)]
                trail = punctuation + trail
        for opening, closing in WRAPPING_PUNCTUATION:
            if middle.startswith(opening):
                middle = middle[len(opening):]
                lead += opening
            # Keep parentheses at the end only if they're balanced.
            if (middle.endswith(closing) and
                    middle.count(closing) == middle.count(opening) + 1):
                middle = middle[:-len(closing)]
                trail = closing + trail
        # Yield the resulting URL.
        if SIMPLE_URL_RE.match(middle):
            yield middle


class Default(EventPlugin):
    def __init__(self):
        self.fetcher = TitleFetcher()
        self.fetcher.agent = IdentifyingAgent(self.fetcher.agent)

    def on_privmsg(self, msg):
        fetches = []
        for iri in extract_iris(msg.content.decode(msg.encoding, 'replace')):
            self.log.debug(
                'Saw URL {iri} from {msg.actor} in venue {msg.venue}',
                iri=iri.encode('utf-8'), msg=msg)
            fetches.append(self.fetcher.fetch_title(
                iri, hostname_tag=True, friendly_errors=True))
        finished = DeferredList(fetches)
        finished.addCallback(self.send_replies, msg)
        return finished

    on_action = on_privmsg

    def send_replies(self, results, msg):
        for success, value in results:
            if success:
                msg.connection.reply(value, msg)
            else:
                self.log.failure(
                    'Unhandled error during URL title extraction',
                    failure=value)
