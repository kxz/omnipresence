import json
import re
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import urllib

from bs4 import BeautifulSoup, NavigableString
from twisted.internet import defer
from twisted.plugin import IPlugin
from twisted.python import log
from twisted.web.client import FileBodyProducer
from twisted.web.http_headers import Headers
from zope.interface import implements

from omnipresence import web
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


class TropeSearch(object):
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

        d = self.search(args[1])
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d

    def privmsg(self, bot, prefix, channel, message):
        dl = []
        for match in TROPE_LINK.finditer(message):
            title = match.group(1).strip()
            if title:
                log.msg('Saw TV Tropes link {{%s}} from %s in %s.'
                        % (title, prefix, channel))
                dl.append(defer.maybeDeferred(self.execute, bot, prefix, None,
                                              channel, '% ' + title))
        if dl:
            return defer.DeferredList(dl)

    action = privmsg

    @defer.inlineCallbacks
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
        preview_text = 'HomePage [=~%s~=] {{%s}}' % (title, plain_title)
        params = { 'source': preview_text }
        bp = FileBodyProducer(StringIO.StringIO(urllib.urlencode(params)))

        req_headers = Headers()
        req_headers.addRawHeader('Content-Type',
                                 'application/x-www-form-urlencoded')

        headers, content = yield web.request('POST',
                                   'http://tvtropes.org/pmwiki/preview.php',
                                   headers=req_headers, bodyProducer=bp)

        preview_soup = BeautifulSoup(content)
        # Discard the bogus HomePage link.
        preview_soup.find('a', 'twikilink').extract()
        while preview_soup.find('a', 'twikilink'):
            link = preview_soup.find('a', 'twikilink').extract()

            try:
                result = link['href']
            except KeyError:
                continue

            # [=~ ~=] searches for non-existent ptitles return a broken
            # link pointing to "ptitle" in the appropriate namespace
            # instead of simply failing like they should, so we skip
            # them.
            if result.rsplit('/', 1)[-1] == 'ptitle':
                continue

            # We've found our match.
            trope = yield self.get_summary(result.encode('utf8'), '')
            defer.returnValue(trope)

        # No results?  Try a full-text Google search.
        params = urllib.urlencode({'q': ('site:tvtropes.org inurl:pmwiki.php '
                                         '-"click the edit button" %s,')
                                          % title,
                                   'v': '1.0'})
        headers, content = yield web.request('GET',
                                   ('http://ajax.googleapis.com/ajax/'
                                    'services/search/web?' + params))

        data = json.loads(content)
        try:
            results = data['responseData']['results']
        except KeyError:
            results = []
        if not results:
            defer.returnValue(None)
        trope = yield self.get_summary(
                        results[0]['unescapedUrl'].encode('utf8'),
                        ' (full-text)')
        defer.returnValue(trope)

    @defer.inlineCallbacks
    def get_summary(self, url, info_text=''):
        headers, content = yield web.request('GET', url)
        soup = BeautifulSoup(content)
        title = web.textify_html(soup.find('title'))
        url = headers['X-Omni-Location']

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
                    text_content = unicode(node)
                else:
                    node_name = node.name
                    text_content = web.textify_html(node)

                if summary and node_name in BLOCK_HTML_ELEMENTS:
                    break

                if node_name not in BLOCK_HTML_ELEMENTS:
                    # Only add whitespace if we've already seen some
                    # other content.
                    if summary or text_content.strip():
                        summary += text_content

            # Reduce runs of whitespace to a single space.
            summary = ' '.join(summary.strip().split())

        defer.returnValue((title, url, summary, info_text))

    def reply(self, trope, bot, prefix, reply_target, channel, args):
        if not trope:
            bot.reply(prefix, channel, 'TV Tropes: No results found for '
                                       '\x02%s\x02.' % args[1])
            return

        title, url, summary, info_text = trope
        title, url = get_real_title_and_url(title, url)
        summary = u': ' + summary if summary else ''

        bot.reply(reply_target, channel,
                  u'TV Tropes{0}: {1} \u2014 \x02{2}\x02{3}'.format(
                    info_text, url, title, summary))


class RandomTrope(TropeSearch):
    """
    \x02%s\x02 - Get a random TV Tropes article.
    """
    name = 'tvtropes_random'

    def execute(self, bot, prefix, reply_target, channel, args):
        d = self.get_summary('http://tvtropes.org/pmwiki/randomitem.php',
                             ' (random)')
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d


default = TropeSearch()
random = RandomTrope()
