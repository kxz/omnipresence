"""Commands related to AniDB."""
import re

from bs4 import BeautifulSoup

from omnipresence.web import textify_html as txt, WebCommand


ANIDB_DATE_RE = re.compile(
                  r'(?P<day>[0-9?]+)\.(?P<month>[0-9?]+)\.(?P<year>[0-9?]+)')

def row_value(soup, html_class):
    return txt(soup.find('tr', html_class).find('td', 'value'))

def parse_anidb_date(date):
    """
    Turn an AniDB day.month.year date, potentially with "??" in certain
    fields, into an ISO 8601 formatted date that omits missing fields.
    """
    match = ANIDB_DATE_RE.match(date)
    if not match:
        return date
    iso8601 = []
    for part in ('year', 'month', 'day'):
        if '?' in match.group(part):
            break
        else:
            iso8601.append(match.group(part))
    return '-'.join(iso8601)


class AnimeSearch(WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search AniDB <http://anidb.net/>
    for anime series with the given title.
    """
    name = 'anidb'
    arg_type = 'a search query'
    # (1) We sort by user count as an approximation of relevance.
    # (2) "do.update" must be passed, or "noalias" is ignored.
    url = ('http://anidb.net/perl-bin/animedb.pl?show=animelist&adb.search=%s&'
           'orderby.ucnt=0.2&do.update=update&noalias=1')
    
    def reply(self, response, bot, prefix, reply_target, channel, args):
        results = []
        soup = BeautifulSoup(response[1])
        
        # We may get one of three differently-formatted responses
        # depending on the number of results: if there are no results,
        # an animelist page with a notice; if there are multiple
        # results, an animelist page with a table containing them; and
        # if there is only one result, an individual anime page.  All of
        # these cases have to be handled differently.
        #
        # It's easiest to leave the "zero results" case to be lumped in
        # with unexpected cases in an "else", so we'll start with the
        # "multiple result" case.
        animelist = soup.find('table', 'animelist')
        anime_all = soup.find('div', 'anime_all')
        
        if animelist:
            # Skip the first header row and grab the second row.
            for row in animelist('tr')[1:]:
                anime = { 'aid': row.find('a')['href'].rsplit('=', 1)[1],
                          'name': txt(row.find('td', 'name')),
                          'atype': txt(row.find('td', 'type')),
                          'episodes': txt(row.find('td', 'eps')),
                          'airdate': txt(row.find('td', 'airdate')),
                          'enddate': txt(row.find('td', 'enddate')),
                          'rating': txt(row.find('td', 'weighted'))
                        }
                if 'TBC' in anime['episodes']:
                    anime['episodes'] = ''
                if '-' in anime['enddate']:
                    anime['enddate'] = ''
                results.append(anime)
        
        # Now for the "single result" case.
        elif anime_all:
            type_cell = row_value(anime_all, 'type').split(', ')

            anime = { 'aid': response[0]['X-Omni-Location'].rsplit('=', 1)[1],
                      # Grab the title from the <h1> element, and yank the
                      # "Anime: " prefix off of it.  We use soup.find here
                      # because the heading is not inside anime_all.
                      'name': txt(soup.find('h1', 'anime'))[7:],
                      'atype': type_cell[0]
                    }
            
            anime['episodes'] = ''
            if len(type_cell) > 1:
                anime['episodes'] = type_cell[1].split()[0]
                if 'unknown' in anime['episodes']:
                    anime['episodes'] = ''

            year_cell = row_value(anime_all, 'year')
            if 'till' in year_cell:
                anime['airdate'], anime['enddate'] = year_cell.split(' till ')
                if anime['enddate'] == '?':
                    anime['enddate'] = ''
            else:
                # Anime aired on a single day.
                anime['airdate'] = year_cell
                anime['enddate'] = anime['airdate']
            
            # Try to get the permanent rating first; if it's "N/A", then
            # move to the temporary rating.
            rating = row_value(anime_all, 'rating')
            if 'N/A' in rating:
                rating = row_value(anime_all, 'tmprating')
            # Get rid of the "(weighted)" note.
            anime['rating'] = ' '.join(rating.split()[:2])
            results.append(anime)
        
        # And all other cases.
        else:
            bot.reply(prefix, channel, 'AniDB: No results were found for '
                                       '\x02%s\x02.' % args[1])
            return
        
        messages = []
        for i, anime in enumerate(results):
            message = u'AniDB: ({0}/{1}) \x02{2}\x02 \u2014 {3}'.format(
              i + 1, len(results),
              anime['name'].strip(), anime['atype'].strip())
            episodes = anime['episodes'].strip()
            if episodes == '1':
                message += u', 1 episode'
            elif episodes:
                message += u', {0} episodes'.format(episodes)
            airdate = parse_anidb_date(anime['airdate'].strip())
            enddate = parse_anidb_date(anime['enddate'].strip())
            if enddate and airdate != enddate:
                message += u' from {0} to {1}'.format(airdate, enddate)
            elif airdate == enddate:
                message += u' on {0}'.format(airdate)
            else:
                message += u' starting {0}'.format(airdate)
            if not anime['rating'].startswith('N/A'):
                message += u' \u2014 rated {0}'.format(anime['rating'].strip())
            message += u' \u2014 http://anidb.net/a{0}'.format(anime['aid'].strip())
            messages.append(message)
        
        bot.reply(reply_target, channel, u'\n'.join(messages))

anime = AnimeSearch()
