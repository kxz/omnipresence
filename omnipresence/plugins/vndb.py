import urlparse

from bs4 import BeautifulSoup

from omnipresence.web import textify_html as txt, WebCommand


class VisualNovelSearch(WebCommand):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search for a visual novel with
    the given name on VNDB <http://vndb.org/>.
    """
    name = 'vndb'
    arg_type = 'a search query'
    url = 'http://vndb.org/v/all?s=pop&o=d&q=%s'  # popularity, descending

    def reply(self, response, bot, prefix, reply_target, channel, args):
        url = response[0]['X-Omni-Location']
        soup = BeautifulSoup(response[1])
        vnbrowse = soup.find('div', 'vnbrowse')
        results = []

        # Either zero results, or more than one result.
        if vnbrowse:
            # Don't recurse into children, to avoid picking up the row
            # contained within the <thead> element.
            for row in vnbrowse.table('tr', recursive=False):
                row_data = row('td')
                vn = { 'url': urlparse.urljoin(url, row_data[0].a['href']),
                       'title': txt(row_data[0].a),
                       'release_date': txt(row_data[3]) }
                alt_title = row_data[0].a['title']
                if alt_title != vn['title']:
                    vn['alt_title'] = alt_title
                rating = txt(row_data[5], format_output=False)
                if not rating.startswith(u'0.00'):
                    vn['rating'] = rating
                results.append(vn)
        # Single result, redirecting to an individual visual novel page.
        else:
            data = soup.find('div', id='maincontent')
            vn = { 'url': url,
                   'title': txt(data.find('h1')),
                   'release_date': txt(data.find('td', 'tc1')) }
            alt_title = data.find('h2', 'alttitle')
            if alt_title:
                vn['alt_title'] = txt(alt_title)
            votestats = data.find('div', 'votestats')
            if votestats:
                rating = txt(votestats('p')[-1])
                rating = rating.rsplit(None, 1)[-1]
                votes = txt(votestats.tfoot.find('td', colspan='2'))
                votes = votes.split(None, 1)[0]
                vn['rating'] = u'{0} ({1})'.format(rating, votes)
            results.append(vn)

        if not results:
            bot.reply(prefix, channel, 'VNDB: No results found for '
                                       '\x02%s\x02.' % args[1])
            return

        messages = []
        for i, vn in enumerate(results):
            message = u'VNDB ({0}/{1}): \x02{2}\x02'.format(
                        i + 1, len(results), vn['title'])
            if 'alt_title' in vn:
                message += u' (\x02{0}\x02)'.format(vn['alt_title'])
            if vn['release_date'] != u'TBA':
                message += u', first release ' + vn['release_date']
            if 'rating' in vn:
                message += u' \u2014 rated ' + vn['rating']
            message += u' \u2014 ' + vn['url']
            messages.append(message)

        bot.reply(reply_target, channel, u'\n'.join(messages))


vndb = VisualNovelSearch()
