import json
import re
import urllib

from BeautifulSoup import BeautifulSoup
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
    def reply_with_trope(self, response, bot, prefix, reply_target, channel,
                         args, info_text=''):
        soup = BeautifulSoup(response[1])
        (title, url) = get_real_title_and_url(html.textify_html(soup.find('title')),
                                              response[0]['content-location'])
        bot.reply(reply_target, channel, (u'TV Tropes%s: \x02%s\x02: %s'
                                            % (info_text, title, url)) \
                                          .encode(self.factory.encoding))
    
    def reply_with_google(self, response, bot, prefix, reply_target, channel,
                          args):
        data = json.loads(response[1])
        
        if ('responseData' not in data or
            'results' not in data['responseData'] or
            len(data['responseData']['results']) < 1):
            bot.reply(prefix, channel, 'TV Tropes: No results found for '
                                       '\x02%s\x02.' % args[1])
            return
        
        result = data['responseData']['results'][0]
        (title, url) = get_real_title_and_url(html.decode_html_entities(result['titleNoFormatting']),
                                              result['unescapedUrl'])
        bot.reply(reply_target, channel, (u'TV Tropes (full-text): '
                                          u'\x02%s\x02: %s' % (title, url)) \
                                          .encode(self.factory.encoding))
    
    def find_trope(self, response, bot, prefix, reply_target, channel, args):
        soup = BeautifulSoup(response[1])
        
        while soup.find('a', 'twikilink'):
            link = soup.find('a', 'twikilink').extract()
            
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
            
            d = self.factory.get_http(result)
            d.addCallback(self.reply_with_trope, bot, prefix, reply_target, channel, args)
            d.addErrback(bot.reply_with_error, prefix, channel, args[0])
            return            
        
        params = urllib.urlencode({'q': ('site:tvtropes.org inurl:pmwiki.php '
                                         '-"click the edit button" %s,')
                                          % args[1],
                                   'v': '1.0'})
        
        d = self.factory.get_http('http://ajax.googleapis.com/ajax/services/search/web?' + params)
        d.addCallback(self.reply_with_google, bot, prefix, reply_target, channel, args)
        d.addErrback(bot.reply_with_error, prefix, channel, args[0])
    
    def check_trope(self, bot, prefix, reply_target, channel, args):
        # Transform the requested page title for {{}} search.  First,
        # remove any characters invalid in plain trope titles, in order
        # to increase the likelihood of an exact match.  Second, force
        # the first character to uppercase; otherwise, an all-lowercase
        # query will lead to the markup not being parsed as a link.
        plain_title = INVALID_TROPE_TITLE_CHARACTERS.sub('', args[1])
        preview_query = ('[=~%s~=] {{%s%s}}'
                          % (args[1], plain_title[0].upper(), plain_title[1:]))
        params = {'source': preview_query}
        
        d = self.factory.get_http('http://tvtropes.org/pmwiki/preview.php',
                                  'POST', body=urllib.urlencode(params),
                                  headers={'Content-type':
                                           'application/x-www-form-urlencoded'})
        d.addCallback(self.find_trope, bot, prefix, reply_target, channel, args)
        return d


class TVTropesSearchCommand(TVTropesSearch):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search for a TV Tropes article with a 
    title matching the given search string, or perform a full-text search if 
    no such article exists.
    """
    implements(IPlugin, ICommand)
    name = 'trope'
    
    def execute(self, bot, prefix, channel, args):
        (args, reply_target) = util.redirect_command(args, prefix, channel)
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        return self.check_trope(bot, prefix, reply_target, channel, args)


class RandomTropeCommand(TVTropesSearch):
    """
    \x02%s\x02 - Get a random TV Tropes article.
    """
    implements(IPlugin, ICommand)
    name = 'trope_random'
    
    def execute(self, bot, prefix, channel, args):
        (args, reply_target) = util.redirect_command(args, prefix, channel)
        d = self.factory.get_http('http://tvtropes.org/pmwiki/randomitem.php')
        d.addCallback(self.reply_with_trope, bot, prefix, reply_target,
                      channel, args, ' (random)')
        return d


class TVTropesLinkHandler(TVTropesSearch):
    """
    Reply to messages containing {{trope links}} with the trope URL.
    """
    implements(IPlugin, IHandler)
    name = 'tvtropes'
    
    def privmsg(self, bot, prefix, channel, message):
        tropes = TROPE_LINK.findall(message)
        
        for match in tropes:
            if match.strip():
                return self.check_trope(bot, prefix, channel, ['trope', match])
    
    action = privmsg


trope = TVTropesSearchCommand()
trope_random = RandomTropeCommand()
trope_handler = TVTropesLinkHandler()