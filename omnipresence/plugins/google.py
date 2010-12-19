import json
import urllib
import urlparse

from BeautifulSoup import BeautifulSoup
from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand

from omnipresence import util


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
    
    def reply_with_results(self, response, bot, prefix, channel, args):
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
            
            content = util.textify_html(BeautifulSoup(result['content']))
            if len(content) > 128:
                content = content[:128] + '...'
            
            messages = [(u'\x02%s\x02: %s \u2014 %s'
                           % (util.decode_html_entities(result['titleNoFormatting']),
                              content, result['unescapedUrl']))]
        else:
            messages = [(u'(%d) \x02%s\x02: %s'
                           % (i + 1,
                              util.decode_html_entities(result['titleNoFormatting']),
                              result['unescapedUrl']))
                        for i, result in enumerate(results)]
        
        bot.reply(prefix, channel,
                  ((u'Google: ' + u' \u2014 '.join(messages)) \
                   .encode(self.factory.encoding)))
    
    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        d = self.factory.get_http('http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s' % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, prefix, channel, args)
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
    
    def reply_with_results(self, response, bot, prefix, channel, args):
        soup = BeautifulSoup(response[1])
        
        try:
            result = util.textify_html(soup.find('', 'r').b)
        except AttributeError:
            result = u'No result was returned!'
        
        bot.reply(prefix, channel, ((u'Google calc: %s' % result) \
                                    .encode(self.factory.encoding)))
    
    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify an expression.')
            return
        
        d = self.factory.get_http('http://www.google.com/search?q=%s' % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, prefix, channel, args)
        return d


class GoogleDefinitionCommand(object):
    """
    \x02%s\x02 \x1Fterm\x1F - Fetch the first set of definitions for the given 
    term from Google.
    """
    implements(IPlugin, ICommand)
    name = 'define'
    
    def reply_with_results(self, response, bot, prefix, channel, args):
        # Using SoupStrainer to parse only <li> tags yields a nested tree of 
        # <li> tags for some reason, so we just use "findAll" instead.
        soup = BeautifulSoup(response[1])
        lis = soup.findAll('li')
        
        results = []
        result_url = ''
        
        for li in lis:
            results.append(util.decode_html_entities(li.next).strip())
            
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
        
        bot.reply(prefix, channel, (u'Google dict: %s \u2014 %s'
                                      % (result, result_url)) \
                                    .encode(self.factory.encoding))
    
    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a term to look up.')
            return
        
        d = self.factory.get_http('http://www.google.com/search?q=define:%s'
                                   % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, prefix, channel, args)
        return d


google = GoogleCommand()
lucky = ImFeelingLuckyCommand()
gcalc = GoogleCalculatorCommand()
define = GoogleDefinitionCommand()