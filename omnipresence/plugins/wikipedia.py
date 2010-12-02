import json
import urllib

from BeautifulSoup import BeautifulSoup
from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.python import log
from omnipresence.iomnipresence import ICommand

from omnipresence import util


def wikipedia_url(language, title):
    title = urllib.quote(title.encode('utf-8').replace(' ', '_'))
    return 'http://%s.wikipedia.org/wiki/%s' % (language, title)


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

    def load_languages(self, response):
        data = json.loads(response[1])
        for x in data['sitematrix'].itervalues():
            if isinstance(x, dict):
                self.languages.add(x['code'])

    def load_interwiki(self, response):
        data = json.loads(response[1])
        for x in data['query']['interwikimap']:
            self.interwiki[x['prefix']] = x['url']

    def registered(self):
        d = self.factory.get_http('http://en.wikipedia.org/w/api.php?action=sitematrix&format=json')
        d.addCallback(self.load_languages)

        d = self.factory.get_http('http://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&siprop=interwikimap&format=json')
        d.addCallback(self.load_interwiki)
    
    def reply_with_summary(self, response, bot, prefix, channel,
                           args, language, title, info_text=''):
        data = json.loads(response[1])

        summary = ''
        soup = BeautifulSoup(data['parse']['text']['*']).findAll('p',
                                                                 recursive=False)
        for p in soup:
            summary = util.textify_html(p)

            if len(summary) > 128:
                summary = summary[:128] + '...'

            if summary:
                break
        else:
            self.reply_without_summary(None, bot, prefix, channel, args,
                                       language, title, info_text)
            return

        bot.reply(prefix, channel, (u'Wikipedia%s: \x02%s\x02: %s \u2014 %s'
                                      % (info_text, title, summary,
                                         wikipedia_url(language, title))) \
                                    .encode(self.factory.encoding))

    def reply_without_summary(self, failure, bot, prefix, channel,
                              args, language, title, info_text=''):
        if failure is not None:
            log.err(failure, 'Wikipedia summary fetching failed.')

        bot.reply(prefix, channel, (u'Wikipedia%s: \x02%s\x02: %s'
                                      % (info_text, title,
                                         wikipedia_url(language, title))) \
                                    .encode(self.factory.encoding))

    def get_summary(self, bot, prefix, channel,
                    args, language, title, info_text=''):
        params = urllib.urlencode({'action': 'parse',
                                   'prop': 'text',
                                   'page': title.encode('utf-8'),
                                   'format': 'json'})
        d = self.factory.get_http('http://%s.wikipedia.org/w/api.php?%s'
                                   % (language, params))
        d.addCallback(self.reply_with_summary, bot, prefix, channel, args,
                      language, title, info_text)
        d.addErrback(self.reply_without_summary, bot, prefix, channel, args,
                     language, title, info_text)

    def _fulltext_search(self, response, bot, prefix,
                         channel, args, language, title):
        data = json.loads(response[1])

        if 'error' in data:
            bot.reply(prefix, channel, 'Wikipedia: API encountered an error: '
                                       '%s.' % (data['error']['info']))
            return

        results = data['query']['search']

        if len(results) < 1:
            bot.reply(prefix, channel, ('Wikipedia (full-text): No results '
                                        'found for \x02%s\x02.' % args[1]))
            return

        self.get_summary(bot, prefix, channel, args, language,
                         results[0]['title'], info_text=' (full-text)')

    def fulltext_search(self, bot, prefix, channel, args, language, title):
        params = urllib.urlencode({'action': 'query',
                                   'list': 'search',
                                   'srsearch': title,
                                   'srlimit': 1,
                                   'format': 'json'})
        d = self.factory.get_http('http://%s.wikipedia.org/w/api.php?%s'
                                   % (language, params))
        d.addCallback(self._fulltext_search, bot, prefix, channel, args,
                      language, title)

    def exact_search(self, response, bot, prefix,
                     channel, args, language, title):
        if response is not None:
            data = json.loads(response[1])

            if not data:
                # Blank query following a language code, which yielded 
                # an empty list.  Return the URL of the main page.
                bot.reply(prefix, channel, 'Wikipedia: http://%s.wikipedia.org/'
                                            % language)
                return

            if 'error' in data:
                bot.reply(prefix, channel, 'Wikipedia: API encountered an '
                                           'error: %s.'
                                            % (data['error']['info']))
                return

            if 'interwiki' in data['query']:
                language = data['query']['interwiki'][0]['iw']
                title = title[len(language) + 1:]

                # If this is a Wikipedia language edition, we want to 
                # continue performing lookups.
                if language not in self.languages:
                    if language not in self.interwiki:
                        # Something changed on us.  Bail to full-text.
                        self.fulltext_search(bot, prefix, channel, args,
                                             language, args[1])
                        return

                    # This is a valid non-Wikipedia interwiki article.
                    url = self.interwiki[language].replace('$1',
                                                           urllib.quote(title))
                    bot.reply(prefix, channel,
                              (u'Wikipedia (interwiki): %s' % url) \
                               .encode(self.factory.encoding))
            elif 'pages' in data['query']:
                if data['query']['pages'].keys()[0] == '-1':
                    # Try a full-text search instead.
                    self.fulltext_search(bot, prefix, channel, args, language,
                                         args[1])
                    return

                self.get_summary(bot, prefix, channel, args, language,
                                 data['query']['pages'].values()[0]['title'])
                return
            else:
                # Nothing works?  Do a full-text search.
                self.fulltext_search(bot, prefix, channel, args, language,
                                     args[1])
                return

        params = urllib.urlencode({'action': 'query',
                                   'titles': title,
                                   'redirects': 1,
                                   'format': 'json'})
        d = self.factory.get_http('http://%s.wikipedia.org/w/api.php?%s'
                                   % (language, params))
        d.addCallback(self.exact_search, bot, prefix, channel, args, language,
                      title)

    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        language = 'en'
        title = args[1]

        if ':' in title:
            (new_language, new_title) = title.split(':', 1)

            if new_language in self.languages:
                language = new_language
                title = new_title

        title = title.strip()

        if len(title) < 1:
            bot.reply(prefix, channel, 'Wikipedia: http://%s.wikipedia.org/'
                                        % language)
            return

        self.exact_search(None, bot, prefix, channel, args, language, title)


