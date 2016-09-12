# -*- test-case-name: omnipresence.test.test_html -*-
"""HTML parsing utility functions."""


from __future__ import unicode_literals

from bs4 import BeautifulSoup, NavigableString, Tag


#: The default parser to use for BeautifulSoup.
DEFAULT_BS4_PARSER = 'html.parser'


def parse(markup):
    """Return a `BeautifulSoup` object from the given markup.

    This is a convenience method that additionally adds a default parser
    argument, to avoid warnings.
    """
    return BeautifulSoup(markup, DEFAULT_BS4_PARSER)


def textify(html, format_output=True):
    """Convert the contents of *html* to a Unicode string.  *html* can
    be either a string containing HTML markup, or a Beautiful Soup tag
    object.  If *format_output* is true, mIRC-style formatting codes
    are added to simulate common element styles."""
    if isinstance(html, BeautifulSoup) or isinstance(html, Tag):
        soup = html
    else:
        soup = parse(html)

    def descend(soup):
        if not format_output:
            return u''.join(soup.strings)
        # Grab the node's tag name, and add formatting if necessary.
        if soup.name in (u'b', u'strong'):
            fmt = u'\x02{0}\x02'
        elif soup.name in (u'i', u'u', u'em', u'cite', u'var'):
            fmt = u'\x16{0}\x16'
        elif soup.name == u'sup':
            fmt = u'^{0}'
        elif soup.name == u'sub':
            fmt = u'_{0}'
        else:
            fmt = u'{0}'
        # Recurse into the node's contents.
        text = u''
        for k in soup.children:
            if isinstance(k, NavigableString):
                text += unicode(k)
            else:  # is another soup element
                text += descend(k)
        return fmt.format(text)

    # Don't strip whitespace until the very end, in order to avoid
    # misparsing constructs like <span>hello<b> world</b></span>.
    return u' '.join(descend(soup).split()).strip()
