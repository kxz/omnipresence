from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand
from omnipresence import util

from BeautifulSoup import BeautifulSoup, SoupStrainer
import urllib

class WWWJDICCommand(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Look up a Japanese word or phrase in Jim 
    Breen's WWWJDIC <http://wwwjdic.org/>, and return the first result.
    """
    implements(IPlugin, ICommand)
    name = 'wwwjdic'
    
    def reply_with_results(self, response, bot, prefix, reply_target, channel, args):
        soup = BeautifulSoup(response[1], parseOnlyThese=SoupStrainer('pre'))
        
        if soup.pre:
            results = soup.pre.string.extract().strip().split(u'\n')
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
                                       '\x02%s\x02.' % args[1])
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search term.')
            return
        
        d = self.factory.get_http('http://www.csse.monash.edu.au/~jwb/cgi-bin/wwwjdic.cgi?1ZUJ%s' % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, prefix, reply_target, channel, args)
        return d

wwwjdiccommand = WWWJDICCommand()