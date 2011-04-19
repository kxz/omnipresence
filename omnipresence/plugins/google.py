import json
import urllib
import urlparse

from BeautifulSoup import BeautifulSoup
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import html, util
from omnipresence.iomnipresence import ICommand


# TODO: Make this configurable and update GoogleTranslateCommand's
# docstring on the fly.
DEFAULT_TARGET_LANGUAGE = 'en'


class GoogleCommand(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Google search on the given 
    search string.
    """
    implements(IPlugin, ICommand)
    name = 'google'
    
    # The maximum number of results to return at any one time.  Google's 
    # absolute maximum for API requests is 4.
    max_results = 3
    
    def reply_with_results(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        
        if ('responseData' not in data or
            'results' not in data['responseData'] or
            len(data['responseData']['results']) < 1):
            bot.reply(prefix, channel,
                      'Google: No results found for \x02%s\x02.' % args[1])
            return
        
        results = data['responseData']['results'][:self.max_results]
        
        if len(results) == 1:
            result = results[0]
            
            content = html.textify_html(BeautifulSoup(result['content']))
            if len(content) > 128:
                content = content[:128] + '...'
            
            messages = [(u'\x02%s\x02: %s \u2014 %s'
                           % (html.decode_html_entities(result['titleNoFormatting']),
                              content, result['unescapedUrl']))]
        else:
            messages = [(u'(%d) \x02%s\x02: %s'
                           % (i + 1,
                              html.decode_html_entities(result['titleNoFormatting']),
                              result['unescapedUrl']))
                        for i, result in enumerate(results)]
        
        bot.reply(reply_target, channel,
                  ((u'Google: ' + u' \u2014 '.join(messages)) \
                   .encode(self.factory.encoding)))
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        d = self.factory.get_http('http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s' % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, prefix, reply_target, channel, args)
        return d


class ImFeelingLuckyCommand(GoogleCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Google search on the given 
    search string, and return only the first result.
    """
    name = 'lucky'
    max_results = 1


class GoogleCalculatorCommand(object):
    """
    \x02%s\x02 \x1Fexpression\x1F - Ask Google to compute a mathematical 
    expression, and return the result.
    """
    implements(IPlugin, ICommand)
    name = 'gcalc'
    
    def reply_with_results(self, response, bot, prefix, reply_target, channel, args):
        soup = BeautifulSoup(response[1])
        
        try:
            result = html.textify_html(soup.find('', 'r').b)
        except AttributeError:
            result = u'No result was returned!'
        
        bot.reply(reply_target, channel, ((u'Google calc: %s' % result) \
                                          .encode(self.factory.encoding)))
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify an expression.')
            return
        
        d = self.factory.get_http('http://www.google.com/search?q=%s' % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, prefix, reply_target, channel, args)
        return d


class GoogleDefinitionCommand(object):
    """
    \x02%s\x02 \x1Fterm\x1F - Fetch the first set of definitions for the given 
    term from Google.
    """
    implements(IPlugin, ICommand)
    name = 'define'
    
    def reply_with_results(self, response, bot, prefix, reply_target, channel, args):
        # Using SoupStrainer to parse only <li> tags yields a nested tree of 
        # <li> tags for some reason, so we just use "findAll" instead.
        soup = BeautifulSoup(response[1])
        lis = soup.findAll('li')
        
        results = []
        result_url = ''
        
        for li in lis:
            results.append(html.decode_html_entities(li.next).strip())
            
            # The last <li> in the first set of definitions has the associated 
            # source linked after a <br>.
            if li.find('br'):
                result_url = urlparse.urlparse(li.find('a')['href']).query
                
                # urlparse.parse_qs() does not like Unicode strings very 
                # much, so we perform an encode/decode here.
                result_url = result_url.encode('utf-8')
                result_url = urlparse.parse_qs(result_url)['q'][0]
                result_url = result_url.decode('utf-8')
                break
        
        if len(results) < 1:
            bot.reply(prefix, channel, 'Google dict: No results found for '
                                       '\x02%s\x02.' % args[1])
            return
        
        result = ' / '.join(results)
        if len(result) > 255:
            result = result[:255] + '...'
        
        bot.reply(reply_target, channel, (u'Google dict: %s \u2014 %s'
                                            % (result, result_url)) \
                                          .encode(self.factory.encoding))
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a term to look up.')
            return
        
        d = self.factory.get_http('http://www.google.com/search?q=define:%s'
                                   % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, prefix, reply_target, channel, args)
        return d


class GoogleTranslateCommand(object):
    """
    \x02%s\x02 [\x1Fsource_language\x1F\x02:\x02]\x1Fsource_text\x1F
    [\x1Ftarget_language\x1F\x02:\x02] - Translate text using Google
    Translate. If no source language is specified, the API will attempt
    to automatically detect one. The destination language, if not
    specified, defaults to \x02en\x02.
    """
    implements(IPlugin, ICommand)
    name = 'translate'
    
    languages = {}
    
    def registered(self):
        self.apikey = self.factory.config.get('google', 'apikey')
        
        params = {'key': self.apikey, 'target': DEFAULT_TARGET_LANGUAGE}
        d = self.factory.get_http('https://www.googleapis.com/language/translate/v2/languages?%s' % urllib.urlencode(params))
        d.addCallback(self.load_languages)
        
    def load_languages(self, response):
        data = json.loads(response[1])
        for i in data['data']['languages']:
            self.languages[i['language']] = i['name']
    
    def reply(self, response, bot, prefix, reply_target, channel,
              params, args):
        data = json.loads(response[1])
        
        if 'error' in data:
            bot.reply(prefix, channel,
                      (('Google Translate: API returned error code \x02%d\x02: '
                       '\x02%s\x02.' % (data['error']['code'],
                                        data['error']['message'])) \
                       .encode(self.factory.encoding)))
            return
        
        translation = data['data']['translations'][0]
        translated_text = html.textify_html(BeautifulSoup(translation['translatedText']))
        
        if 'source' in params:
            source_name = self.languages[params['source']] 
        else:
            source_name = '%s (auto-detected)' % self.languages[translation['detectedSourceLanguage']]
        
        target_name = self.languages[params['target']]
        
        bot.reply(reply_target, channel,
                  ((u'Google translation from %s to %s: %s'
                      % (source_name, target_name, translated_text)) \
                   .encode(self.factory.encoding)))
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a string to translate.')
            return
        
        params = {'key': self.apikey,
                  'target': DEFAULT_TARGET_LANGUAGE,
                  'q': args[1]}
        
        try:
            params['q'] = params['q'].decode(self.factory.encoding)
        except UnicodeDecodeError:
            bot.reply(prefix, channel, 'Strings to be translated must use the '
                                       '"%s" character encoding. Check your '
                                       'client settings and try again.'
                                        % self.factory.encoding)
            return
        
        for language in self.languages:
            if params['q'].startswith(language + ':'):
                params['q'] = params['q'].split(':', 1)[1]
                params['source'] = language
                break
        
        print params['q']
        
        for language in self.languages:
            if params['q'].endswith(' ' + language + ':'):
                params['q'] = params['q'].rsplit(' ', 1)[0]
                params['target'] = language
                break
        
        print params['q']
        
        params['q'] = params['q'].strip()
        if not params['q']:
            bot.reply(prefix, channel, 'Please specify a string to translate.')
            return
        
        params['q'] = params['q'].encode('utf-8')
        
        d = self.factory.get_http('https://www.googleapis.com/language/translate/v2?%s' % urllib.urlencode(params))
        d.addCallback(self.reply, bot, prefix, reply_target, channel,
                      params, args)
        return d


google = GoogleCommand()
lucky = ImFeelingLuckyCommand()
gcalc = GoogleCalculatorCommand()
define = GoogleDefinitionCommand()
translate = GoogleTranslateCommand()
