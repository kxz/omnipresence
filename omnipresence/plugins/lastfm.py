import json
import urllib

from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand

from omnipresence import util


class LastFmCommand(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Last.fm search for artists 
    with a name matching the given search string.
    """
    implements(IPlugin, ICommand)
    name = 'lastfm'
    
    # The maximum number of results to return at any one time.
    max_results = 3
    
    def registered(self):
        self.apikey = self.factory.config.get('lastfm', 'apikey')
    
    def reply_with_results(self, response, bot, user, channel, args):
        data = json.loads(response[1])
        
        if ('error' in data):
            bot.reply(user, channel, 'Last.fm: API returned error: %s.'
                                      % data['message'])
            return
        
        if ('results' not in data or 'artistmatches' not in data['results'] or
            not isinstance(data['results']['artistmatches'], dict)):
            bot.reply(user, channel, 'Last.fm: No results found for \x02%s\x02.'
                                      % args[1])
            return
        
        results = data['results']['artistmatches']['artist']
        if not isinstance(results, list):
            results = [results]
        messages = []
        
        for i, result in enumerate(results):
            number = ''
            if len(results) > 1:
                number = '(%d) ' % (i + 1)
            
            listeners = ''
            if 'listeners' in result and result['listeners']:
                listeners = ', %s listeners' % result['listeners']
            
            messages.append(u'%s\x02%s\x02%s: %s' % (number, result['name'],
                                                     listeners, result['url']))
        
        bot.reply(user, channel, ((u'Last.fm: ' + u' \u2014 '.join(messages)) \
                                     .encode(self.factory.encoding)))
    
    def execute(self, bot, user, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(user, channel, 'Please specify a search string.')
            return
        
        params = urllib.urlencode({'method': 'artist.search',
                                   'artist': args[1],
                                   'api_key': self.apikey,
                                   'format': 'json',
                                   'limit': self.max_results})
        
        d = self.factory.get_http('http://ws.audioscrobbler.com/2.0/?%s'
                                   % params)
        d.addCallback(self.reply_with_results, bot, user, channel, args)
        return d


class LastFmAbbreviatedCommand(LastFmCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Last.fm search for the given 
    artist name, and return only the first result.
    """
    name = 'as'
    max_results = 1


lastfm = LastFmCommand()
lastfm_abbreviated = LastFmAbbreviatedCommand()