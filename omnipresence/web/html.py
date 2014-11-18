# -*- test-case-name: omnipresence.test.test_html -*-
"""HTML parsing utility functions."""


from __future__ import unicode_literals

from bs4 import BeautifulSoup, NavigableString, Tag


def textify(html, format_output=True):
    """Convert the contents of *html* to a Unicode string.  *html* can
    be either a string containing HTML markup, or a Beautiful Soup tag
    object.  If *format_output* is ``True``, IRC formatting codes are
    added to simulate common element styles."""
    if isinstance(html, BeautifulSoup) or isinstance(html, Tag):
        soup = html
    else:
        soup = BeautifulSoup(html)

    def descend(soup, format_output):
        if format_output:
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
            contents = u''
            for k in soup.contents:
                if isinstance(k, NavigableString):
                    contents += unicode(k)
                elif hasattr(k, 'name'):  # is another soup element
                    contents += descend(k, format_output)
            return fmt.format(contents)
        else:
            return u''.join(soup.strings)

    # Don't strip whitespace until the very end, in order to avoid
    # misparsing constructs like <span>hello<b> world</b></span>.
    return u' '.join(descend(soup, format_output).split()).strip()
