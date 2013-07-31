"""Commands for Rotten Tomatoes searches."""

import json

from omnipresence.web import WebCommand


class MovieSearch(WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search Rotten Tomatoes for movies
    with the given title.
    """
    name = 'rottentomatoes'
    arg_type = 'a search string'
    url = ('http://api.rottentomatoes.com/api/public/v1.0/movies.json?'
           'q=%s&apikey=')

    def registered(self):
        self.url += self.factory.config.get('rottentomatoes', 'apikey')

    def reply(self, response, bot, prefix, reply_target, channel, args):
        data = json.loads(response[1])
        try:
            movies = data['movies']
        except KeyError:
            movies = []
        if not movies:
            bot.reply(
                prefix, channel,
                'Rotten Tomatoes: No results found for \x02%s\x02.' % args[1])
            return
        messages = []
        for i, movie in enumerate(movies):
            message = u'Rotten Tomatoes ({0}/{1}): \x02{2}\x02 ({3})'.format(
                i + 1, len(movies), movie['title'], movie['year'])
            message += u' \u2014 MPAA {0}'.format(movie['mpaa_rating'])
            if movie['runtime']:
                message += u', {0} minutes'.format(movie['runtime'])
            if movie['abridged_cast']:
                cast = (x['name'] for x in movie['abridged_cast'])
                message += u' \u2014 {0}'.format(u', '.join(cast))
            # Only provide scores if there are textual descriptions
            # indicating that a sufficient number of critics or users
            # have rated the film for the scores to be meaningful.
            rating_messages = []
            for source in ('critics', 'audience'):
                if ('%s_rating' % source) in movie['ratings']:
                    rating_messages.append(u'{0}% {1}'.format(
                        movie['ratings']['%s_score' % source], source))
            if rating_messages:
                message += u' \u2014 ' + u'; '.join(rating_messages)
            message += u' \u2014 {0}'.format(movie['links']['alternate'])
            messages.append(message)
        bot.reply(reply_target, channel, u'\n'.join(messages))


default = MovieSearch()
