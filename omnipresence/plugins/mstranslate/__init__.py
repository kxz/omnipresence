# -*- test-case-name: omnipresence.plugins.mstranslate.test_mstranslate
"""Event plugins for Microsoft Translator."""


import json
import re
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import time
import urllib

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import readBody
from twisted.web.http_headers import Headers

from ...plugin import EventPlugin, UserVisibleError
from ...web.http import default_agent, read_json_body


#: The default target language to use if neither the user nor the plugin
#: configuration specifies one.
DEFAULT_TARGET = 'en'

#: A regular expression matching a well-formed argument string.
ARGS_RE = re.compile(
    ur'^(?:(?P<from>[^: ]+):)?(?P<text>.+?)(?:\s+(?P<to>[^: ]+):)?$',
    re.UNICODE)

#: The URL of the Microsoft Cognitive Services Authentication Token API.
AUTH_URL = 'https://api.cognitive.microsoft.com/sts/v1.0/issueToken'

#: The lifetime, in seconds, of an authentication token.
#
# This isn't provided to us in the authentication response.  The docs at
# <http://docs.microsofttranslator.com/oauth-token.html> give a lifetime
# of 10 minutes, but recommend obtaining a new token every 8.
AUTH_TOKEN_TTL = 480

#: The URL of the Microsoft Translator Text Translation API.  The format
#: template item is replaced with the operation.
TRANSLATOR_URL = 'https://api.microsofttranslator.com/V2/Ajax.svc/{}'


def default_target(msg):
    """Return the default target specified in the settings for *msg*, or
    `DEFAULT_TARGET` if none is set."""
    return msg.settings.get('mstranslate.default_target',
                            default=DEFAULT_TARGET)


class Default(EventPlugin):
    """Translate text between languages with Microsoft Translator.

    The ``mstranslate.subscription_key`` :ref:`settings variable
    <settings-variable>` must be set to a valid Microsoft Cognitive
    Services subscription key.  For more information, see the `Text
    Translation API documentation`__.

    __ http://docs.microsofttranslator.com/text-translate.html

    The ``mstranslate.default_target`` settings variable is an optional
    two-letter language code specifying the target language to use if
    the user does not specify one.  It defaults to ``en`` for English.

    :alice: mstranslate hola
    :bot: Hello
    :alice: mstranslate hola de:
    :bot: Hallo
    """

    def __init__(self):
        self.agent = default_agent

        #: The set of valid language codes.
        self.languages = None

        # TODO:  For strictly correct per-channel request behavior, the
        # following properties need to be keyed on the settings venue.

        #: The bot's Microsoft Cognitive Services subscription key.
        self.subscription_key = None

        #: The last authentication token obtained, or `None` if none has
        #: been requested yet.
        self.auth_token = None

        #: The timestamp at which `auth_token` expires.
        self.token_expiry = -1

    @inlineCallbacks
    def obtain_auth_token(self):
        """Return a valid Microsoft Cognitive Services authentication
        token, obtained with the current subscription key if necessary.
        """
        start_time = time.time()
        if self.auth_token is None or self.token_expiry < start_time:
            headers = Headers()
            headers.addRawHeader('Ocp-Apim-Subscription-Key',
                                 self.subscription_key)
            headers.addRawHeader('Content-Length', '0')
            response = yield self.agent.request(
                'POST', AUTH_URL, headers=headers)
            if response.code != 200:
                data = yield readBody(response)
                self.log.error(
                    'Could not authenticate to Microsoft Cognitive '
                    'Services: {data}', data=data)
                raise UserVisibleError(
                    'Could not authenticate to Microsoft Cognitive '
                    'Services. Try again later.')
            # Coerce the access token to a byte string to avoid problems
            # inside Twisted's header handling code down the line.
            self.auth_token = (
                (yield readBody(response)).strip().decode('ascii'))
            self.token_expiry = start_time + AUTH_TOKEN_TTL
        returnValue(self.auth_token)

    @inlineCallbacks
    def call_endpoint(self, operation, params=None):
        """Make a request to the Microsoft Translator API endpoint with
        the given operation and parameters, and return the body of the
        response."""
        auth_token = yield self.obtain_auth_token()
        headers = Headers()
        headers.addRawHeader('Authorization', 'Bearer ' + auth_token)
        url = TRANSLATOR_URL.format(operation)
        if params is not None:
            url += '?' + urllib.urlencode(sorted(params.iteritems()))
        response = yield self.agent.request('GET', url, headers=headers)
        returnValue(json.loads((yield readBody(response)).decode('utf-8-sig')))

    @inlineCallbacks
    def initialize(self, msg):
        if self.subscription_key is None:
            self.subscription_key = msg.settings.get(
                'mstranslate.subscription_key')
            if self.subscription_key is None:
                self.log.error(
                    'No Microsoft Cognitive Services subscription key '
                    'has been specified in the Omnipresence settings. '
                    'Set the "mstranslate.subscription_key" variable '
                    'to a valid key, and reload the bot settings.')
                raise UserVisibleError(
                    'Could not authenticate to Microsoft Cognitive Services.')

        if self.languages is None:
            self.languages = frozenset((
                yield self.call_endpoint('GetLanguagesForTranslate')))

    @inlineCallbacks
    def on_command(self, msg):
        yield self.initialize(msg)

        if not msg.content:
            raise UserVisibleError('Please specify a string to translate.')
        match = ARGS_RE.match(msg.content.decode(msg.encoding, 'replace'))
        if match is None:
            raise UserVisibleError("Couldn't parse argument string.")

        params = {'to': default_target(msg)}
        text = match.group('text')
        source = match.group('from')
        target = match.group('to')

        # Check the validity of the source language code.
        if source is not None:
            if source in self.languages:
                params['from'] = source
            else:
                text = u'{}:{}'.format(source, text)
        # Same for the target language code.
        if target is not None:
            if target in self.languages:
                params['to'] = target
            else:
                text = u'{} {}:'.format(text, target)

        params['text'] = text.encode('utf-8').strip()
        if not params['text']:
            raise UserVisibleError('Please specify a string to translate.')

        translation = yield self.call_endpoint('Translate', params)
        if 'Exception:' in translation:
            raise IOError(translation.encode(errors='replace'))
        returnValue(translation)

    @inlineCallbacks
    def on_cmdhelp(self, msg):
        if msg.content == 'languages':
            yield self.initialize(msg)
            language_names = yield self.call_endpoint('GetLanguageNames', {
                'languageCodes': json.dumps(list(self.languages)),
                'locale': default_target(msg)})
            if not language_names:
                returnValue(u'No supported languages were found.')
            codes_to_names = zip(self.languages, language_names)
            lang_list = u', '.join(u'\x02{}\x02 ({})'.format(k, v)
                                   for k, v in sorted(codes_to_names))
            returnValue(u'Supported languages: {}.'.format(lang_list))
        returnValue(u'[\x1Fsource\x1F\x02:\x02]\x1Ftext\x1F '
                    u'[\x1Ftarget\x1F\x02:\x02] - Translate text using '
                    u'Microsoft Translator. For a list of source and '
                    u'target language codes, see help for \x02{0} '
                    u'languages\x02. If not given, they default to '
                    u'automatic detection and \x02{1}\x02, respectively.'
                    .format(msg.subaction, default_target(msg)))
