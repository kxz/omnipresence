# -*- test-case-name: omnipresence.test.test_connection -*-
"""Core IRC connection protocol class and supporting machinery."""


import collections
import re

import sqlobject
from twisted.internet import reactor
from twisted.internet.defer import (
    DeferredList, inlineCallbacks, maybeDeferred)
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log
from twisted.python.failure import Failure
from twisted.words.protocols.irc import IRCClient

from . import __version__, __source__, mapping
from .message import Message, chunk
from .plugin import UserVisibleError


#: The maximum length of a single command reply, in bytes.
MAX_REPLY_LENGTH = 256

#: A sentinel "channel" used for direct messages to users.
PRIVATE_CHANNEL = '@'


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
        self.message_buffers = {PRIVATE_CHANNEL: {}}

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
        self.respond_to(Message(self, False, 'disconnected'))
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
        self.respond_to(Message(self, False, 'connected'))
        # Resetting the connection delay when a successful connection is
        # made, instead of at IRC sign-on, overlooks situations such as
        # host bans where the server accepts a connection and then
        # immediately disconnects the client.  In these cases, the delay
        # should continue to increase, especially if the problem is that
        # there are too many connections!
        self.factory.resetDelay()
        for channel in self.factory.config.options('channels'):
            # Skip over "@", which has a special meaning to the bot.
            if channel != PRIVATE_CHANNEL:
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
        self.message_buffers = {PRIVATE_CHANNEL: {}}

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

    def add_event_plugin(self, plugin_class, channels):
        """Attach a new instance of *plugin_class* to this connection
        and return it.  *channels* is a dict mapping channel names to
        lists of command keywords to assign to the new plugin."""
        plugin = plugin_class(self)
        for channel, keywords in channels.iteritems():
            self.event_plugins.setdefault(channel, [])
            self.event_plugins[channel].append((plugin, keywords))
        return plugin

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
            if msg.venue:
                venues = [msg.venue]
            else:
                # If there is an actor, forward the message only to
                # plugins enabled in at least one channel where the
                # actor was present.  Otherwise, forward it to every
                # plugin active on the connection.
                if msg.actor:
                    venues = [channel for channel, names
                              in self.channel_names.iteritems()
                              if msg.actor.nick in names]
                else:
                    venues = self.event_plugins.keys()
            plugins = set()
            for venue in venues:
                for plugin, keywords in self.event_plugins.get(venue, []):
                    if (msg.action == 'command' and
                            msg.subaction not in keywords):
                        continue
                    plugins.add(plugin)
            for plugin in plugins:
                deferred = maybeDeferred(plugin.respond_to, msg)
                if msg.action == 'command':
                    deferred.addCallback(self.buffer_reply, msg)
                    deferred.addCallback(self.reply_from_buffer, msg)
                    deferred.addErrback(self.reply_error, msg)
                else:
                    deferred.addErrback(log.err,
                        'Error in plugin %s responding to %s' %
                        (plugin.__class__.name, msg))
                deferreds.append(deferred)
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

    def buffer_reply(self, response, request):
        """Add the :ref:`command reply <command-replies>` *response* to
        the appropriate user's reply buffer according to the invocation
        :py:class:`~.Message` *request*."""
        buf_venue = PRIVATE_CHANNEL if request.private else request.venue
        if not response:
            self.message_buffers[buf_venue].pop(request.actor.nick, None)
            return
        if isinstance(response, basestring):
            buf = chunk(response, self.factory.encoding, MAX_REPLY_LENGTH)
        elif isinstance(response, collections.Iterable):
            buf = response
        else:
            raise TypeError('invalid command reply type ' +
                            type(response).__name__)
        self.message_buffers[buf_venue][request.actor.nick] = buf
        return request.actor.nick

    @inlineCallbacks
    def reply_from_buffer(self, nick, request, reply_when_empty=False):
        """Send the next reply from the reply buffer belonging to *nick*
        in the :py:attr:`~.Message.venue` venue of the invocation
        :py:class:`~.Message` *request*.  If the request venue is a
        channel, send the reply to the venue as a standard message
        addressed to *request*'s :py:attr:`~.Message.target`.
        Otherwise, send the reply as a private notice to *request*'s
        :py:attr:`~.Message.actor`."""
        buf = self.message_buffers[request.venue].get(nick, [])
        message = None
        remaining_chars = None
        if isinstance(buf, collections.Sequence):
            if buf:
                message = buf.pop(0)
                remaining_chars = sum(map(len, buf))
        else:  # assume an iterator
            try:
                message = yield next(buf)
            except StopIteration:
                pass
            except Exception:
                self.reply_error(Failure(), request)
                return
        if not (message or reply_when_empty):
            return
        if message is None:
            message = 'No text in buffer.'
        message = message.replace('\n', ' / ')
        if remaining_chars:
            message += ' (+{} more characters)'.format(remaining_chars)
        if request.private:
            log.msg('Private reply for %s: %s' % (nick, message))
            self.notice(nick, message)
        else:
            log.msg('Reply for %s in %s: %s' %
                    (request.target, request.venue, message))
            # TODO:  Make the format configurable.
            message = '\x0314{}: {}'.format(request.target, message)
            self.msg(request.venue, message)

    def reply_error(self, failure, request):
        """Call :py:meth:`reply` with information on a *failure* that
        occurred in the callback invoked to handle a command request. If
        *failure* wraps a :py:class:`~.UserVisibleError`, reply with its
        exception string.  Otherwise, log the error and reply with a
        generic message. If the ``show_errors`` configuration option is
        true, reply with the exception string regardless of *failure*'s
        exception type.

        This method is automatically called whenever an unhandled
        exception occurs in a plugin's command callback, and should
        never need to be invoked manually.
        """
        # TODO:  Implement `show_errors`.
        error_request = request._replace(target=request.actor.nick)
        message = 'Command \x02{}\x02 encountered an error'.format(
            request.subaction)
        if failure.check(UserVisibleError):
            self.buffer_reply(
                '{}: {}.'.format(message, failure.getErrorMessage()),
                error_request)
            self.reply_from_buffer(request.actor.nick, error_request)
            return
        log.err(failure, 'Error during command callback: %s %s' %
                (request.subaction, request.content))
        self.buffer_reply(message + '.', error_request)
        self.reply_from_buffer(request.actor.nick, error_request)

    # Overrides IRCClient.lineReceived.
    def lineReceived(self, line):
        deferred = self.respond_to(Message.from_raw(self, False, line))
        IRCClient.lineReceived(self, line)
        return deferred

    # Overrides IRCClient.sendLine.
    def sendLine(self, line):
        deferred = self.respond_to(Message.from_raw(
            self, True, line, actor=self.nickname))
        IRCClient.sendLine(self, line)
        return deferred


class ConnectionFactory(ReconnectingClientFactory):
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
