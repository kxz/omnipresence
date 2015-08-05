# -*- test-case-name: omnipresence.plugins.vndb.test_vndb
"""Event plugins for searching the Visual Novel Database."""


import urllib
from urlparse import urljoin

from bs4 import BeautifulSoup
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import readBody

from ...message import collapse
from ...plugin import EventPlugin, UserVisibleError
from ...web.html import textify
from ...web.http import default_agent


class Default(EventPlugin):
    def __init__(self):
        self.agent = default_agent

    @inlineCallbacks
    def on_command(self, msg):
        if not msg.content:
            raise UserVisibleError('Please specify a search query.')
        q = urllib.quote_plus(msg.content)
        response = yield self.agent.request(
            'GET', 'https://vndb.org/v/all?s=pop&o=d&q={}'.format(q))
        content = yield readBody(response)
        soup = BeautifulSoup(content)

        # TODO:  Implement page navigation.
        results = []
        vnbrowse = soup.find('div', 'vnbrowse')
        if vnbrowse:  # either zero results, or more than one result
            # Don't recurse into children, to avoid picking up the row
            # contained within the <thead> element.
            for row in vnbrowse.table('tr', recursive=False):
                row_data = row('td')
                vn = {'url': urljoin(response.request.absoluteURI,
                                     row_data[0].a['href']),
                      'title': textify(row_data[0].a),
                      'release_date': textify(row_data[3]) }
                alt_title = row_data[0].a['title']
                if alt_title != vn['title']:
                    vn['alt_title'] = alt_title
                rating = textify(row_data[5], format_output=False)
                if not rating.startswith(u'0.00'):
                    vn['rating'] = rating
                results.append(vn)
        else:  # single result, redirecting to an individual VN page
            data = soup.find('div', id='maincontent')
            vn = {'url': response.request.absoluteURI,
                  'title': textify(data.find('h1')),
                  'release_date': textify(data.find('td', 'tc1')) }
            alt_title = data.find('h2', 'alttitle')
            if alt_title:
                vn['alt_title'] = textify(alt_title)
            votestats = data.find('div', 'votestats')
            if votestats:
                rating = textify(votestats('p')[-1])
                rating = rating.rsplit(None, 1)[-1]
                votes = textify(votestats.tfoot.find('td', colspan='2'))
                votes = votes.split(None, 1)[0]
                vn['rating'] = u'{0} ({1})'.format(rating, votes)
            results.append(vn)

        if not results:
            raise UserVisibleError('No results found for \x02{}\x02.'
                                   .format(msg.content))
        messages = []
        for vn in results:
            message = u'{} \u2014 \x02{}\x02'.format(vn['url'], vn['title'])
            if 'alt_title' in vn:
                message += u' (\x02{}\x02)'.format(vn['alt_title'])
            if vn['release_date'] != u'TBA':
                message += u', first release ' + vn['release_date']
            if 'rating' in vn:
                message += u' \u2014 rated ' + vn['rating']
            messages.append(message)
        returnValue(messages)

    def on_cmdhelp(self, msg):
        return collapse("""\
            \x1Ftitle\x1F - Search the Visual Novel Database
            <https://vndb.org/> for visual novels with the given title.
            """)
