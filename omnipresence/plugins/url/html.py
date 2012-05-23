import cgi
import re

from BeautifulSoup import BeautifulSoup, SoupStrainer
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence.plugins.url import ITitleProcessor, Redirect
from omnipresence.web import textify_html


"""The maximum delay a ``<meta>`` refresh can have to be considered a
soft redirect.  This avoids catching pages that automatically refresh
themselves every minute or longer."""
MAX_REFRESH_DELAY = 15

REFRESH_RE = re.compile('refresh', re.IGNORECASE)


class HTMLTitleProcessor(object):
    implements(IPlugin, ITitleProcessor)
    supported_content_types = ('text/html', 'application/xhtml+xml')

    def process(self, headers, content):
        soup_kwargs = {}
        # If the HTTP "Content-Type" header specifies an encoding, try
        # to use it to decode the document.
        ctype, cparams = cgi.parse_header(headers.get('Content-Type', ''))
        if 'charset' in cparams:
            soup_kwargs['fromEncoding'] = cparams['charset']
        soup = BeautifulSoup(content, **soup_kwargs)

        # Handle any <meta> refreshes.
        for refresh in soup('meta', attrs={'http-equiv': REFRESH_RE,
                                           'content': True}):
            rseconds, rparams = cgi.parse_header(refresh['content'])
            try:
                rseconds = int(rseconds, 10)
            except ValueError:
                # Not a valid number; just pretend it's zero.
                rseconds = 0
            if rseconds < MAX_REFRESH_DELAY and 'url' in rparams:
                return Redirect(rparams['url'])

        # Just the title, ma'am.
        if soup.title:
            return u'\x02{0}\x02'.format(textify_html(soup.title))
        return None

h = HTMLTitleProcessor()
