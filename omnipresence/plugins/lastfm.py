"""Commands related to Last.fm."""
import json

from omnipresence import web


class ArtistSearch(web.WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Perform a Last.fm search for artists 
    with a name matching the given search string.
    """
    name = 'lastfm'
    arg_type = 'a search query'
    url = ('http://ws.audioscrobbler.com/2.0/?method=artist.search&artist=%s&'
           'format=json&api_key=')

    def registered(self):
        self.url += self.factory.config.get('lastfm', 'apikey')
    
    def reply(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        if 'error' in data:
            bot.reply(prefix, channel, 'Last.fm: API returned error: %s.'
                                        % data['message'])
            return
        try:
            results = data['results']['artistmatches']['artist']
        except KeyError:
            results = []
        # "artistmatches" ends up being a string if there are no results.
        except TypeError:
            results = []
        if not results:
            bot.reply(prefix, channel,
                      'Last.fm: No results found for \x02%s\x02.' % args[1])
            return
        messages = []
        for i, result in enumerate(results):
            message = u'Last.fm: ({0}/{1}) {2} \u2014 \x02{3}\x02'.format(
              i + 1, len(results), result['url'], result['name'])
            if 'listeners' in result and result['listeners']:
                message += u', {0} listeners'.format(result['listeners'])
            messages.append(message)
        bot.reply(reply_target, channel, u'\n'.join(messages))


artist = ArtistSearch()
