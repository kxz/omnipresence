import itertools

import amazonproduct
import bitly_api
from twisted.internet import defer, threads
from twisted.plugin import IPlugin
from twisted.python import log
from zope.interface import implements

from omnipresence.iomnipresence import ICommand


class APIError(Exception):
    pass


class ProductSearch(object):
    """
    \x02%s\x02 \x1Fsearch_string\x1F - Search for Amazon.com products
    matching the given search string. (Full disclosure: This returns an
    affiliate link.)
    """
    implements(IPlugin, ICommand)
    name = 'amazon'

    def registered(self):
        self.amazon_api = amazonproduct.API(
            cfg=dict(self.factory.config.items('amazon')))
        self.bitly_api = bitly_api.Connection(
            access_token=self.factory.config.get('bitly', 'access_token'))

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)

        if len(args) < 2:
            bot.reply(prefix, channel, 'Please specify a search string.')
            return

        d = threads.deferToThread(self.search, args[1])
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d

    def search(self, keywords):
        try:
            products = list(itertools.islice(
                self.amazon_api.item_search(
                    'Blended', Keywords=keywords,
                    ResponseGroup='ItemAttributes,OfferSummary'),
                5))
        except amazonproduct.errors.AWSError as e:
            raise APIError('Amazon Product API encountered an error.')
        summaries = []
        for i, product in enumerate(products):
            # Shorten the URL.
            url = self.bitly_api.shorten(product.DetailPageURL.text)['url']
            # Name.
            name = u'\x02%s\x02' % product.ItemAttributes.Title.text
            if hasattr(product.ItemAttributes, 'Author'):
                name += u' by %s' % product.ItemAttributes.Author.text
            # Offer summary.
            offers = []
            for condition in ('new', 'used', 'collectible', 'refurbished'):
                total_tag = 'Total%s' % condition.capitalize()
                total = int(product.OfferSummary[total_tag].text)
                if total:
                    lowest_tag = 'Lowest%sPrice' % condition.capitalize()
                    offers.append(u'%d %s from %s' % (
                        total, condition,
                        product.OfferSummary[lowest_tag].FormattedPrice.text))
            offers = '; '.join(offers)
            summaries.append(u'Amazon: (%d/%d) %s \u2014 %s \u2014 %s' % (
                i+1, len(products), url, name, offers))
        return summaries

    def reply(self, summaries, bot, prefix, reply_target, channel, args):
        if not summaries:
            bot.reply(prefix, channel, ('Amazon: No results found for '
                                        '\x02%s\x02.' % args[1]))
            return
        bot.reply(reply_target, channel, u'\n'.join(summaries))


default = ProductSearch()
