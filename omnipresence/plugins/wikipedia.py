import json
import re
import urllib

from BeautifulSoup import BeautifulSoup
from twisted.internet import defer
from twisted.plugin import IPlugin
from twisted.python import log
from zope.interface import implements

from omnipresence import web
from omnipresence.iomnipresence import ICommand, IHandler


DEFAULT_LANGUAGE = 'en'
WIKIPEDIA_API_URL = 'https://%s.wikipedia.org/w/api.php?%s'
WIKIPEDIA_INLINE_LINK = re.compile(r'\[\[(.*?)\]\]')

languages = None


class WikipediaAPIError(Exception):
    pass


@defer.inlineCallbacks
def call_wikipedia_api(language, params):
    params['format'] = 'json'
    request_url = WIKIPEDIA_API_URL % (language, urllib.urlencode(params))
    headers, content = yield web.request('GET', request_url)
    data = json.loads(content)
    if 'error' in data:
        raise WikipediaAPIError('Wikipedia API encountered an error: '
                                '\x02%s\x02.' % (data['error']['info']))
    defer.returnValue(data)

@defer.inlineCallbacks
def load_languages():
    global languages
    if languages is not None:
        return
    languages = set()
    data = yield call_wikipedia_api(DEFAULT_LANGUAGE, {'action': 'sitematrix'})
    for x in data['sitematrix'].itervalues():
        if isinstance(x, dict):
            languages.add(x['code'])


class WikipediaPlugin(object):
    implements(IPlugin, ICommand)

    def registered(self):
        load_languages()

    def reply(self, pageinfo, bot, prefix, reply_target, channel, args):
        if not pageinfo:
            bot.reply(prefix, channel, ('Wikipedia: No results found for '
                                        '\x02%s\x02.' % args[1]))
            return
        url, summary, info_text = pageinfo

        if summary:
            # Reduce the summary down to the first paragraph.
            soup = BeautifulSoup(summary).findAll('p', '', recursive=False)
            for p in soup:
                ptext = web.textify_html(p)
                if ptext:
                    summary = u' \u2014 ' + ptext
                    break
        if not summary:
            summary = u''
        
        bot.reply(reply_target, channel,
                  u'Wikipedia{0}: {1}{2}'.format(info_text, url, summary))


class ArticleSearch(WikipediaPlugin):
    """
    \x02%s\x02 [\x1Flanguage_code\x1F\x02:\x02]\x1Fsearch_string\x1F -
    Search for a Wikipedia article with a title matching the given
    search string, or perform a full-text search if no such article
    exists.  If a \x1Flanguage_code\x1F is specified, the search is
    performed on the Wikipedia of that language.
    """
    implements(IHandler)  # in addition to IPlugin and ICommand
    name = 'wikipedia'

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return

        # Strip off valid language codes.
        language = DEFAULT_LANGUAGE
        title = args[1]
        while ':' in title:
            new_language, new_title = title.split(':', 1)
            if new_language in languages:
                language, title = new_language, new_title
            else:
                break

        title = title.strip()
        if not title:
            bot.reply(reply_target, channel,
                      'Wikipedia: https://%s.wikipedia.org/' % language)
            return

        d = self.search(language, title)
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d

    def privmsg(self, bot, prefix, channel, message):
        dl = []
        for match in WIKIPEDIA_INLINE_LINK.finditer(message):
            # Split on | in order to allow [[article|text]] links.
            title = match.group(1).split('|')[0].strip()
            if title:
                log.msg('Saw Wikipedia link [[%s]] from %s in %s.'
                        % (title, prefix, channel))
                dl.append(defer.maybeDeferred(self.execute, bot, prefix, None,
                                              channel, '% ' + title))
        if dl:
            return defer.DeferredList(dl)

    action = privmsg

    @defer.inlineCallbacks
    def search(self, language, title):
        exact = yield call_wikipedia_api(
                  language, { 'action': 'query',
                              'titles': title,
                              'redirects': 1,
                              'iwurl': 1,
                              'prop': 'info|extracts',
                              'inprop': 'url',
                              'exchars': 256 })

        if 'interwiki' in exact['query']:
            # This is a valid non-Wikipedia interwiki article.
            # Strip off the interwiki prefix from the title.
            url = exact['query']['interwiki'][0]['url']
            defer.returnValue((url, None, u' (interwiki)'))

        if 'pages' in exact['query']:
            for pageid, pageinfo in exact['query']['pages'].iteritems():
                # If there's no page with the given title, or if the
                # title is invalid, the API will still return an entry
                # with a pageid of -1.
                if pageid != '-1':
                    defer.returnValue((pageinfo['fullurl'],
                                       pageinfo['extract'], u''))

        # No results from the exact search; try full-text.
        ftext = yield call_wikipedia_api(
                  language, { 'action': 'query',
                              'generator': 'search',
                              'gsrsearch': title,
                              'gsrlimit': 1,
                              'prop': 'info|extracts',
                              'inprop': 'url',
                              'exchars': 256 })

        if 'pages' in ftext['query']:
            for pageinfo in ftext['query']['pages'].itervalues():
                defer.returnValue((pageinfo['fullurl'],
                                   pageinfo['extract'], u' (full-text)'))
        
        # Nothing doing.
        defer.returnValue(None)


class RandomArticle(WikipediaPlugin):
    """
    \x02%s\x02 [\x1Flanguage_code\x1F[\x02:\x02]] - Get a random main
    namespace Wikipedia article, in the Wikipedia corresponding to
    \x1Flanguage_code\x1F if one is specified.
    """
    name = 'wikipedia_random'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1) 
        language = DEFAULT_LANGUAGE
        if len(args) > 1:
            language = args[1].rstrip(':')
            if language not in languages:
                bot.reply(prefix, channel,
                          'The language code \x02%s\x02 is invalid.'
                           % language)
                return
        
        d = self.random(language)
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d
    
    @defer.inlineCallbacks
    def random(self, language):
        random = yield call_wikipedia_api(language, {'action': 'query',
                                                     'generator': 'random',
                                                     'grnnamespace': 0,
                                                     'prop': 'info|extracts',
                                                     'inprop': 'url',
                                                     'exchars': 256 })

        if 'pages' in random['query']:
            for pageinfo in random['query']['pages'].itervalues():
                defer.returnValue((pageinfo['fullurl'],
                                   pageinfo['extract'], u' (random)'))

        defer.returnValue(None)

    def reply(self, pageinfo, *args):
        if not pageinfo:
            bot.reply(prefix, channel,
                      'Wikipedia (random): No articles found.')
            return
    
        super(RandomArticle, self).reply(pageinfo, *args)


default = ArticleSearch()
random = RandomArticle()
