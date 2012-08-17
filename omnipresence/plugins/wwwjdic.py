from bs4 import BeautifulSoup, SoupStrainer

from omnipresence import web


class WWWJDICSearch(web.WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Look up a Japanese word or phrase in Jim
    Breen's WWWJDIC <http://wwwjdic.org/>.
    """
    name = 'wwwjdic'
    arg_type = 'a term to look up'
    url = 'http://www.csse.monash.edu.au/~jwb/cgi-bin/wwwjdic.cgi?1ZUJ%s'

    def reply(self, response, bot, prefix, reply_target, channel, args):
        soup = BeautifulSoup(response[1], parseOnlyThese=SoupStrainer('pre'))

        if soup.pre:
            results = unicode(soup.pre.string).strip().split(u'\n')
            messages = []
            # Strip off the trailing slash for the last gloss, then replace
            # the first slash with nothing and the remaining ones with
            # semicolons, in an approximation of the Web interface.
            for i, result in enumerate(results):
                message = result[:-1].strip()
                message = message.replace(u'/', u'', 1)
                message = message.replace(u'/', u'; ')
                messages.append(u'WWWJDIC: ({0}/{1}) {2}'.format(
                                  i + 1, len(results), message))
            bot.reply(reply_target, channel, u'\n'.join(messages))
        else:
            bot.reply(prefix, channel, 'WWWJDIC: No results found for '
                                       '\x02{0}\x02.'.format(args[1]))


wwwjdic = WWWJDICSearch()
