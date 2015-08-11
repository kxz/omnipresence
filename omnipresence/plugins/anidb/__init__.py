# -*- test-case-name: omnipresence.plugins.anidb.test_anidb
"""Event plugins for searching AniDB."""


import re
import urllib

from bs4 import BeautifulSoup
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import readBody

from ...message import collapse
from ...plugin import EventPlugin, UserVisibleError
from ...web.html import textify
from ...web.http import default_agent


#: A regex matching AniDB's day.month.year date format.
ANIDB_DATE = re.compile(r'^([0-9?]{2})\.([0-9?]{2})\.([0-9?]{4})$')

#: A regex matching the format of a "romaji" cell in an AniDB metadata
#: table; e.g., "Bakemonogatari (a6327)".
ROMAJI_VALUE = re.compile(r'^(.+) \(a([0-9]+)\)$')


def anidb_to_iso8601(date):
    """Turn an AniDB day.month.year date, potentially with "??" in one
    or more fields, into an ISO 8601 formatted date that omits missing
    fields."""
    return '-'.join(filter(lambda s: '?' not in s,
                           reversed(ANIDB_DATE.findall(date)[0])))


def row_value(table, html_class):
    """Get the value of the row with the given HTML class from a
    `BeautifulSoup` object representing an AniDB metadata table."""
    return textify(table.find('tr', html_class).find('td', 'value'))


def parse_animelist(animelist):
    """Parse an AniDB search results page and return a list of details
    from all of the anime on that page."""
    # Skip the first header row and grab the second row.
    results = []
    if not animelist:
        return results
    for row in animelist('tr')[1:]:
        anime = {'aid': row.find('a')['href'].rsplit('=', 1)[1],
                 'name': textify(row.find('td', 'name')),
                 'atype': textify(row.find('td', 'type')),
                 'episodes': textify(row.find('td', 'eps')),
                 'airdate': textify(row.find('td', 'airdate')),
                 'enddate': textify(row.find('td', 'enddate')),
                 'rating': textify(row.find('td', 'weighted'))}
        if 'TBC' in anime['episodes']:
            anime['episodes'] = ''
        if '-' in anime['enddate']:
            anime['enddate'] = ''
        results.append(anime)
    return results


def parse_anime_all(anime_all):
    """Parse an AniDB anime page and return a single-element list
    containing that anime's details."""
    if not anime_all:
        return []
    name, aid = ROMAJI_VALUE.findall(row_value(anime_all, 'romaji'))[0]
    type_value = row_value(anime_all, 'type').split(', ')
    anime = {'aid': aid, 'name': name, 'atype': type_value[0], 'episodes': ''}
    if len(type_value) > 1 and 'unknown' not in type_value:
        anime['episodes'] = type_value[1].split()[0]
    year_value = row_value(anime_all, 'year')
    if 'till' in year_value:
        anime['airdate'], anime['enddate'] = year_value.split(' till ')
        if anime['enddate'] == '?':
            anime['enddate'] = ''
    else:
        # Anime aired on a single day.
        anime['airdate'] = year_value
        anime['enddate'] = anime['airdate']
    # Try to get the permanent rating first; if it's "N/A", then
    # move to the temporary rating.
    rating = row_value(anime_all, 'rating')
    if 'N/A' in rating:
        rating = row_value(anime_all, 'tmprating')
    # Get rid of the "(weighted)" note.
    anime['rating'] = ' '.join(rating.split()[:2])
    return [anime]


class Default(EventPlugin):
    def __init__(self):
        self.agent = default_agent

    @inlineCallbacks
    def on_command(self, msg):
        if not msg.content:
            raise UserVisibleError('Please specify a search query.')
        # We sort by user count as an approximation of relevance.  The
        # "do.update" parameter must be passed, or "noalias" is ignored.
        response = yield self.agent.request('GET',
           'http://anidb.net/perl-bin/animedb.pl?show=animelist&'
           'adb.search={}&orderby.ucnt=0.2&do.update=update&noalias=1'
           .format(urllib.quote_plus(msg.content)))
        content = yield readBody(response)
        soup = BeautifulSoup(content)

        # We may get one of three differently-formatted responses
        # depending on the number of results: if there are no results,
        # an animelist page with a notice; if there are multiple
        # results, an animelist page with a table containing them; and
        # if there is only one result, an individual anime page.
        results = parse_animelist(soup.find('table', 'animelist'))
        if not results:
            results = parse_anime_all(soup.find('div', 'anime_all'))
        if not results:
            raise UserVisibleError('No results found for \x02{}\x02.'
                                   .format(msg.content))
        messages = []
        for anime in results:
            anime = {k: v.strip() for k, v in anime.iteritems()}
            message = (u'http://anidb.net/a{0[aid]} \u2014 '
                       u'\x02{0[name]}\x02 \u2014 {0[atype]}'.format(anime))
            episodes = anime['episodes']
            if episodes == '1':
                message += u', 1 episode'
            elif episodes:
                message += u', {} episodes'.format(episodes)
            airdate = anidb_to_iso8601(anime['airdate'])
            enddate = anidb_to_iso8601(anime['enddate'])
            if enddate and airdate != enddate:
                message += u' from {} to {}'.format(airdate, enddate)
            elif airdate == enddate:
                message += u' on {}'.format(airdate)
            else:
                message += u' starting {}'.format(airdate)
            if not anime['rating'].startswith('N/A'):
                message += u' \u2014 rated {}'.format(anime['rating'])
            messages.append(message)
        returnValue(messages)

    def on_cmdhelp(self, msg):
        return collapse("""\
            \x1Ftitle\x1F - Search AniDB <http://anidb.net/> for anime
            with the given title.
            """)
