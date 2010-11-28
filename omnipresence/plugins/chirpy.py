from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand

import random
import re
import sqlobject

ID_SYNTAX = re.compile(r'^#([0-9]+)$')

class ChirpyCommand(object):
    """
    \x02%s\x02 [\x02#\x02\x1Fid\x1F|\x1Fsearch_string\x1F] - Retrieve a quote 
    from the quote database.  If neither a quote ID nor a search string is 
    specified, return a random quote less than 400 characters long.
    """
    implements(IPlugin, ICommand)
    name = 'chirpy'
    
    table = None
    
    def registered(self):
        sqlobject_uri = self.factory.config.get('chirpy', 'database')
        
        class ChirpyQuote(sqlobject.SQLObject):
            _connection = sqlobject.connectionForURI(sqlobject_uri)
            
            class sqlmeta:
                fromDatabase = True
                table = self.factory.config.get('chirpy', 'table')
        
        self.table = ChirpyQuote

    def execute(self, bot, user, channel, args):
        args = args.split(None, 1)[1:]
        
        if args:
            id_match = ID_SYNTAX.match(args[0])
            if id_match:
                id = int(id_match.group(1))
                q_expression = sqlobject.AND(self.table.q.id==id,
                                             self.table.q.approved==1)
            else:
                q_expression = sqlobject.AND(self.table.q.body.contains(args[0]),
                                             self.table.q.approved==1)
        else:
            q_expression = 'CHAR_LENGTH(body) < 400 AND approved = 1'
        
        quotes = self.table.select(q_expression)
        if quotes.count() > 0:
            quote = random.choice(list(quotes))
            quote_text = quote.body.replace('\n', ' ')
            bot.reply(user, channel, 'QDB: (#%d, %+d/%d) %s' % (quote.id,
                                                                quote.rating,
                                                                quote.votes,
                                                                quote_text))
        else:
            bot.reply(user, channel, "QDB: Couldn't find any quotes!")


chirpycommand = ChirpyCommand()
