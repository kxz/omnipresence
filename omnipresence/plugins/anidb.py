import re
import urllib

from BeautifulSoup import BeautifulSoup
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import html, util
from omnipresence.iomnipresence import ICommand, IHandler

ANIDB_DATE_RE = re.compile(r'(?P<day>[0-9?]+)\.(?P<month>[0-9?]+)\.'
                           r'(?P<year>[0-9?]+)')

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


class AniDBSearchCommand(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search AniDB <http://anidb.net/>
    for anime series with the given title.
    """
    implements(IPlugin, ICommand)
    name = 'anidb'
    
    def reply_with_anime(self, response, bot, prefix, reply_target, channel, args):
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
        anime_all = soup.find('div', 'g_content anime_all')
        
        if animelist:
            # Skip the first header row and grab the second row.
            anime_row = animelist.findAll('tr')[1]
            aid = anime_row.find('a')['href'].rsplit('=', 1)[1]
            name = html.textify_html(anime_row.find('td', 'name'))
            atype = html.textify_html(anime_row.find('td', {'class':
                                                     re.compile('^type')}))
            episodes = html.textify_html(anime_row.find('td', 'count eps'))
            if 'TBC' in episodes:
                episodes = ''
            airdate = html.textify_html(anime_row.find('td', 'date airdate'))
            enddate = html.textify_html(anime_row.find('td', 'date enddate'))
            if '-' in enddate:
                enddate = ''
            rating = html.textify_html(anime_row.find('td', 'rating perm'))
        
        # Now for the "single result" case.
        elif anime_all:
            # The regular expression matches for some fields are needed
            # because "g_odd" may be added to their class names.
            
            aid = response[0]['content-location'].rsplit('=', 1)[1]
            # Grab the title from the <h1> element, and yank the
            # "Anime: " prefix off of it.  We use soup.find here
            # because the heading is not inside anime_all.
            name = html.textify_html(soup.find('h1', 'anime'))[7:]
            
            type_cell = html.textify_html(anime_all.find('tr', {'class':
                                                         re.compile('type$')}) \
                                                   .find('td', 'value'))
            type_cell = type_cell.split(', ')
            atype = type_cell[0]
            episodes = type_cell[1].split()[0]
            if 'unknown' in episodes:
                episodes = ''
            
            year_cell = html.textify_html(anime_all.find('tr', {'class':
                                                         re.compile('year$')}) \
                                                   .find('td', 'value'))
            if 'till' in year_cell:
                (airdate, enddate) = year_cell.split(' till ')
                if '?' in enddate:
                    enddate = ''
            else:
                # Anime aired on a single day.
                airdate = year_cell
                enddate = airdate
            
            # Try to get the permanent rating first; if it's "N/A", then
            # move to the temporary rating.
            rating = html.textify_html(anime_all.find('tr', {'class':
                                                      re.compile(r'\brating$')}) \
                                                .find('td', 'value'))
            if 'N/A' in rating:
                rating = html.textify_html(anime_all.find('tr', {'class':
                                                          re.compile('tmprating$')}) \
                                                    .find('td', 'value'))
            # Get rid of the "(weighted)" note.
            rating = ' '.join(rating.split()[:2])
        
        # And all other cases.
        else:
            bot.reply(prefix, channel, 'AniDB: No results were found for '
                                       '\x02%s\x02.' % args[1])
            return
        
        reply = u'AniDB: %s \u2014 %s' % (name.strip(), atype.strip())
        episodes = episodes.strip()
        if episodes == '1':
            reply += u', 1 episode'
        elif episodes:
            reply += u', %s episodes' % episodes
        
        airdate = parse_anidb_date(airdate.strip())
        enddate = parse_anidb_date(enddate.strip())
        
        if enddate and airdate != enddate:
            reply += u' from %s to %s' % (airdate, enddate)
        elif airdate == enddate:
            reply += u' on %s' % airdate
        else:
            reply += u' starting %s' % airdate
        
        if not rating.startswith('N/A'):
            reply += u' \u2014 rated %s' % rating.strip()
        
        reply += u' \u2014 http://anidb.net/a%s' % aid.strip()
        
        bot.reply(reply_target, channel, reply.encode(self.factory.encoding))
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        # "do.update" must be passed, or "noalias" is ignored.
        params = {'show': 'animelist', 'orderby.ucnt': '0.2',
                  'do.update': 'update', 'noalias': 1, 'adb.search': args[1]}
        
        d = self.factory.get_http('http://anidb.net/perl-bin/animedb.pl?%s'
                                   % urllib.urlencode(params))
        d.addCallback(self.reply_with_anime, bot, prefix, reply_target, channel, args)
        return d

a = AniDBSearchCommand()
