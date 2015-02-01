# -*- test-case-name: omnipresence.test.test_connection -*-
"""Core IRC connection protocol class and supporting machinery."""


import re

import sqlobject
from twisted.internet import defer, protocol, reactor, task, threads
from twisted.internet.defer import DeferredList
from twisted.python import failure, log
from twisted.words.protocols.irc import IRCClient, CHANNEL_PREFIXES

from . import __version__, __source__, mapping, plugins, ircutil
from .message import Message, truncate_unicode


#: The maximum length of a single command reply, in bytes.
MAX_REPLY_LENGTH = 256


class Connection(IRCClient):
    """Omnipresence's core IRC client protocol."""

    # Instance variables handled by IRCClient.
    versionName = 'Omnipresence'
    versionNum = __version__
    sourceURL = __source__

    #: The maximum acceptable lag, in seconds.  If this amount of time
    #: elapses following a PING from the client with no PONG response
    #: from the server, the connection has timed out.  (The timeout
    #: check only occurs at every :py:attr:`~.heartbeatInterval`, so
    #: actual disconnection intervals may vary by up to one heartbeat.)
    max_lag = 150

    #: The number of seconds to wait between sending successive PINGs
    #: to the server.  This overrides a class variable in Twisted's
    #: implementation, hence the unusual capitalization.
    heartbeatInterval = 60

    def __init__(self, factory):
        #: The :py:class:`ConnectionFactory` that created this client.
        self.factory = factory

        # Various instance variables provided by Twisted's IRCClient.
        self.nickname = factory.config.getdefault('core', 'nickname',
                                                  default=self.versionName)
        self.password = factory.config.getdefault('core', 'password')
        self.realname = factory.config.getdefault('core', 'realname')
        self.username = factory.config.getdefault('core', 'username')
        self.userinfo = factory.config.getdefault('core', 'userinfo')

        #: The reactor in use on this client.  This may be overridden
        #: when a deterministic clock is needed, such as in unit tests.
        self.reactor = reactor

        #: The time of the last PONG seen from the server.
        self.last_pong = None

        #: An :py:class:`~twisted.internet.interfaces.IDelayedCall` used
        #: to detect timeouts that occur after connecting to the server,
        #: but before receiving the ``RPL_WELCOME`` message that starts
        #: the normal PING heartbeat.
        self.signon_timeout = None

        log.msg('Assuming default CASEMAPPING "rfc1459"')
        #: The case mapping currently in effect on this connection.
        self.case_mapping = mapping.by_name('rfc1459')

        #: A mapping of channels to the set of nicks present in each
        #: channel.
        self.channel_names = {}

        #: A mapping of channels to a mapping containing message buffers
        #: for each channel, keyed by nick.
        self.message_buffers = {'@': {}}

        # See self.add_event_plugin().
        self.event_plugins = self._case_mapped_dict()

        #: If the bot is currently firing callbacks, a queue of
        #: :py:class:`.Message` objects for which the bot has yet to
        #: fire callbacks.  Otherwise, :py:data:`None`.
        self.message_queue = None

        #: If joins are suspended, a set containing the channels to join
        #: when joins are resumed.  Otherwise, :py:data:`None`.
        self.suspended_joins = None

    # Utility methods

    def _case_mapped_dict(self, initial=None):
        """Return a :py:class:`~.CaseMappedDict` using this connection's
        current case mapping."""
        return mapping.CaseMappedDict(initial, case_mapping=self.case_mapping)

    def _lower(self, string):
        """Convenience alias for ``self.case_mapping.lower``."""
        return self.case_mapping.lower(string)

    def _upper(self, string):
        """Convenience alias for ``self.case_mapping.upper``."""
        return self.case_mapping.upper(string)

    def is_channel(self, name):
        """Return True if *name* belongs to a channel, according to the
        server-provided list of channel prefixes, or False otherwise.
        """
        # We can assume the CHANTYPES feature will always be present,
        # since Twisted gives it a default value.
        return name[0] in self.supported.getFeature('CHANTYPES')

    def suspend_joins(self):
        """Suspend all channel joins until :py:meth:`resume_joins` is
        called."""
        # If suspended_joins is not None, then we've already suspended
        # joins for this client, and we shouldn't clobber the queue.
        if self.suspended_joins is not None:
            return
        log.msg('Suspending channel joins')
        self.suspended_joins = []

    def resume_joins(self):
        """Resume immediate joining of channels after suspending it with
        :py:meth:`suspend_joins`, and perform any channel joins that
        have been queued in the interim."""
        if self.suspended_joins is None:
            return
        log.msg('Resuming channel joins')
        suspended_joins = self.suspended_joins
        self.suspended_joins = None
        for channel in suspended_joins:
            self.join(channel)

    def reply(self, prefix, channel, message):
        """Send a reply to a user.  The method used depends on the
        values of *prefix* and *channel*:

        * If *prefix* is specified and *channel* starts with an IRC
          channel prefix (such as ``#`` or ``+``), send the reply
          publicly to the given channel, addressed to the nickname
          specified by *prefix*.
        * If *prefix* is specified and *channel* is the bot's nickname,
          send the reply as a private notice to the nickname specified
          by *prefix*.
        * If *prefix* is not specified, send the reply publicly to the
          channel given by *channel*, with no nickname addressing.

        Long replies are buffered in order to satisfy protocol message
        length limits; a maximum of 256 characters will be sent at any
        given time.  Further content from a buffered reply can be
        retrieved by using the command provided with the `more` plugin.

        When possible, Omnipresence attempts to truncate replies on
        whitespace, instead of in the middle of a word.  Replies are
        _always_ broken on newlines, which can be useful for creating
        commands that progressively give more information.
        """
        # FIXME:  Unify this with message.chunk.  In particular, note
        # how newlines are handled specially in this implementation.
        #
        # _Always_ split on a newline.
        to_send, sep, to_buffer = message.partition('\n')
        if isinstance(to_send, unicode):
            truncated = truncate_unicode(
                to_send, MAX_REPLY_LENGTH, self.factory.encoding)
            if truncated.decode(self.factory.encoding) != to_send:
                # Try and find whitespace to split the message on.
                truncated = truncated.rsplit(None, 1)[0]
                to_buffer = to_send[len(truncated.decode(self.factory.encoding)):] + \
                            sep + to_buffer
        else:
            truncated = to_send[:MAX_REPLY_LENGTH]
            if truncated != to_send:
                # Try and find whitespace to split the message on.
                truncated = truncated.rsplit(None, 1)[0]
                to_buffer = to_send[len(truncated):] + sep + to_buffer
        message = ircutil.close_formatting_codes(truncated).strip()
        to_buffer = ''.join(ircutil.unclosed_formatting_codes(truncated)) + \
                    to_buffer.strip()
        if prefix:
            nick = prefix.split('!', 1)[0].strip()
            if to_buffer:
                message += ' (+%d more characters)' % len(to_buffer)
            log.msg('Reply for %s on channel %s: %s'
                     % (nick, channel, message))

            if channel == self.nickname:
                self.message_buffers['@'][nick] = to_buffer
                self.notice(nick, message)
                return

            self.message_buffers[channel][nick] = to_buffer
            message = '%s: %s' % (nick, message)
        else:
            if to_buffer:
                message += u'\u2026'.encode(self.factory.encoding)
            log.msg('Undirected reply for channel %s: %s' % (channel, message))

        self.msg(channel, '\x0314%s' % message)

    def reply_with_error(self, failure, prefix, channel, keyword):
        """Call :py:meth:`reply` with information on an error that
        occurred during an invocation of the command with the given
        *keyword*.  *failure* should be an instance of
        :py:class:`twisted.python.failure.Failure`.

        .. note:: This method is automatically called whenever an
           unhandled exception occurs in a command's
           :py:meth:`~omnipresence.iomnipresence.ICommand.execute`
           method, and usually does not need to be invoked manually.
        """
        self.reply(prefix, channel, 'Command \x02%s\x02 encountered an error: '
                                    '%s.' % (keyword,
                                             failure.getErrorMessage()))
        log.err(failure, 'Command "%s" encountered an error.' % keyword)

    # Connection maintenance

    def connectionMade(self):
        """Called when a connection has been successfully made to the
        IRC server."""
        log.msg('Connected to server')
        IRCClient.connectionMade(self)
        self.signon_timeout = self.reactor.callLater(
            self.max_lag, self.signon_timed_out)

    def signon_timed_out(self):
        """Called when a timeout occurs after connecting to the server,
        but before receiving the ``RPL_WELCOME`` message that starts the
        normal PING heartbeat."""
        log.msg('Sign-on timeout (%d seconds); disconnecting' % self.max_lag)
        self.transport.abortConnection()

    def _createHeartbeat(self):
        heartbeat = IRCClient._createHeartbeat(self)
        heartbeat.clock = self.reactor
        return heartbeat

    def _sendHeartbeat(self):
        lag = self.reactor.seconds() - self.last_pong
        if lag > self.max_lag:
            log.msg('Ping timeout (%d > %d seconds); disconnecting' %
                    (lag, self.max_lag))
            self.transport.abortConnection()
            return
        IRCClient._sendHeartbeat(self)

    def startHeartbeat(self):
        self.last_pong = self.reactor.seconds()
        IRCClient.startHeartbeat(self)

    def connectionLost(self, reason):
        """Called when the connection to the IRC server has been lost
        or disconnected."""
        log.msg('Disconnected from server')
        IRCClient.connectionLost(self, reason)

    # Callbacks inherited from IRCClient

    def isupport(self, options):
        """Called when the server sends information about supported
        features."""
        # Update the connection case mapping if one is available.
        case_mappings = self.supported.getFeature('CASEMAPPING')
        if case_mappings:
            name = case_mappings[0]
            try:
                self.case_mapping = mapping.by_name(name)
            except ValueError:
                log.msg('Ignoring unsupported server CASEMAPPING "%s"' % name)
            else:
                log.msg('Using server-provided CASEMAPPING "%s"' % name)
                self.event_plugins = self._case_mapped_dict(
                    self.event_plugins.items())

    def privmsg(self, prefix, channel, message):
        """Called when we receive a message from another user."""
        if not self.is_channel(channel):
            log.msg('Message from %s for %s: %s' % (prefix, channel, message))

    def joined(self, channel):
        """Called when the bot successfully joins the given *channel*."""
        log.msg('Successfully joined %s' % channel)
        self.channel_names[channel] = set()
        self.message_buffers[channel] = {}

    def left(self, channel):
        """Called when the bot leaves the given *channel*."""
        log.msg('Leaving %s' % channel)
        del self.channel_names[channel]
        del self.message_buffers[channel]

    def noticed(self, prefix, channel, message):
        """Called when we receive a notice from another user.  Behaves
        largely the same as :py:meth:`privmsg`."""
        if not self.is_channel(channel):
            log.msg('Notice from %s for %s: %s' % (prefix, channel, message))

    def signedOn(self):
        """Called after successfully signing on to the server."""
        log.msg('Successfully signed on to server.')
        if self.signon_timeout:
            self.signon_timeout.cancel()
        # Resetting the connection delay when a successful connection is
        # made, instead of at IRC sign-on, overlooks situations such as
        # host bans where the server accepts a connection and then
        # immediately disconnects the client.  In these cases, the delay
        # should continue to increase, especially if the problem is that
        # there are too many connections!
        self.factory.resetDelay()
        for channel in self.factory.config.options('channels'):
            # Skip over "@", which has a special meaning to the bot.
            if channel != '@':
                self.join(channel)

    def kickedFrom(self, channel, kicker, message):
        """Called when the bot is kicked from the given *channel*."""
        log.msg('Kicked from %s by %s: %s' % (channel, kicker, message))
        del self.channel_names[channel]
        del self.message_buffers[channel]

    def userJoined(self, prefix, channel):
        """Called when another user joins the given *channel*."""
        self.channel_names[channel].add(prefix.split('!', 1)[0])

    def userLeft(self, prefix, channel):
        """Called when another user leaves the given *channel*."""
        nick = prefix.split('!', 1)[0]
        self.channel_names[channel].discard(nick)
        self.message_buffers[channel].pop(nick, None)

    def userQuit(self, nick, quitMessage):
        """Called when another user has quit the IRC server."""
        for channel in self.channel_names:
            self.channel_names[channel].discard(nick)
            self.message_buffers[channel].pop(nick, None)

    def userKicked(self, kickee, channel, kicker, message):
        """Called when another user kicks a third party from the given
        *channel*."""
        self.channel_names[channel].discard(kickee)
        self.message_buffers[channel].pop(kickee, None)

    def userRenamed(self, oldname, newname):
        """Called when another user changes nick."""
        for channel in self.channel_names:
            if oldname in self.channel_names[channel]:
                self.channel_names[channel].discard(oldname)
                self.channel_names[channel].add(newname)
        for channel in self.message_buffers:
            if oldname in self.message_buffers[channel]:
                self.message_buffers[channel][newname] = (
                    self.message_buffers[channel].pop(oldname))

    def join(self, channel):
        """Join the given *channel*.  If joins have been suspended with
        :py:meth:`suspend_joins`, add the channel to the join queue and
        actually join it when :py:meth:`resume_joins` is called."""
        # If joins are suspended, add this one to the queue; otherwise,
        # just go ahead and join the channel immediately.
        if self.suspended_joins is not None:
            log.msg('Adding %s to join queue' % channel)
            self.suspended_joins.append(channel)
            return
        log.msg('Joining %s' % channel)
        IRCClient.join(self, channel)

    def kick(self, channel, nick, reason=None):
        """Kick the the given *nick* from the given *channel*."""
        IRCClient.kick(self, channel, nick, reason)
        self.channel_names[channel].discard(nick)
        self.message_buffers[channel].pop(nick, None)

    def setNick(self, nickname):
        """Change the bot's nickname."""
        oldnick = self.nickname
        IRCClient.setNick(self, nickname)
        for channel in self.channel_names:
            if oldnick in self.channel_names[channel]:  # sanity check
                self.channel_names[channel].discard(oldnick)
                self.channel_names[channel].add(nickname)
        for channel in self.message_buffers:
            # We should never have a buffer for ourselves.
            self.message_buffers[channel].pop(oldnick, None)

    def quit(self, message=''):
        """Quit from the IRC server."""
        IRCClient.quit(self, message)
        self.channel_names = {}
        self.message_buffers = {'@': {}}

    # IRC methods not defined by IRCClient

    def irc_PONG(self, prefix, secs):
        self.last_pong = self.reactor.seconds()

    def irc_RPL_NAMREPLY(self, prefix, params):
        channel = params[2]
        names = params[3].split()
        self.namesArrived(channel, names)

    def namesArrived(self, channel, names):
        # Liberally strip out all user mode prefixes such as @%+.  Some
        # networks support more prefixes, so this removes any prefixes
        # with characters not valid in nicknames.
        names = map(lambda x: re.sub(r'^[^A-Za-z0-9\-\[\]\\`^{}]+', '', x),
                    names)
        self.channel_names[channel].update(names)

    # Temporary shadow implementation of event plugins.

    def add_event_plugin(self, plugin, channels):
        """Register an event plugin.  *channels* is a dict mapping
        channel names to lists of keywords."""
        for channel, keywords in channels.iteritems():
            self.event_plugins.setdefault(channel, [])
            self.event_plugins[channel].append((plugin, keywords))
        plugin.respond_to(Message(self, False, 'registration'))

    def respond_to(self, msg):
        """Start the appropriate event plugin callbacks for *msg*, and
        return a :py:class:`twisted.internet.defer.DeferredList`."""
        if self.message_queue is not None:
            # We're already firing callbacks.  Bail.
            self.message_queue.append(msg)
            return
        self.message_queue = [msg]
        deferreds = []
        while self.message_queue:
            msg = self.message_queue.pop(0)
            if msg.action in ('nick', 'quit'):
                # Forward nick changes and quits only to plugins enabled
                # in at least one channel where the actor was present.
                venues = [channel for channel, names
                          in self.channel_names.iteritems()
                          if msg.actor.nick in names]
            else:
                venues = [msg.venue]
            plugins = set()
            for venue in venues:
                for plugin, keywords in self.event_plugins.get(venue, []):
                    if (msg.action == 'command' and
                            msg.subaction not in keywords):
                        continue
                    plugins.add(plugin)
            for plugin in plugins:
                deferreds.append(plugin.respond_to(msg))
            # Extract any command invocations and fire events for them.
            if msg.private:
                command_prefixes = None
            else:
                defaults = {'current_nickname': self.nickname}
                command_prefixes = self.factory.config.getspacelist(
                    'core', 'command_prefixes', False, defaults)
            command_msg = msg.extract_command(prefixes=command_prefixes)
            if command_msg is not None:
                # Get the command message in immediately after the
                # current privmsg, as they come from the same event.
                self.message_queue.insert(0, command_msg)
        self.message_queue = None
        return DeferredList(deferreds)

    # Overrides IRCClient.lineReceived.
    def lineReceived(self, line):
        self.respond_to(Message.from_raw(self, False, line))
        IRCClient.lineReceived(self, line)

    # Overrides IRCClient.sendLine.
    def sendLine(self, line):
        self.respond_to(Message.from_raw(
            # Fake a prefix for the message parser's convenience.
            self, True, ':{} {}'.format(self.nickname, line)))
        IRCClient.sendLine(self, line)


class ConnectionFactory(protocol.ReconnectingClientFactory):
    """Creates :py:class:`.Connection` instances."""
    protocol = Connection

    encoding = 'utf-8'

    def __init__(self, config):
        self.config = config
        self.encoding = self.config.getdefault('core', 'encoding',
                                               self.encoding)

        # Set up the bot's SQLObject connection instance.
        sqlobject_uri = self.config.get('core', 'database')
        sqlobject.sqlhub.processConnection = (
            sqlobject.connectionForURI(sqlobject_uri))

    def startedConnecting(self, connector):
        log.msg('Attempting to connect to server')

    def buildProtocol(self, addr):
        return self.protocol(self)
