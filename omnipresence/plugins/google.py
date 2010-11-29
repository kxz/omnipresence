from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand

import json
import urllib

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
    
    def reply_with_results(self, response, bot, user, channel, args):
        data = json.loads(response[1])
        
        if 'responseData' not in data or 'results' not in data['responseData'] or len(data['responseData']['results']) < 1:
            bot.reply(user, channel, 'Google: No results found for \x02%s\x02.'
                                      % args[1])
        
        results = data['responseData']['results'][:self.max_results]
        
        i = 1
        messages = []
        
        for result in results:
            message = u''
            
            if len(results) > 1:
                message += u'(%d) ' % i
            
            message += (u'\x02%s\x02: %s'
                          % (util.decode_html_entities(result['titleNoFormatting']),
                             result['unescapedUrl']))
            
            messages.append(message)
            i += 1
        
        bot.reply(user, channel, ((u'Google: ' + u' \u2014 '.join(messages)) \
                                   .encode(self.factory.encoding)))
    
    def execute(self, bot, user, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(user, channel, 'Please specify a search string.')
            return
        
        d = self.factory.get_http('http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s' % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, user, channel, args)
        return d

class ImFeelingLuckyCommand(GoogleCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Google search on the given 
    search string, and return only the first result.
    """
    name = 'lucky'
    max_results = 1


google = GoogleCommand()
lucky = ImFeelingLuckyCommand()