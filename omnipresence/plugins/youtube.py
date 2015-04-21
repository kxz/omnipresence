"""Commands related to YouTube."""
import json

from omnipresence import web


class YouTubeSearch(web.WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a YouTube search for videos
    matching the given search string.
    """
    name = 'youtube'
    arg_type = 'a search query'
    url = ('https://www.googleapis.com/youtube/v3/search?q=%s&'
           'type=video&part=snippet&fields=items(id,snippet)')

    def registered(self):
        self.url += '&key=%s' % self.factory.config.get('google', 'key')

    def reply(self, response, bot, prefix, reply_target, channel, args):
        items = json.loads(response[1]).get('items', [])
        if not items:
            bot.reply(prefix, channel,
                      'YouTube: No results found for \x02%s\x02.' % args[1])
            return
        messages = []
        for i, item in enumerate(items):
            message = (u'YouTube: ({}/{}) '
                       u'https://www.youtube.com/watch?v={} \u2014 '
                       u'\x02{}\x02'.format(
                i + 1, len(items),
                item['id']['videoId'],
                item['snippet']['title']))
            if item['snippet']['description']:
                message += u': ' + item['snippet']['description']
            messages.append(message)
        bot.reply(reply_target, channel, u'\n'.join(messages))


default = YouTubeSearch()
