try:
    from xml.etree.cElementTree import ParseError, XML
except ImportError:
    from xml.etree.ElementTree import ParseError, XML
import urllib

from omnipresence.web import WebCommand


class APIError(Exception):
    pass


class WolframAlphaQuery(WebCommand):
    """
    \x02%s\x02 \x1Fquery_string\x1F - Retrieve Wolfram|Alpha results for the
    given query string.
    """
    name = 'wolframalpha'
    arg_type = 'a query string'
    url = ('http://api.wolframalpha.com/v2/query?input=%s&format=plaintext&'
           'appid=')
    
    def registered(self):
        self.url += self.factory.config.get('wolframalpha', 'appid')
    
    def reply(self, response, bot, prefix, reply_target, channel, args):
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


class DictionaryLookup(WolframAlphaQuery):
    """
    \x02%s\x02 \x1Fterm\x1F - Get a definition for the given term from
    Wolfram|Alpha.
    """
    name = 'wolframalpha_define'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        args.insert(1, 'definition of')
        args = ' '.join(args)
        super(DictionaryLookup, self).execute(bot, prefix, reply_target,
                                              channel, args)


default = WolframAlphaQuery()
define = DictionaryLookup()
