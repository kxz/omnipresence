"""Omnipresence plugins for Microsoft Translator."""


import json
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import time
import urllib

from twisted.internet import defer
from twisted.plugin import IPlugin
from twisted.web.client import FileBodyProducer
from twisted.web.http_headers import Headers
from zope.interface import implements

from omnipresence import web
from omnipresence.iomnipresence import ICommand


#: The default target language to use if the user does not specify one
#: and one is not given in the plugin configuration.
#
# Yeah, the name sounds silly, but it's accurate.
DEFAULT_DEFAULT_TARGET = 'en'

#: The URL of the Microsoft Azure OAuth endpoint.
OAUTH_URL = 'https://datamarket.accesscontrol.windows.net/v2/OAuth2-13'

#: The URL of the Microsoft Translator AJAX endpoint.  The format
#: template items are replaced with the method and GET parameters.
TRANSLATOR_URL = 'http://api.microsofttranslator.com/V2/Ajax.svc/{}?{}'


class MicrosoftTranslator(object):
    """Command plugin for simple translation requests."""
    implements(IPlugin, ICommand)
    name = 'mstranslate'

    def __init__(self):
        self.languages = {}
        self.access_token = None
        self.token_expiry = -1

    @defer.inlineCallbacks
    def obtain_access_token(self):
        """Return a valid Microsoft Azure OAuth access token."""
        start_time = time.time()
        if self.access_token is None or self.token_expiry < start_time:
            headers = Headers()
            headers.addRawHeader('Content-Type',
                                 'application/x-www-form-urlencoded')
            params = {'client_id': self.client_id,
                      'client_secret': self.client_secret,
                      'scope': 'http://api.microsofttranslator.com',
                      'grant_type': 'client_credentials'}
            bp = FileBodyProducer(StringIO(urllib.urlencode(params)))
            _, content = yield web.request(
                'POST', OAUTH_URL, headers=headers, bodyProducer=bp)
            credentials = json.loads(content)
            if 'error_description' in credentials:
                raise IOError('Could not authenticate to Microsoft Azure: ' +
                              credentials['error_description'])
            # Coerce the access token to a byte string to avoid problems
            # inside Twisted's header handling code down the line.
            self.access_token = str(credentials['access_token'])
            self.token_expiry = start_time + int(credentials['expires_in'])
        defer.returnValue(self.access_token)

    @defer.inlineCallbacks
    def call_endpoint(self, method, params=None):
        """Make a request to the Microsoft Translator AJAX endpoint with
        the given method and parameters, and return the response."""
        access_token = yield self.obtain_access_token()
        headers = Headers()
        headers.addRawHeader('Authorization', 'Bearer ' + access_token)
        if params is None:
            params = {}
        _, content = yield web.request('GET',
            TRANSLATOR_URL.format(method, urllib.urlencode(params)),
            headers=headers)
        defer.returnValue(json.loads(content.decode('utf-8-sig')))

    def registered(self):
        self.client_id = self.factory.config.get(
            'mstranslate', 'client_id')
        self.client_secret = self.factory.config.get(
            'mstranslate', 'client_secret')
        self.default_target = self.factory.config.getdefault(
            'mstranslate', 'default_target', DEFAULT_DEFAULT_TARGET)
        self.load_languages()

    @defer.inlineCallbacks
    def load_languages(self):
        codes = yield self.call_endpoint('GetLanguagesForTranslate')
        names = yield self.call_endpoint('GetLanguageNames', {
            'languageCodes': json.dumps(codes),
            'locale': self.default_target})
        # Same logic as above for the coercion here.
        self.languages = dict(map(lambda c, n: (str(c), n), codes, names))

    @defer.inlineCallbacks
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        if len(args) < 2:
            bot.reply(prefix, channel,
                      'Please specify a string to translate.')
            return

        params = {'text': args[1], 'to': self.default_target}
        # Extract the source language code if it's present.
        for language in self.languages:
            if params['text'].startswith(language + ':'):
                params['text'] = params['text'].split(':', 1)[1]
                params['from'] = language
                break
        # Same for the target language code.
        for language in self.languages:
            if params['text'].endswith(' ' + language + ':'):
                params['text'] = params['text'].rsplit(' ', 1)[0]
                params['to'] = language
                break

        params['text'] = params['text'].strip()
        if not params['text']:
            bot.reply(prefix, channel,
                      'Please specify a string to translate.')
            return

        translation = yield self.call_endpoint('Translate', params)
        if 'Exception:' in translation:
            raise IOError(translation)
        bot.reply(reply_target, channel,
                  u'Microsoft Translate: \x02{}\x02'.format(translation))

    def help(self, args):
        if len(args) >= 3 and args[2] == 'languages':
            if not self.languages:
                return 'No supported languages were found.'
            lang_list = u', '.join(u'\x02{}\x02 ({})'.format(k, v) for k, v in
                                   sorted(self.languages.iteritems()))
            return u'Supported languages: {}.'.format(lang_list)
        return ('\x02{0[1]}\x02 [\x1Fsource\x1F\x02:\x02]\x1Ftext\x1F '
                '[\x1Ftarget\x1F\x02:\x02] - Translate text using '
                'Microsoft Translator. For a list of source and target '
                'language codes, see \x02{0[0]} {0[1]} languages\x02. '
                'If not given, they default to automatic detection and '
                '\x02{1}\x02, respectively.'
                .format(args, self.default_target))


default = MicrosoftTranslator()
