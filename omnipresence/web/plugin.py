"""Helpers for Omnipresence plugins that retrieve Web documents."""


import urllib

from twisted.plugin import IPlugin
from zope.interface import implements

from omnipresence.iomnipresence import ICommand


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
