import random
import re

import sqlobject
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import util
from omnipresence.iomnipresence import ICommand

ID_SYNTAX = re.compile(r'^#([0-9]+)$')

# An approximate Python version of the "get_search_instruction" function
# in Chirpy/UI/WebApp.pm.  Originally contributed by James Kalenius.
#
# <https://bitbucket.org/kxz/omnipresence/issue/17>
QUERY_REGEX = re.compile(r'"(.*?)"|"([^"]+)$|(\S+)')
TAG_REGEX = re.compile(r'^tag:', re.IGNORECASE)

def get_search_instruction(query):
    queries = []
    tags = []

    m = QUERY_REGEX.findall(query)
    for match in m:
        if match[0]:
            queries.append(match[0])
        elif match[1]:
            queries.append(match[1])
        elif match[2]:
            if TAG_REGEX.match(match[2]):
                # Ensure that tag matches aren't blank.
                t = TAG_REGEX.sub('', match[2])
                if t:
                    tags.append(t)
            else:
                queries.append(match[2])
    return (queries, tags)


class ChirpyCommand(object):
    """
    \x02%s\x02 [\x02#\x02\x1Fid\x1F|\x1Fsearch_string\x1F] - Retrieve a quote 
    from the quote database.  If neither a quote ID nor a search string is 
    specified, return a random short quote.
    """
    implements(IPlugin, ICommand)
    name = 'chirpy'
    
    table = None
    
    def registered(self):
        sqlobject_uri = self.factory.config.get('chirpy', 'database')
        
        self.connection = sqlobject.connectionForURI(sqlobject_uri)
        self.prefix = self.factory.config.getdefault('chirpy', 'prefix', 'qdb_')
        self.quote_url = self.factory.config.getdefault('chirpy', 'quote_url', '')
        
        class ChirpyQuote(sqlobject.SQLObject):
            _connection = self.connection
            
            class sqlmeta:
                fromDatabase = True
                table = self.prefix + 'quotes'
        
        self.quotes = ChirpyQuote

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        query = sqlobject.AND(sqlobject.func.CHAR_LENGTH(self.quotes.q.body)<192,
                              self.quotes.q.approved==1)
        
        if len(args) > 1:
            id_match = ID_SYNTAX.match(args[1])
            if id_match:
                id = int(id_match.group(1))
                query = sqlobject.AND(self.quotes.q.id==id,
                                      self.quotes.q.approved==1)
            else:
                (strings, tags) = get_search_instruction(args[1])
                
                arg_queries = [self.quotes.q.body.contains(string)
                               for string in strings]
                
                # Whittle down the set of quotes containing the
                # specified tags.  This is not particularly efficient,
                # but the SQLObject contortions that would be involved
                # in an entirely query-based solution make my head hurt.
                tagged_quotes = None
                
                for tag in tags:
                    tag_quotes_query = ('SELECT quote_id FROM {0}quote_tag '
                                        'LEFT JOIN {0}tags '
                                        'ON {0}quote_tag.tag_id = {0}tags.id '
                                        'WHERE {0}tags.tag = {1}') \
                                       .format(self.prefix,
                                               self.connection.sqlrepr(tag))
                    results = set((quote[0] for quote in
                                   self.connection.queryAll(tag_quotes_query)))
                    
                    if tagged_quotes is None:
                        tagged_quotes = results
                    else:
                        tagged_quotes &= results
                
                if tagged_quotes:
                    tag_query = sqlobject.OR(*[self.quotes.q.id==quote_id
                                               for quote_id in tagged_quotes])
                    arg_queries.append(tag_query)
                
                query = sqlobject.AND(self.quotes.q.approved==1, *arg_queries)
        
        quotes = list(self.quotes.select(query))
        
        if not quotes:
            bot.reply(prefix, channel, "QDB: Couldn't find any quotes!")
            return
        
        quote = random.choice(quotes)
        quote_text = quote.body.decode('utf-8').replace('\n', ' ')
        reply = u'QDB: (#%d, %+d/%d) %s' % (quote.id, quote.rating,
                                            quote.votes, quote_text)

        if self.quote_url:
            reply += u' \u2014 ' + self.quote_url % quote.id
        
        bot.reply(reply_target, channel, reply)


chirpycommand = ChirpyCommand()
