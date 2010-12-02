from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand

from BeautifulSoup import BeautifulSoup, SoupStrainer
import urllib

class WWWJDICCommand(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Look up a Japanese word or phrase in Jim 
    Breen's WWWJDIC <http://wwwjdic.org/>, and return the first result.
    """
    implements(IPlugin, ICommand)
    name = 'wwwjdic'
    
    def reply_with_results(self, response, bot, prefix, channel, args):
        soup = BeautifulSoup(response[1], parseOnlyThese=SoupStrainer('pre'))
        
        if soup.pre:
            result = soup.pre.string.extract().strip().split('\n')[0]
            # Strip off the trailing slash for the last gloss, then replace 
            # the first slash with nothing and the remaining ones with 
            # semicolons, in an approximation of the Web interface.
            result = result[:-1]
            result = result.replace('/', '', 1)
            result = result.replace('/', '; ')
            result = result.encode(self.factory.encoding)
            bot.reply(prefix, channel, 'WWWJDIC: %s' % result)
        else:
            bot.reply(prefix, channel, 'WWWJDIC: No results found for '
                                       '\x02%s\x02.' % args[1])
    
    def execute(self, bot, prefix, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search term.')
            return
        
        d = self.factory.get_http('http://www.csse.monash.edu.au/~jwb/cgi-bin/wwwjdic.cgi?1ZUJ%s' % urllib.quote(args[1]))
        d.addCallback(self.reply_with_results, bot, prefix, channel, args)
        return d

wwwjdiccommand = WWWJDICCommand()