import json
import re
import urllib

from BeautifulSoup import BeautifulSoup, NavigableString
from twisted.internet import threads
from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence import html, util
from omnipresence.iomnipresence import ICommand, IHandler

TROPE_LINK = re.compile(r'{{(.*?)}}')
INVALID_TROPE_TITLE_CHARACTERS = re.compile(r'[^@A-Za-z0-9\-./ ]+')

# <img> is technically not a block-level element, but we include it here
# since it doesn't delineate text content in TV Tropes articles.
BLOCK_HTML_ELEMENTS = ['address', 'blockquote', 'center', 'dd', 'div',
                       'dl', 'dt', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr',
                       'img', 'li', 'ol', 'p', 'pre', 'script', 'ul']


def get_real_title_and_url(title, url):
    title = title.rsplit(' - ', 1)[0]
    (url, query) = urllib.splitquery(url)
    
    # If no page title was returned (which does happen quite often), use
    # the last component of the URL instead.
    if not title:
        title = url.rsplit('/', 1)[-1]
    
    return (title, url)


class TVTropesSearch(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search for a TV Tropes article with a 
    title matching the given search string, or perform a full-text search if 
    no such article exists.
    """
    implements(IPlugin, ICommand, IHandler)
    name = 'tvtropes'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)
        
        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return
        
        d = threads.deferToThread(self.search, args[1])
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d
    
    def privmsg(self, bot, prefix, channel, message):
        tropes = TROPE_LINK.findall(message)
        
        for match in tropes:
            match = match.strip()
            if match:
                d = threads.deferToThread(self.search, match)
                d.addCallback(self.reply, bot, prefix, None, channel, [match])
                return d
    
    action = privmsg
    
    def search(self, title):
        # Start off by trying to find a trope with the exact title.
        
        # Transform the requested page title for {{}} search.  First,
        # remove any characters invalid in plain trope titles, in order
        # to increase the likelihood of an exact match.  Second, force
        # the first character to uppercase; otherwise, an all-lowercase
        # query will lead to the markup not being parsed as a link.
        plain_title = INVALID_TROPE_TITLE_CHARACTERS.sub('', title)
        plain_title = plain_title[0].upper() + plain_title[1:]
        
        # Work around a TV Tropes bug (2011-03-31) that returns "blue"
        # existing article links instead of "red" nonexistent article
        # links, by adding the known extant article "HomePage" to the
        # beginning of the query.  When removing this workaround, make
        # sure to update the link loop below as well!
        preview_query = ('HomePage [=~%s~=] {{%s}}' % (title, plain_title))
        params = {'source': preview_query}
        
        response = self.factory.get_http('http://tvtropes.org/pmwiki/preview.php',
                                         'POST', body=urllib.urlencode(params),
                                         headers={'Content-type':
                                                  'application/x-www-form-urlencoded'},
                                         defer=False)
        preview_soup = BeautifulSoup(response[1])
        
        # Discard the bogus HomePage link.
        preview_soup.find('a', 'twikilink').extract()
        
        while preview_soup.find('a', 'twikilink'):
            link = preview_soup.find('a', 'twikilink').extract()
            
            try:
                result = link.attrMap['href']
            except KeyError:
                continue
            
            # [=~ ~=] searches for non-existent ptitles return a broken
            # link pointing to "ptitle" in the appropriate namespace
            # instead of simply failing like they should, so we skip
            # them.
            if result.rsplit('/', 1)[-1] == 'ptitle':
                continue
            
            # We've found our match.
            return self.get_summary(result, '')

        # No results?  Try a full-text Google search.        
        params = urllib.urlencode({'q': ('site:tvtropes.org inurl:pmwiki.php '
                                         '-"click the edit button" %s,')
                                          % title,
                                   'v': '1.0'})
        
        response = self.factory.get_http('http://ajax.googleapis.com/ajax/'
                                         'services/search/web?' + params,
                                         defer=False)
        data = json.loads(response[1])
        
        if ('responseData' not in data or
            'results' not in data['responseData'] or
            not data['responseData']['results']):
            return None
        
        result = data['responseData']['results'][0]
        return self.get_summary(result['unescapedUrl'], ' (full-text)')
    
    def get_summary(self, url, info_text=''):
        try:
            response = self.factory.get_http(url, defer=False)
        except:
            log.err(None, 'TV Tropes summary fetching failed.')
            return ('', url, None, info_text)
        
        soup = BeautifulSoup(response[1])
        title = html.textify_html(soup.find('title'))
        url = response[0]['content-location']
        
        # Summary generation.
        #
        # The HTML generated by TV Tropes is, not to put too fine a
        # point on it, stupid.  Instead of using <p> and </p> to wrap
        # paragraphs, or even just inserting an opening tag with no matching
        # matching closing tag, it puts a full <p></p> in between
        # paragraphs, meaning that any sane parser will see a bunch of
        # text content and inline-level HTML elements floating around
        # inside the content container.
        #
        # What we do here to get the first paragraph of text directly
        # under the container, then, is skip every single block-level
        # element we see, as well as any empty text nodes, then add the
        # text content of any following inline or text nodes until we
        # encounter another block-level element.
        summary = ''
        wikitext = soup.find('div', id='wikitext')
        
        if wikitext:
            for node in wikitext.contents:
                if isinstance(node, NavigableString):
                    node_name = '#text'
                    text_content = html.decode_html_entities(node)
                else:
                    node_name = node.name
                    text_content = html.textify_html(node)
                
                if summary and node_name in BLOCK_HTML_ELEMENTS:
                    break
                
                if node_name not in BLOCK_HTML_ELEMENTS:
                    # Only add whitespace if we've already seen some
                    # other content.
                    if summary or text_content.strip():
                        summary += text_content
            
            # Reduce runs of whitespace to a single space.
            summary = ' '.join(summary.strip().split())
            
            if len(summary) > 128:
                summary = summary[:128] + u'...'

        return (title, url, summary, info_text)
    
    def reply(self, trope, bot, prefix, reply_target, channel, args):
        if not trope:
            bot.reply(prefix, channel, 'TV Tropes: No results found for '
                                       '\x02%s\x02.' % args[1])
            return
        
        (title, url, summary, info_text) = trope
        (title, url) = get_real_title_and_url(title, url)
        summary = summary + u' \u2014 ' if summary else ''
        
        bot.reply(reply_target, channel, (u'TV Tropes%s: \x02%s\x02: %s%s'
                                            % (info_text, title,
                                               summary, url)) \
                                          .encode(self.factory.encoding))


class RandomTrope(TVTropesSearch):
    """
    \x02%s\x02 - Get a random TV Tropes article.
    """
    name = 'tvtropes_random'
    
    def execute(self, bot, prefix, reply_target, channel, args):
        d = threads.deferToThread(self.random)
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d
    
    def random(self):
        return self.get_summary('http://tvtropes.org/pmwiki/randomitem.php',
                                ' (random)')


tvtropes = TVTropesSearch()
tvtropes_random = RandomTrope()