class RandomWikipediaArticle(WikipediaSearch):
    """
    \x02%s\x02 [\x1Flanguage_code\x1F[\x02:]] - Get a random main 
    namespace Wikipedia article, in the Wikipedia corresponding to 
    \x1Flanguage_code\x1F if one is specified.
    """
    name = 'wikipedia_random'
    
    def get_random(self, response, bot, prefix, channel, args, language):
        data = json.loads(response[1])
        
        if 'error' in data:
            bot.reply(prefix, channel, 'Wikipedia (random): API encountered '
                                       'an error: %s.'
                                        % (data['error']['info']))
            return
        
        results = data['query']['random']
        
        if len(results) < 1:
            bot.reply(prefix, channel,
                      'Wikipedia (random): No articles found.')
            return
        
        self.get_summary(bot, prefix, channel, args, language,
                         results[0]['title'], info_text=' (random)')
    
    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        language = 'en'
        
        if len(args) > 1:
            language = args[1].rstrip(':')
            if language not in self.languages:
                bot.reply(prefix, channel,
                          'The language code \x02%s\x02 is invalid.'
                           % language)
                return
        
        params = urllib.urlencode({'action': 'query',
                                   'list': 'random',
                                   'rnnamespace': 0,
                                   'format': 'json'})
        d = self.factory.get_http('http://%s.wikipedia.org/w/api.php?%s'
                                   % (language, params))
        d.addCallback(self.get_random, bot, prefix, channel, args, language)
        return d


wikipedia = WikipediaSearch()
wikipedia_random = RandomWikipediaArticle()
