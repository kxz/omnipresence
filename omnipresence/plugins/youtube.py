import json
import urllib

from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand
from omnipresence import util

from omnipresence import web


class YouTubeSearch(web.WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a YouTube search for videos 
    matching the given search string.
    """
    name = 'youtube'
    arg_type = 'a search query'
    url = ('http://gdata.youtube.com/feeds/api/videos?v=2&q=%s&alt=json&'
           "fields=entry(title,link[@rel%%3D'alternate'],yt:statistics)")
    
    def reply(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        try:
            results = data['feed']['entry']
        except KeyError:
            results = []
        if not results:
            bot.reply(prefix, channel,
                      'Google: No results found for \x02%s\x02.' % args[1])
            return
        messages = []
        for i, result in enumerate(results):
            message = u'YouTube: ({0}/{1}) {2} \u2014 \x02{3}\x02'.format(
              i + 1, len(results),
              result['link'][0]['href'].split('&', 1)[0],
              result['title']['$t'])
            # A lot of video queries don't return associated view
            # statistics for one reason or another.
            if 'yt$statistics' in result: 
                message += u' \u2014 {0:n} views'.format(
                             int(result['yt$statistics']['viewCount']))
            messages.append(message)
        bot.reply(reply_target, channel, u'\n'.join(messages))


default = YouTubeSearch()
