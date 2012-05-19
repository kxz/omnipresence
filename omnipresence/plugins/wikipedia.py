import json
import sys
import urllib

from BeautifulSoup import BeautifulSoup
from twisted.internet import threads
from twisted.plugin import IPlugin
from twisted.python import log
from zope.interface import implements

from omnipresence import html, util
from omnipresence.iomnipresence import ICommand


DEFAULT_LANGUAGE = 'en'
WIKIPEDIA_API_URL = 'http://%s.wikipedia.org/w/api.php?%s'


class WikipediaAPIError(Exception):
    pass


class WikipediaSearch(object):
    """
    \x02%s\x02 [\x1Flanguage_code\x1F\x02:\x02]\x1Fsearch_string\x1F - 
    Search for a Wikipedia article with a title matching the given 
    search string, or perform a full-text search if no such article 
    exists.  If a \x1Flanguage_code\x1F is specified, the search is 
    performed on the Wikipedia of that language.
    """
    implements(IPlugin, ICommand)
    name = 'wikipedia'

    languages = set()
    
    def call_wikipedia_api(self, language, params):
        params['format'] = 'json'
        response = self.factory.get_http(WIKIPEDIA_API_URL
                                          % (language, urllib.urlencode(params)),
                                         defer=False)
        data = json.loads(response[1])
        if 'error' in data:
            raise WikipediaAPIError('Wikipedia API encountered an error: '
                                    '\x02%s\x02.' % (data['error']['info']))
        return data

    def registered(self):
        d = threads.deferToThread(self.call_wikipedia_api,
                                  DEFAULT_LANGUAGE, {'action': 'sitematrix'})
        d.addCallback(self.load_languages)
    
    def load_languages(self, data):
        for x in data['sitematrix'].itervalues():
            if isinstance(x, dict):
                self.languages.add(x['code'])

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        language = DEFAULT_LANGUAGE
        title = args[1]

        # Strip off valid language codes.
        while ':' in title:
            (new_language, new_title) = title.split(':', 1)

            if new_language in self.languages:
                language = new_language
                title = new_title
            else:
                break

        title = title.strip()

        if not title:
            bot.reply(reply_target, channel, 'Wikipedia: '
                                             'http://%s.wikipedia.org/'
                                              % language)
            return

        d = threads.deferToThread(self.search, language, title)
        d.addCallback(self.reply_with_article, bot, prefix, reply_target,
                      channel, args)
        return d

    def search(self, language, title):
        # Perform a full-text search first, then query for the title
        # returned by the full-text search as well as the exact one.
        # Return information for the latter if the page exists, the
        # former otherwise.  Doing this saves us some extraneous API
        # requests and repeated code.
        
        query_titles = title
        title = title.decode('utf-8')
        
        # Full-text search first.
        data = self.call_wikipedia_api(language, {'action': 'query',
                                                  'list': 'search',
                                                  'srsearch': query_titles,
                                                  'srlimit': 1})

        if data['query']['search']:
            query_titles += '|' + data['query']['search'][0]['title'].encode('utf-8')
        
        # Now do the exact search.
        data = self.call_wikipedia_api(language, {'action': 'query',
                                                  'titles': query_titles,
                                                  'redirects': 1,
                                                  'iwurl': 1,
                                                  'prop': 'info',
                                                  'inprop': 'url'})

        if 'interwiki' in data['query']:
            # This is a valid non-Wikipedia interwiki article.
            
            # Strip off the interwiki prefix from the title.
            title = title[len(data['query']['interwiki'][0]['iw']) + 1:]
            url = data['query']['interwiki'][0]['url']
            return (title, url, None, ' (interwiki)')
        
        info_text = ''
        if 'pages' in data['query']:
            if '-1' in data['query']['pages']:
                # We can reasonably assume that the only title in our
                # query that'll return a "missing article" result will
                # be the exact title provided in `title`; full-text
                # search shouldn't return nonexistent articles.  Thus,
                # one "missing" result is enough to determine that we
                # are falling back on full-text results.
                info_text = ' (full-text)'
            
            for (pageid, pageinfo) in data['query']['pages'].iteritems():
                if pageid != '-1':
                    title = pageinfo['title']
                    url = pageinfo['fullurl']
                    return self.get_summary(language, title, url, info_text)

        return None

    def get_summary(self, language, title, url, info_text=''):
        try:
            data = self.call_wikipedia_api(language, {'action': 'parse',
                                                      'prop': 'text',
                                                      'page': title.encode('utf-8')})
        except:
            log.err(None, 'Wikipedia summary fetching failed.')
            return (title, url, None, info_text)
        
        soup = BeautifulSoup(data['parse']['text']['*']).findAll('p', '',
                                                                 recursive=False)
        for p in soup:
            summary = html.textify_html(p)

            if summary:
                return (title, url, summary, info_text)
        else:
            return (title, url, None, info_text)
    
    def reply_with_article(self, response, bot, prefix,
                           reply_target, channel, args):
        if not response:
            bot.reply(prefix, channel, ('Wikipedia: No results found for '
                                        '\x02%s\x02.' % args[1]))
            return
        
        (title, url, summary, info_text) = response
        
        summary = u': ' + summary if summary else ''
        
        bot.reply(reply_target, channel, (u'Wikipedia%s: %s \u2014 \x02%s\x02%s'
                                            % (info_text, url, title, summary)))


class RandomWikipediaArticle(WikipediaSearch):
    """
    \x02%s\x02 [\x1Flanguage_code\x1F[\x02:]] - Get a random main 
    namespace Wikipedia article, in the Wikipedia corresponding to 
    \x1Flanguage_code\x1F if one is specified.
    """
    name = 'wikipedia_random'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        language = DEFAULT_LANGUAGE
        
        if len(args) > 1:
            language = args[1].rstrip(':')
            if language not in self.languages:
                bot.reply(prefix, channel,
                          'The language code \x02%s\x02 is invalid.'
                           % language)
                return
        
        d = threads.deferToThread(self.random, language)
        d.addCallback(self.reply_with_article, bot, prefix, reply_target,
                      channel, args)
        return d
    
    def random(self, language):
        data = self.call_wikipedia_api(language, {'action': 'query',
                                                  'generator': 'random',
                                                  'grnnamespace': 0,
                                                  'prop': 'info',
                                                  'inprop': 'url'})
        
        if 'pages' in data['query']:
            for (pageid, pageinfo) in data['query']['pages'].iteritems():
                if pageid != '-1':
                    title = pageinfo['title']
                    url = pageinfo['fullurl']
                    return self.get_summary(language, title, url,
                                            info_text=' (random)')

        return None
    
    def reply_with_article(self, response, bot, prefix,
                           reply_target, channel, args):
        if not response:
            bot.reply(prefix, channel,
                      'Wikipedia (random): No articles found.')
            return
        
        super(RandomWikipediaArticle, self).reply_with_article(response,
                                                               bot, prefix,
                                                               reply_target,
                                                               channel, args)


wikipedia = WikipediaSearch()
wikipedia_random = RandomWikipediaArticle()
