try:
    from xml.etree.cElementTree import ParseError, XML
except ImportError:
    from xml.etree.ElementTree import ParseError, XML
import urllib

from zope.interface import implements
from twisted.plugin import IPlugin
from omnipresence.iomnipresence import ICommand
from omnipresence import util


class APIError(Exception):
    pass


class Query(object):
    """
    \x02%s\x02 \x1Fquery_string\x1F - Retrieve Wolfram|Alpha results for the
    given query string.
    """
    implements(IPlugin, ICommand)
    name = 'wolframalpha'
    
    def registered(self):
        self.appid = self.factory.config.get('wolframalpha', 'appid')
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a query string.')
            return
        
        params = urllib.urlencode({'appid': self.appid,
                                   'input': args[1],
                                   'format': 'plaintext'})
        
        d = self.factory.get_http('http://api.wolframalpha.com/v2/query?%s'
                                   % params)
        d.addCallback(self.reply_with_results, bot, prefix, reply_target, channel, args)
        return d
    
    def reply_with_results(self, response, bot, prefix, reply_target, channel, args):
        try:
            queryresult = XML(response[1])
        except ParseError:
            raise APIError('Wolfram|Alpha API returned invalid XML.')
        
        if queryresult.get('error', 'true') == 'true':
            error_message = queryresult.findtext('error/msg')
            
            if error_message is None:
                raise APIError('Wolfram|Alpha API encountered an error.')
            else:
                raise APIError('Wolfram|Alpha API encountered an error: '
                               '\x02%s\x02.' % error_message)
        
        if queryresult.get('success', 'false') == 'false':
            # TODO: More detailed failure messages.
            bot.reply(prefix, channel, 'Wolfram|Alpha could not interpret the '
                                       'query \x02%s\x02.' % args[1])
            return
        
        messages = []
        
        warnings = queryresult.find('warnings')
        if warnings is not None:
            for warning in list(warnings):
                if 'text' in warning:
                    messages.append(warning.get('text') +
                                    # input reinterpretations
                                    (' ' + warning.get('new')
                                     if 'new' in warning else ''))
        
        assumption = queryresult.find('assumptions/assumption/value')
        if assumption is not None:
            messages.append('Assuming \x02%s\x02' % assumption.get('desc'))
        
        pods = queryresult.findall('pod')
        if not pods:
            bot.reply(prefix, channel, 'Wolfram|Alpha has no plain-text '
                                       'results for the query \x02%s\x02.'
                                        % args[1])
            return
        for pod in pods:
            subpods = pod.findall('subpod')
            pod_messages = []
            for subpod in subpods:
                title = subpod.get('title')
                text = subpod.findtext('plaintext').replace('\n', '; ')
                
                if not text:
                    continue
                
                if title:
                    pod_messages.append('%s: %s' % (title, text))
                else:
                    pod_messages.append(text)
            if pod_messages:
                messages.append('%s: \x02%s\x02' % (pod.get('title'),
                                                    ' / '.join(pod_messages)))
        
        bot.reply(reply_target, channel,
                  u'Wolfram|Alpha: ' + u' \u2014 '.join(messages))


class Dictionary(Query):
    """
    \x02%s\x02 \x1Fterm\x1F - Get a definition for the given term from
    Wolfram|Alpha.
    """
    implements(IPlugin, ICommand)
    name = 'wolframalpha_define'
    
    def registered(self):
        self.appid = self.factory.config.get('wolframalpha', 'appid')
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a term to look up.')
            return
        
        params = urllib.urlencode({'appid': self.appid,
                                   'input': 'definition of %s' % args[1],
                                   'format': 'plaintext'})
        
        d = self.factory.get_http('http://api.wolframalpha.com/v2/query?%s'
                                   % params)
        d.addCallback(self.reply_with_results, bot, prefix, reply_target, channel, args)
        return d


default = Query()
define = Dictionary()
