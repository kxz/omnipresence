# -*- coding: utf-8
# -*- test-case-name: omnipresence.plugins.wwwjdic.test_wwwjdic
"""Event plugins for searching WWWJDIC."""


import re
import urllib

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import readBody
try:
    from waapuro import romanize
except ImportError:
    romanize = None

from ...message import collapse
from ...plugin import EventPlugin, UserVisibleError
from ...web.html import parse as parse_html
from ...web.http import default_agent


#: A regex for identifying pronunciations in a JDIC entry, if present.
PRONUNCIATIONS_RE = re.compile(ur'\[([^\]]+)\]')

#: A regex for identifying markings at the end of a kana pronunciation.
MARKINGS_RE = re.compile(ur'(?:\([^)]+\))+$')


class Default(EventPlugin):
    u"""Define a Japanese word or phrase using `Jim Breen's WWWJDIC`__.

    __ http://wwwjdic.org/

    If `Waapuro`__ is installed, Nihon-shiki romanizations are provided
    alongside the kana spellings.

    __ https://pypi.python.org/pypi/waapuro

    :alice: wwwjdic kotoba
    :bot: 言葉(P);詞;辞 [ことば (kotoba) (P); けとば (ketoba) (言葉)(ok)] (n)
          (1) (See 言語) language; dialect;
          (2) (See 単語) word; words; phrase; term; expression; remark;
          (3) speech; (manner of) speaking; (P) (+28 more)
    """

    def __init__(self):
        self.agent = default_agent
        self.romanize = romanize

    @inlineCallbacks
    def on_command(self, msg):
        if not msg.content:
            raise UserVisibleError('Please specify a search query.')
        q = urllib.quote_plus(msg.content)
        response = yield self.agent.request('GET',
            'http://www.edrdg.org/cgi-bin/wwwjdic/wwwjdic?1ZUJ{}'.format(q))
        content = yield readBody(response)
        soup = parse_html(content)
        results = []
        if not soup.pre:
            returnValue(results)
        for result in soup.pre.string.strip().splitlines():
            if not result.strip():
                continue
            # Find the kana pronunciations and add their romanizations.
            if self.romanize:
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
                        u' (' + self.romanize(pronunciation) + u')' +
                        (u'' if match is None else u' ' + match.group(0)))
                result = (result[:start] +
                          u'; '.join(with_romanizations) +
                          result[end:])
            # Strip off the trailing slash for the last gloss, then
            # replace the first slash with nothing and the remaining
            # ones with semicolons, in an approximation of the Web
            # interface.
            result = result[:-1].strip()
            result = result.replace(u'/', u'', 1)
            result = result.replace(u'/', u'; ')
            results.append(result)
        returnValue(results)

    def on_cmdhelp(self, msg):
        return collapse("""\
            \x1Fquery\x1F - Look up a Japanese word or phrase in Jim
            Breen's WWWJDIC <http://wwwjdic.org/>.
            """)
