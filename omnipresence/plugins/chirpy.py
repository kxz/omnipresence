from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand

import sqlobject
import random

class ChirpyCommand(object):
    implements(IPlugin, ICommand)
    name = 'chirpy'
    
    table = None

    def execute(self, bot, user, channel, args):
        if not self.table:
            sqlobject_uri = self.factory.config.get('chirpy', 'database')
            
            class ChirpyQuote(sqlobject.SQLObject):
                _connection = sqlobject.connectionForURI(sqlobject_uri)
                
                class sqlmeta:
                    fromDatabase = True
                    table = self.factory.config.get('chirpy', 'table')
            
            self.table = ChirpyQuote
        
        quotes = self.table.select('CHAR_LENGTH(body) < 400 AND approved = 1')
        if quotes.count() > 0:
            quote = random.choice(list(quotes))
            quote_text = quote.body.replace('\n', ' ')
            bot.reply(user, channel, u'QDB: (#%d, %+d/%d) %s' % (quote.id,
                                                                 quote.rating,
                                                                 quote.votes,
                                                                 quote_text))
        else:
            bot.reply(user, channel, u"QDB: Couldn't find any quotes!")


chirpycommand = ChirpyCommand()
