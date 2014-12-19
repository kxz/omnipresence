"""Commands related to Google Web services."""
import json

from bs4 import BeautifulSoup

from omnipresence.web import WebCommand, textify_html as txt


class GoogleSearch(WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Google search on the
    given search string.
    """
    name = 'google'
    arg_type = 'a search query'
    url = 'https://www.googleapis.com/customsearch/v1?q=%s'

    def registered(self):
        self.url += '&key=%s&cx=%s' % (
            self.factory.config.get('google', 'key'),
            self.factory.config.get('google', 'cx'))

    def reply(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        if 'error' in data:
            raise IOError('Google API error: ' + data['error']['message'])
        items = data.get('items')
        if not items:
            bot.reply(prefix, channel,
                      'Google: No results found for \x02%s\x02.' % args[1])
            return
        bot.reply(reply_target, channel, u'\n'.join(
                    u'Google: ({}/{}) {} \u2014 \x02{}\x02: {}'.format(
                      i + 1, len(items), item['link'], item['title'],
                      txt(BeautifulSoup(item['htmlSnippet'])))
                    for i, item in enumerate(items)))


default = GoogleSearch()
