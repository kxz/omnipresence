# -*- test-case-name: omnipresence.test.test_web -*-
"""Utility methods for retrieving and manipulating data from Web resources."""

import sys
import urllib
from urlparse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag
import ipaddress
from twisted.internet import defer, reactor
from twisted.plugin import IPlugin
from twisted.web.client import (IAgent, Agent, ContentDecoderAgent,
                                RedirectAgent, GzipDecoder, readBody)
from twisted.web.http_headers import Headers
from zope.interface import implements

from omnipresence import VERSION_NUM, SOURCE_URL
from omnipresence.iomnipresence import ICommand


USER_AGENT = 'Omnipresence/{} (+bot; {})'.format(VERSION_NUM, SOURCE_URL)


#
# HTTP request machinery
#

default_agent = ContentDecoderAgent(RedirectAgent(Agent(reactor)),
                                    [('gzip', GzipDecoder)])


@defer.inlineCallbacks
def request(*args, **kwargs):
    """Make an HTTP request, and return a Deferred that will yield an
    httplib2-style ``(headers, content)`` tuple to its callback.

    Arguments are as for a request to a typical Twisted Web agent, with
    the addition of one keyword argument, *max_bytes*, that specifies
    the maximum number of bytes to fetch from the desired resource.  If
    no ``User-Agent`` header is specified, one is added before making
    the request.

    Two custom headers are returned in the response, in addition to any
    set by the HTTP server:  ``X-Omni-Location`` contains the final
    location of the request resource after following all redirects, and
    ``X-Omni-Length`` contains the original value of the response's
    ``Content-Length`` header, which Twisted may overwrite if the actual
    response exceeds *max_bytes* in size."""
    kwargs.setdefault('headers', Headers())
    if not kwargs['headers'].hasHeader('User-Agent'):
        kwargs['headers'].addRawHeader('User-Agent', USER_AGENT)
    agent = kwargs.pop('agent', None) or default_agent
    response = yield agent.request(*args, **kwargs)
    headers = dict((k, v[0]) for k, v in response.headers.getAllRawHeaders())
    # Add the ultimately requested URL as a custom X-header.
    headers['X-Omni-Location'] = response.request.absoluteURI
    # Calling deliverBody causes the response's Content-Length header to
    # be overwritten with how much of the body was actually delivered.
    # In some cases, the original value is needed, so we store it in a
    # custom X-header field.
    headers['X-Omni-Length'] = str(response.length)
    d = defer.Deferred()
    try:
        content = yield readBody(response)
    except PartialDownloadError as e:
        content = e.response
    defer.returnValue((headers, content))


#
# HTML handling methods
#

def decode_html_entities(s):
    """Convert HTML entities in a string to their Unicode character
    equivalents.  This method is equivalent to::

        textify_html(s, format_output=False)

    .. deprecated:: 2.2
       Use :py:func:`textify_html` instead.
    """
    return textify_html(s, format_output=False)


def textify_html(html, format_output=True):
    """Convert the contents of *html* to a Unicode string.  *html* can
    be either a string containing HTML markup, or a Beautiful Soup tag
    object.  If *format_output* is ``True``, IRC formatting codes are
    added to simulate common element styles."""
    if isinstance(html, BeautifulSoup) or isinstance(html, Tag):
        soup = html
    else:
        soup = BeautifulSoup(html)

    def handle_soup(soup, format_output):
        if format_output:
            # Grab the node's tag name, and change the format if necessary.
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
                    contents += handle_soup(k, format_output)
            return fmt.format(contents)
        else:
            return u''.join(soup.strings)

    # Don't strip whitespace until the very end, in order to avoid
    # misparsing constructs like <span>hello<b> world</b></span>.
    return u' '.join(handle_soup(soup, format_output).split()).strip()


#
# Plugin utility classes
#

class WebCommand(object):
    """A utility class for writing command plugins that make a single
    HTTP GET request and do something with the response.

    Subclasses should define a :py:attr:`url` property containing the
    string ``%s``, and implement the :py:meth:`.reply` method.  When the
    command is invoked, ``%s`` is substituted with the command's literal
    argument string, and a deferred request to the resulting URL is made
    with :py:meth:`.reply` as its success callback.

    An optional property :py:attr:`arg_type` can be used to indicate the
    type of argument that your custom command expects.  This is used to
    provide a usage message should no arguments be given; for example,
    setting :py:attr:`arg_type` to ``'a search term'`` sets the usage
    message to "Please specify a search term."  The default value is
    ``'an argument string'``.
    """
    implements(IPlugin, ICommand)
    arg_type = 'an argument string'
    url = None

    def execute(self, bot, prefix, reply_target, channel, args):
        args = args.split(None, 1)

        if len(args) < 2:
            bot.reply(prefix, channel,
                      'Please specify {0}.'.format(self.arg_type))
            return

        if self.url is None:
            raise NotImplementedError('no URL provided for WebCommand')

        d = request('GET', self.url % urllib.quote(args[1]))
        d.addCallback(self.reply, bot, prefix, reply_target, channel, args)
        return d

    def reply(self, response, bot, prefix, reply_target, channel, args):
        """Implement this method in your command subclass.  The
        *response* argument will contain a ``(headers, content)``
        response tuple as returned by
        :py:func:`~omnipresence.web.request`.  The other arguments are
        as passed in to :py:meth:`ICommand.execute`.
        """
        raise NotImplementedError('no reply method provided for WebCommand')
