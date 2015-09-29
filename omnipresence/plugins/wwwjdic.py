"""Omnipresence plugins for WWWJDIC."""


import re

from bs4 import BeautifulSoup, SoupStrainer
try:
    from waapuro import romanize
except ImportError:
    romanize = None

from omnipresence import web


#: A regex for identifying pronunciations in a JDIC entry, if present.
PRONUNCIATIONS_RE = re.compile(ur'\[([^\]]+)\]')

#: A regex for identifying markings at the end of a kana pronunciation.
MARKINGS_RE = re.compile(ur'(?:\([^)]+\))+$')


class WWWJDICSearch(web.WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Look up a Japanese word or phrase in Jim
    Breen's WWWJDIC <http://wwwjdic.org/>.
    """
    name = 'wwwjdic'
    arg_type = 'a term to look up'
    url = 'http://nihongo.monash.edu/cgi-bin/wwwjdic.cgi?1ZUJ%s'

    def reply(self, response, bot, prefix, reply_target, channel, args):
        soup = BeautifulSoup(response[1], parse_only=SoupStrainer('pre'))
        if not soup.pre:
            bot.reply(prefix, channel, 'WWWJDIC: No results found for '
                                       '\x02{0}\x02.'.format(args[1]))
            return
        results = unicode(soup.pre.string).strip().split(u'\n')
        messages = []
        for i, result in enumerate(results):
            if not result.strip():
                continue
            # Find the kana pronunciations and add their romanizations.
            if romanize:
                match = PRONUNCIATIONS_RE.search(result)
                if match is None:
                    pronunciations = result.split(None, 1)[0]
                    start = 0
                    end = len(pronunciations)
                else:
                    pronunciations = match.group(1)
                    start = match.start(1)
                    end = match.end(1)
                pronunciations = pronunciations.split(u';')
                with_romanizations = []
                for pronunciation in pronunciations:
                    match = MARKINGS_RE.search(pronunciation)
                    if match is not None:
                        pronunciation = pronunciation[:match.start()]
                    with_romanizations.append(
                        pronunciation +
                        u' (' + romanize(pronunciation) + u')' +
                        (u'' if match is None else u' ' + match.group(0)))
                result = (result[:start] +
                          u'; '.join(with_romanizations) +
                          result[end:])
            # Strip off the trailing slash for the last gloss, then
            # replace the first slash with nothing and the remaining
            # ones with semicolons, in an approximation of the Web
            # interface.
            message = result[:-1].strip()
            message = message.replace(u'/', u'', 1)
            message = message.replace(u'/', u'; ')
            messages.append(u'WWWJDIC: ({0}/{1}) {2}'.format(
                              i + 1, len(results), message))
        bot.reply(reply_target, channel, u'\n'.join(messages))


wwwjdic = WWWJDICSearch()
