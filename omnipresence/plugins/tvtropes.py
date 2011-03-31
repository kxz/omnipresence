import json
import re
import urllib

from BeautifulSoup import BeautifulSoup
from twisted.internet import threads
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import html, util
from omnipresence.iomnipresence import ICommand, IHandler

TROPE_LINK = re.compile(r'{{(.*?)}}')
INVALID_TROPE_TITLE_CHARACTERS = re.compile(r'[^@A-Za-z0-9\-./]+')


def strip_redirect(s):
    return s.split('?from=', 1)[0]

def get_real_title_and_url(title, url):
    title = title.split(' - ', 1)[0]
    url = strip_redirect(url)
    
    # If no page title was returned (which does happen quite often), use
    # the last component of the URL instead.
    if not title:
        title = url.rsplit('/', 1)[-1]
    
    return (title, url)


class TVTropesSearch(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search for a TV Tropes article with a 
    title matching the given search string, or perform a full-text search if 
    no such article exists.
    """
    implements(IPlugin, ICommand, IHandler)
    name = 'tvtropes'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        d = threads.deferToThread(self.search, args[1])
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d
    
    def privmsg(self, bot, prefix, channel, message):
        tropes = TROPE_LINK.findall(message)
        
        for match in tropes:
            match = match.strip()
            if match:
                d = threads.deferToThread(self.search, match)
                d.addCallback(self.reply_without_target, bot,
                              prefix, channel, match)
                return d
    
    action = privmsg
    
    def search(self, title):
        # Start off by trying to find a trope with the exact title.
        
        # Transform the requested page title for {{}} search.  First,
        # remove any characters invalid in plain trope titles, in order
        # to increase the likelihood of an exact match.  Second, force
        # the first character to uppercase; otherwise, an all-lowercase
        # query will lead to the markup not being parsed as a link.
        plain_title = INVALID_TROPE_TITLE_CHARACTERS.sub('', title)
        plain_title = plain_title[0].upper() + plain_title[1:]
        
        # Work around a TV Tropes bug (2011-03-31) that returns "blue"
        # existing article links instead of "red" nonexistent article
        # links, by adding the known extant article "HomePage" to the
        # beginning of the query.  When removing this workaround, make
        # sure to update the link loop below as well!
        preview_query = ('HomePage [=~%s~=] {{%s}}' % (title, plain_title))
        params = {'source': preview_query}
        
        response = self.factory.get_http('http://tvtropes.org/pmwiki/preview.php',
                                         'POST', body=urllib.urlencode(params),
                                         headers={'Content-type':
                                                  'application/x-www-form-urlencoded'},
                                         defer=False)
        preview_soup = BeautifulSoup(response[1])
        
        # Discard the bogus HomePage link.
        preview_soup.find('a', 'twikilink').extract()
        
        while preview_soup.find('a', 'twikilink'):
            link = preview_soup.find('a', 'twikilink').extract()
            
            try:
                result = link.attrMap['href']
            except KeyError:
                continue
            
            # [=~ ~=] searches for non-existent ptitles return a broken
            # link pointing to "ptitle" in the appropriate namespace
            # instead of simply failing like they should, so we skip
            # them.
            if result.rsplit('/', 1)[-1] == 'ptitle':
                continue
            
            # We've found our match.
            response = self.factory.get_http(result, defer=False)
            article_soup = BeautifulSoup(response[1])
            return (html.textify_html(article_soup.find('title')),
                    response[0]['content-location'], '')

        # No results?  Try a full-text Google search.        
        params = urllib.urlencode({'q': ('site:tvtropes.org inurl:pmwiki.php '
                                         '-"click the edit button" %s,')
                                          % title,
                                   'v': '1.0'})
        
        response = self.factory.get_http('http://ajax.googleapis.com/ajax/'
                                         'services/search/web?' + params,
                                         defer=False)
        data = json.loads(response[1])
        
        if ('responseData' not in data or
            'results' not in data['responseData'] or
            not data['responseData']['results']):
            return None
        
        result = data['responseData']['results'][0]
        return (html.decode_html_entities(result['titleNoFormatting']),
                result['unescapedUrl'], ' (full-text)')
    
    def reply(self, trope, bot, prefix, reply_target, channel, args):
        if not trope:
            bot.reply(prefix, channel, 'TV Tropes: No results found for '
                                       '\x02%s\x02.' % args[1])
            return
        
        (title, url, info_text) = trope
        (title, url) = get_real_title_and_url(title, url)
        
        bot.reply(reply_target, channel, (u'TV Tropes%s: \x02%s\x02: %s'
                                            % (info_text, title, url)) \
                                          .encode(self.factory.encoding))
    
    def reply_without_target(self, trope, bot, prefix, channel, match):
        if not trope:
            bot.msg(channel, '\x0314TV Tropes: No results found for '
                             '\x02%s\x02.' % match)
            return
        
        (title, url, info_text) = trope
        (title, url) = get_real_title_and_url(title, url)
        
        bot.msg(channel, (u'\x0314TV Tropes%s: \x02%s\x02: %s'
                            % (info_text, title, url)) \
                          .encode(self.factory.encoding))


class RandomTrope(TVTropesSearch):
    """
    \x02%s\x02 - Get a random TV Tropes article.
    """
    name = 'tvtropes_random'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        d = threads.deferToThread(self.random)
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d
    
    def random(self):
        response = self.factory.get_http('http://tvtropes.org/pmwiki/randomitem.php',
                                         defer=False)
        soup = BeautifulSoup(response[1])
        return (html.textify_html(soup.find('title')),
                response[0]['content-location'], ' (random)')


tvtropes = TVTropesSearch()
tvtropes_random = RandomTrope()
