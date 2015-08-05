# -*- test-case-name: omnipresence.plugins.google.test_google
"""Event plugins for Google searches."""


import urllib

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import readBody

from ...message import collapse
from ...plugin import EventPlugin, UserVisibleError
from ...web.html import textify
from ...web.http import default_agent, read_json_body


class SearchIterator(object):
    """An iterator returnable as an Omnipresence reply that fetches new
    Google result pages on demand."""

    endpoint_uri = 'https://www.googleapis.com/customsearch/v1'

    def __init__(self, agent, num, key, cx, q):
        self.agent = agent
        self.num = num
        self.key = key
        self.cx = cx
        self.q = q
        self.items = []
        self.start = 1
        self.total_results = NotImplemented

    def __iter__(self):
        return self

    @staticmethod
    def format_item(item):
        # Google inserts random newlines into HTML snippets that serve
        # no purpose and in fact appear where whitespace shouldn't be.
        snippet = item['htmlSnippet'].replace('\n', '')
        return u'{} \u2014 \x02{}\x02: {}'.format(
            item['link'], item['title'], textify(snippet))

    @inlineCallbacks
    def next(self):
        if self.items:
            self.total_results -= 1
            returnValue(SearchIterator.format_item(self.items.pop(0)))
        if self.start is None:
            # We can't use StopIteration because that gets eaten by
            # inlineCallbacks, so instead we just return None.
            returnValue(None)
        query_string = urllib.urlencode([
            ('key', self.key),
            ('cx', self.cx),
            ('q', self.q),
            ('num', self.num),
            ('start', self.start)])
        response = yield self.agent.request(
            'GET', '{}?{}'.format(self.endpoint_uri, query_string))
        data = yield read_json_body(response)
        if 'error' in data:
            raise UserVisibleError('Google API error: ' +
                                   data['error']['message'])
        self.items = data.get('items')
        if not self.items:
            raise UserVisibleError('No results found for \x02{}\x02.'
                                   .format(self.q))
        if self.start == 1:
            self.total_results = int(data['searchInformation']['totalResults'])
        if 'nextPage' in data['queries']:
            self.start = data['queries']['nextPage'][0]['startIndex']
        else:
            # The API will, bafflingly, return the last result if you
            # give it a start offset past the end of known results.
            self.start = None
        self.total_results -= 1
        returnValue(SearchIterator.format_item(self.items.pop(0)))

    def __length_hint__(self):
        return self.total_results


class Default(EventPlugin):
    def __init__(self):
        self.agent = default_agent
        self.num = 10  # number of results to request at each fetch

    def on_command(self, msg):
        if not msg.content:
            raise UserVisibleError('Please specify a search query.')
        return SearchIterator(self.agent, self.num,
                              msg.settings.get('google.key'),
                              msg.settings.get('google.cx'),
                              msg.content)

    def on_cmdhelp(self, msg):
        return collapse("""\
            \x1Fquery\x1F - Search Google using the given query.
            """)
