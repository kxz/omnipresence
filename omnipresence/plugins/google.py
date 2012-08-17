"""Commands related to Google Web services."""
import json

from bs4 import BeautifulSoup

from omnipresence import web


class GoogleSearch(web.WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Google search on the given
    search string.
    """
    name = 'google'
    arg_type = 'a search query'
    url = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s'

    def reply(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        try:
            results = data['responseData']['results']
        except KeyError:
            results = []
        if not results:
            bot.reply(prefix, channel,
                      'Google: No results found for \x02%s\x02.' % args[1])
            return
        bot.reply(reply_target, channel, u'\n'.join(
                    u'Google: ({0}/{1}) {2} \u2014 \x02{3}\x02: {4}'.format(
                      i + 1, len(results), result['unescapedUrl'],
                      web.textify_html(result['titleNoFormatting']),
                      web.textify_html(BeautifulSoup(result['content'])))
                    for i, result in enumerate(results)))


default = GoogleSearch()
