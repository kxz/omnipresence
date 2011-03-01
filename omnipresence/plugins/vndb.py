import urllib

from BeautifulSoup import BeautifulSoup
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import html, util
from omnipresence.iomnipresence import ICommand

class VNDBSearch(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search for a visual novel with
    the given name on VNDB <http://vndb.org/>.
    """
    implements(IPlugin, ICommand)
    name = 'vndb'
    
    def reply_with_result(self, response, bot, prefix,
                          reply_target, channel, args):
        soup = BeautifulSoup(response[1])
        results = soup.find('div', 'mainbox browse vnbrowse')
        
        if not results:
            # We were redirected to a visual novel page, as there is
            # only one result for the given search string.
            url = response[0]['content-location']

            data = soup.find('div', id='maincontent')
            title = html.textify_html(data.find('h1'))
            alt_title = data.find('h2', 'alttitle')
            alt_title = (u' (\x02%s\x02)' % html.textify_html(alt_title)
                         if alt_title else u'')
            release_date = html.textify_html(data.find('td', 'tc1'))
            votestats = data.find('div', 'votestats')
            if votestats:
                rating = html.textify_html(votestats.findAll('p')[-1])
                rating = rating.rsplit(None, 1)[-1]

                votes = html.textify_html(votestats.tfoot.find('td',
                                                               colspan='2'))
                votes = votes.split(None, 1)[0]

                rating = u'%s (%s)' % (rating, votes)
            else:
                rating = u''
        elif results.thead.nextSibling:
            data = results.thead.nextSibling.findAll('td')
            url = 'http://vndb.org' + data[0].a['href']
            title = html.textify_html(data[0].a)
            alt_title = data[0].a['title']
            alt_title = u'' if (alt_title == title) else (u' (\x02%s\x02)'
                                                           % alt_title)
            release_date = html.textify_html(data[3])
            rating = html.textify_html(data[5])
            if rating == u'0.00 (0)':
                rating = u''
        else:
            bot.reply(prefix, channel, 'VNDB: No results found for '
                                       '\x02%s\x02.' % args[1])
            return
        
        if release_date == u'TBA':
            release_date = u''
        else:
            release_date = u', first release %s' % release_date
        if rating:
            rating = u' \u2014 rated %s' % rating

        bot.reply(reply_target, channel,
                  (u'VNDB: \x02%s\x02%s%s%s \u2014 %s'
                     % (title, alt_title, release_date, rating, url)) \
                  .encode(self.factory.encoding))
    
    def execute(self, bot, prefix, channel, args):
        (args, reply_target) = util.redirect_command(args, prefix, channel)
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        params = urllib.urlencode({'q': args[1], 's': 'pop', 'o': 'd'})
                                               # popularity, descending
        d = self.factory.get_http('http://vndb.org/v/all?' + params)
        d.addCallback(self.reply_with_result, bot, prefix, reply_target, channel, args)
        return d


vndb = VNDBSearch()
