"""HTML parsing utility functions."""
import re

from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, NavigableString

# HTML hexadecimal character references (e.g. &#x201f;)
HTML_HEX_REFS = re.compile(r'&#x([0-9a-fA-F]+);')


def decode_html_entities(s):
    """Convert HTML entities in a string to their Unicode character 
    equivalents."""
    s = BeautifulStoneSoup(s,
                           convertEntities=BeautifulStoneSoup.HTML_ENTITIES) \
                          .contents[0]
    # BeautifulStoneSoup doesn't parse hexadecimal character references
    s = HTML_HEX_REFS.sub(lambda x: unichr(int(x.group(1), 16)), s)
    return s

def textify_html(soup):
    """Convert a BeautifulSoup element's contents to plain text."""
    result = u''
    
    for k in soup.contents:
        if isinstance(k, NavigableString):
            result += decode_html_entities(k)
        elif hasattr(k, 'name'):  # is another soup element
            if k.name == u'sup':
                result += u'^'
            
            result += textify_html(k)
    
    return result
