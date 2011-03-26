import json
import sys
import urllib

from BeautifulSoup import BeautifulSoup
from twisted.internet import defer, threads
from twisted.plugin import IPlugin
from twisted.python import log
from zope.interface import implements

from omnipresence import html, util
from omnipresence.iomnipresence import ICommand


DEFAULT_LANGUAGE = 'en'
WIKIPEDIA_API_URL = 'http://%s.wikipedia.org/w/api.php?%s'

def wikipedia_url(language, title):
    title = urllib.quote(title.encode('utf-8').replace(' ', '_'))
    return 'http://%s.wikipedia.org/wiki/%s' % (language, title)


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
    interwiki = {}
    
    def call_wikipedia_api(self, language, params, defer=True):
        params['format'] = 'json'
        return self.factory.get_http(WIKIPEDIA_API_URL
                                      % (language, urllib.urlencode(params)),
                                     defer=defer)

    def registered(self):
        d = self.call_wikipedia_api(DEFAULT_LANGUAGE, {'action': 'sitematrix'})
        d.addCallback(self.load_languages)

        d = self.call_wikipedia_api(DEFAULT_LANGUAGE,
                                    {'action': 'query', 'meta': 'siteinfo',
                                     'siprop': 'interwikimap'})
        d.addCallback(self.load_interwiki)
    
    def load_languages(self, response):
        data = json.loads(response[1])
        for x in data['sitematrix'].itervalues():
            if isinstance(x, dict):
                self.languages.add(x['code'])

    def load_interwiki(self, response):
        data = json.loads(response[1])
        for x in data['query']['interwikimap']:
            self.interwiki[x['prefix']] = x['url']

    def execute(self, bot, prefix, channel, args):
        (args, reply_target) = util.redirect_command(args, prefix, channel)
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
        # Try an exact search first.
        response = self.call_wikipedia_api(language, {'action': 'query',
                                                      'titles': title,
                                                      'redirects': 1,
                                                      'format': 'json'},
                                           defer=False)
        data = json.loads(response[1])

        if 'error' in data:
            raise WikipediaAPIError('Wikipedia API encountered an error: '
                                    '\x02%s\x02.' % (data['error']['info']))

        if 'interwiki' in data['query']:
            language = data['query']['interwiki'][0]['iw']
            title = title[len(language) + 1:]

            # This is a valid non-Wikipedia interwiki article.
            return (language, title, None, '')
        
        if 'pages' in data['query']:
            if data['query']['pages'].keys()[0] != '-1':
                title = data['query']['pages'].values()[0]['title']
                return self.get_summary(language, title)

        # Nothing works?  Do a full-text search.
        response = self.call_wikipedia_api(language, {'action': 'query',
                                                      'list': 'search',
                                                      'srsearch': title,
                                                      'srlimit': 1,
                                                      'format': 'json'},
                                           defer=False)
        data = json.loads(response[1])

        if 'error' in data:
            raise WikipediaAPIError('Wikipedia API encountered an error: '
                                    '\x02%s\x02.' % (data['error']['info']))

        results = data['query']['search']

        if not results:
            return None

        return self.get_summary(language, results[0]['title'],
                                info_text=' (full-text)')

    def get_summary(self, language, title, info_text=''):
        try:
            response = self.call_wikipedia_api(language, {'action': 'parse',
                                                          'prop': 'text',
                                                          'page': title.encode('utf-8'),
                                                          'format': 'json'},
                                               defer=False)
        except:
            log.err(None, 'Wikipedia summary fetching failed.')
            return (language, title, None, info_text)
        
        data = json.loads(response[1])
        soup = BeautifulSoup(data['parse']['text']['*']).findAll('p', '',
                                                                 recursive=False)
        for p in soup:
            summary = html.textify_html(p)

            if len(summary) > 128:
                summary = summary[:128] + u'...'

            if summary:
                return (language, title, summary, info_text)
        else:
            return (language, title, None, info_text)
    
    def reply_with_article(self, response, bot, prefix,
                           reply_target, channel, args):
        if not response:
            bot.reply(prefix, channel, ('Wikipedia: No results found for '
                                        '\x02%s\x02.' % args[1]))
            return
        
        (language, title, summary, info_text) = response
        
        if language not in self.languages:
            if language in self.interwiki:
                url = self.interwiki[language].replace('$1',
                                                       urllib.quote(title))
            else:
                # This generally shouldn't happen unless the interwiki
                # map was touched since registered() was fired.  Make up
                # a realistic URL.
                url = wikipedia_url(DEFAULT_LANGUAGE, language + ':' + title)
            
            bot.reply(reply_target, channel,
                      (u'Wikipedia (interwiki): %s' % url) \
                       .encode(self.factory.encoding))
            return
        
        summary = summary + u' \u2014 ' if summary else ''
        
        bot.reply(reply_target, channel, (u'Wikipedia%s: \x02%s\x02: %s%s'
                                            % (info_text, title, summary,
                                               wikipedia_url(language, title))) \
                                          .encode(self.factory.encoding))


class RandomWikipediaArticle(WikipediaSearch):
    """
    \x02%s\x02 [\x1Flanguage_code\x1F[\x02:]] - Get a random main 
    namespace Wikipedia article, in the Wikipedia corresponding to 
    \x1Flanguage_code\x1F if one is specified.
    """
    name = 'wikipedia_random'
    
    def execute(self, bot, prefix, channel, args):
        (args, reply_target) = util.redirect_command(args, prefix, channel)
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
        response = self.call_wikipedia_api(language, {'action': 'query',
                                                      'list': 'random',
                                                      'rnnamespace': 0,
                                                      'format': 'json'},
                                           defer=False)
        data = json.loads(response[1])
        
        if 'error' in data:
            raise WikipediaAPIError('Wikipedia API encountered an error: '
                                    '\x02%s\x02.' % (data['error']['info']))
        
        results = data['query']['random']
        
        if not results:
            return None
        
        return self.get_summary(language, results[0]['title'],
                                info_text=' (random)')
    
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
