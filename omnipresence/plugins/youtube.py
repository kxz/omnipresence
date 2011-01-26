import json
import urllib

from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand


class YouTubeCommand(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a YouTube search for videos 
    matching the given search string.
    """
    implements(IPlugin, ICommand)
    name = 'youtube'
    
    # The maximum number of results to return at any one time.
    max_results = 3
    
    def reply_with_results(self, response, bot, prefix, channel, args):
        data = json.loads(response[1])
        
        if 'feed' not in data or 'entry' not in data['feed']:
            bot.reply(prefix, channel, 'YouTube: No results found for '
                                       '\x02%s\x02.' % args[1])
            return
        
        results = data['feed']['entry']
        messages = []
        
        for i, result in enumerate(results):
            number = ''
            if len(results) > 1:
                number = '(%d) ' % (i + 1)
            
            messages.append(u'%s\x02%s\x02, %s views: %s'
                              % (number, result['title']['$t'],
                                 result['yt$statistics']['viewCount'],
                                 result['link'][0]['href'].split('&', 1)[0]))
        
        bot.reply(prefix, channel, ((u'YouTube: ' + u' \u2014 '.join(messages)) \
                                       .encode(self.factory.encoding)))
    
    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        params = urllib.urlencode({'q': args[1],
                                   'alt': 'json',
                                   'max-results': self.max_results,
                                   'fields': "entry(title,link[@rel='alternate'],yt:statistics)",
                                   'v': 2})
        
        d = self.factory.get_http('http://gdata.youtube.com/feeds/api/videos?%s'
                                   % params)
        d.addCallback(self.reply_with_results, bot, prefix, channel, args)
        return d


class YouTubeAbbreviatedCommand(YouTubeCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a YouTube search for videos 
    matching the given search string, and return only the first result.
    """
    name = 'yt'
    max_results = 1


youtube = YouTubeCommand()
youtube_abbreviated = YouTubeAbbreviatedCommand()