from BeautifulSoup import BeautifulSoup, SoupStrainer

from omnipresence import web


class WWWJDICSearch(web.WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Look up a Japanese word or phrase in Jim
    Breen's WWWJDIC <http://wwwjdic.org/>, and return the first result.
    """
    name = 'wwwjdic'
    arg_type = 'a term to look up'
    url = 'http://www.csse.monash.edu.au/~jwb/cgi-bin/wwwjdic.cgi?1ZUJ%s'

    def reply(self, response, bot, prefix, reply_target, channel, args):
        soup = BeautifulSoup(response[1], parseOnlyThese=SoupStrainer('pre'))

        if soup.pre:
            results = []
            # Strip off the trailing slash for the last gloss, then replace 
            # the first slash with nothing and the remaining ones with 
            # semicolons, in an approximation of the Web interface.
            for result in soup.pre.string.extract().strip().split(u'\n'):
                result = u'WWWJDIC: ' + result[:-1]
                result = result.replace(u'/', u'', 1)
                result = result.replace(u'/', u'; ')
                results.append(result)
            bot.reply(reply_target, channel, u'\n'.join(results))
        else:
            bot.reply(prefix, channel, 'WWWJDIC: No results found for '
                                       '\x02{0}\x02.'.format(args[1]))


wwwjdic = WWWJDICSearch()
