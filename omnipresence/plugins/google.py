"""Commands related to Google Web services."""
import json

from BeautifulSoup import BeautifulSoup

from omnipresence import web


class GoogleSearch(web.WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Google search on the given 
    search string.
    """
    name = 'google'
    arg_type = 'a search query'
    url = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s'
    max_results = 3
    
    def reply(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        
        try:
            results = data['responseData']['results'][:self.max_results]
        except KeyError:
            results = []
        
        if len(results) < 1:
            bot.reply(prefix, channel,
                      'Google: No results found for \x02%s\x02.' % args[1])
            return
        
        if len(results) == 1:
            result = results[0]
            
            content = web.textify_html(BeautifulSoup(result['content']))
            if len(content) > 128:
                content = content[:128] + u'\u2026'
            
            messages = [(u'\x02%s\x02: %s \u2014 %s'
                           % (web.decode_html_entities(result['titleNoFormatting']),
                              content, result['unescapedUrl']))]
        else:
            messages = [(u'(%d) \x02%s\x02: %s'
                           % (i + 1,
                              web.decode_html_entities(result['titleNoFormatting']),
                              result['unescapedUrl']))
                        for i, result in enumerate(results)]
        
        bot.reply(reply_target, channel,
                  ((u'Google: ' + u' \u2014 '.join(messages)) \
                   .encode(self.factory.encoding)))


class ImFeelingLucky(GoogleSearch):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Google search on the given 
    search string, and return only the first result.
    """
    name = 'lucky'
    max_results = 1


google = GoogleSearch()
lucky = ImFeelingLucky()
