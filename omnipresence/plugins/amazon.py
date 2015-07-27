import itertools

import amazonproduct
import bitly_api
from twisted.internet import threads
from twisted.plugin import IPlugin
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

        d = threads.deferToThread(self.search,
                                  args[1].decode(self.factory.encoding))
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
            # If there's no detail page (which happens sometimes), just
            # skip the product in question.
            if not hasattr(product, 'DetailPageURL'):
                continue
            # Shorten the URL.
            url = self.bitly_api.shorten(product.DetailPageURL.text)['url']
            # Name.
            name = u'\x02%s\x02' % product.ItemAttributes.Title.text
            if hasattr(product.ItemAttributes, 'Binding'):
                name += u' (%s)' % product.ItemAttributes.Binding.text
            if hasattr(product.ItemAttributes, 'Author'):
                name += u' by %s' % product.ItemAttributes.Author.text
            elif hasattr(product.ItemAttributes, 'Artist'):
                name += u' by %s' % product.ItemAttributes.Artist.text
            # Offer summary.
            if hasattr(product, 'OfferSummary'):
                offers = []
                for condition in ('new', 'used', 'collectible', 'refurbished'):
                    total_tag = 'Total%s' % condition.capitalize()
                    total = int(product.OfferSummary[total_tag].text)
                    if not total:
                        continue
                    lowest_tag = 'Lowest%sPrice' % condition.capitalize()
                    offers.append(u'%d %s from %s' % (
                        total, condition,
                        product.OfferSummary[lowest_tag].FormattedPrice.text))
                offers = '; '.join(offers)
            else:
                offers = u''
            if offers:
                offers = u' \u2014 %s' % offers
            summaries.append(u'%s \u2014 %s%s' % (url, name, offers))
        return summaries

    def reply(self, summaries, bot, prefix, reply_target, channel, args):
        if not summaries:
            bot.reply(prefix, channel, ('No results found for '
                                        '\x02%s\x02.' % args[1]))
            return
        bot.reply(reply_target, channel, u'\n'.join(summaries))


default = ProductSearch()
