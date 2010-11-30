import json
import urllib

from BeautifulSoup import BeautifulSoup
from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand

from omnipresence import util


def strip_redirect(s):
    return s.split('?from=', 1)[0]


class TVTropesSearch(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search for a TV Tropes article with a 
    title matching the given search string, or perform a full-text search if 
    no such article exists.
    """
    implements(IPlugin, ICommand)
    name = 'trope'
    
    def reply_with_trope(self, response, bot, user, channel, args, info_text=''):
        soup = BeautifulSoup(response[1])
        title = util.textify_html(soup.find('title')).split(' - ', 1)[0]
        
        bot.reply(user, channel, (u'TV Tropes%s: \x02%s\x02: %s'
                                    % (info_text, title,
                                       strip_redirect(response[0]['content-location']))) \
                                  .encode(self.factory.encoding))
    
    def reply_with_google(self, response, bot, user, channel, args):
        data = json.loads(response[1])
        
        if ('responseData' not in data or
            'results' not in data['responseData'] or
            len(data['responseData']['results']) < 1):
            bot.reply(user, channel, 'TV Tropes: No results found for \x02%s\x02.'
                                      % args[1])
            return
        
        result = data['responseData']['results'][0]
        bot.reply(user, channel, (u'TV Tropes (full-text): \x02%s\x02: %s'
                                    % (util.decode_html_entities(result['titleNoFormatting']).split(' - ', 1)[0],
                                       result['unescapedUrl'])) \
                                  .encode(self.factory.encoding))
    
    def find_trope(self, response, bot, user, channel, args):
        soup = BeautifulSoup(response[1])
        
        while soup.find('a', 'twikilink'):
            link = soup.find('a', 'twikilink').extract()
            
            try:
                result = link.attrMap['href']
            except KeyError:
                continue
            
            d = self.factory.get_http(result)
            d.addCallback(self.reply_with_trope, bot, user, channel, args)
            d.addErrback(bot.reply_with_error, user, channel, args[0])
            return            
        
        params = urllib.urlencode({'q': ('site:tvtropes.org inurl:pmwiki.php '
                                         '-"click the edit button" %s,')
                                          % args[1],
                                   'v': '1.0'})
        
        d = self.factory.get_http('http://ajax.googleapis.com/ajax/services/search/web?' + params)
        d.addCallback(self.reply_with_google, bot, user, channel, args)
        d.addErrback(bot.reply_with_error, user, channel, args[0])
    
    def execute(self, bot, user, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(user, channel, 'Please specify a search string.')
            return
        
        # Force the first character to uppercase for {{}} search; otherwise, 
        # the markup won't be parsed as a link if the query is all-lowercase.
        preview_query = ('[=~%s~=] {{%s%s}}'
                          % (args[1], args[1][0].upper(), args[1][1:]))
        params = {'source': preview_query}
        
        d = self.factory.get_http('http://tvtropes.org/pmwiki/preview.php',
                                  'POST', body=urllib.urlencode(params),
                                  headers={'Content-type':
                                           'application/x-www-form-urlencoded'})
        d.addCallback(self.find_trope, bot, user, channel, args)
        return d


class RandomTrope(TVTropesSearch):
    """
    \x02%s\x02 - Get a random TV Tropes article.
    """
    name = 'trope_random'
    
    def execute(self, bot, user, channel, args):
        d = self.factory.get_http('http://tvtropes.org/pmwiki/randomitem.php')
        d.addCallback(self.reply_with_trope, bot, user, channel, args, ' (random)')
        return d


trope = TVTropesSearch()
trope_random = RandomTrope()