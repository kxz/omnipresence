# -*- test-case-name: omnipresence.test.test_connection -*-
"""Core IRC connection protocol class and supporting machinery."""


import re
from weakref import WeakSet

from twisted.internet import reactor
from twisted.internet.defer import (DeferredList, maybeDeferred,
                                    inlineCallbacks, returnValue)
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.logger import Logger
from twisted.words.protocols.irc import IRCClient

from . import __version__, __source__, mapping
from .compat import length_hint
from .message import Message, ReplyBuffer, truncate_unicode
from .plugin import UserVisibleError
from .settings import ConnectionSettings, PRIVATE_CHANNEL


#: The maximum length of a single command reply, in bytes.
MAX_REPLY_LENGTH = 288


#
# State tracking classes
#

class UserInfo(object):
    """A container for information about an IRC user."""

    def __init__(self):
        #: This user's full hostmask.
        self.hostmask = None

        #: This user's services account name.
        self.account = None


class ChannelInfo(object):
    """A container for information about an IRC channel."""

    def __init__(self, case_mapping=None):
        #: A dictionary of modes in effect on this channel.  Keys are
        #: single-letter flags.  Values may be `None`, a string for
        #: single-parameter modes like ``l`` (limit), or a set of
        #: strings for address modes like ``o`` (channel operator).
        self.modes = {}

        #: A dictionary mapping nicks to `.ChannelUserInfo` objects.
        self.nicks = mapping.CaseMappedDict(case_mapping=case_mapping)

        #: This channel's topic, or the empty string if none is set.
        self.topic = ''


class ChannelUserInfo(object):
    """A container for information about a user's state in a particular
    IRC channel."""

    def __init__(self):
        #: The set of channel mode flags currently applied to this user.
        self.modes = set()

        #: This user's current channel reply buffer.
        self.reply_buffer = []


#
# Connection protocol
#

class Connection(IRCClient, object):
    """Omnipresence's core IRC client protocol."""

    log = Logger()

    # Instance variables handled by IRCClient.
    versionName = 'Omnipresence'
    versionNum = __version__
    sourceURL = __source__

    #: The maximum acceptable lag, in seconds.  If this amount of time
    #: elapses following a PING from the client with no PONG response
    #: from the server, the connection has timed out.  (The timeout
    #: check only occurs at every `.heartbeatInterval`, so actual
    #: disconnection intervals may vary by up to one heartbeat.)
    max_lag = 150

    #: The number of seconds to wait between sending successive PINGs
    #: to the server.  This overrides a class variable in Twisted's
    #: implementation, hence the unusual capitalization.
    heartbeatInterval = 60

    def __init__(self):
        #: The `.ConnectionFactory` that created this client, if any.
        self.factory = None

        #: The settings in use on this client.
        self.settings = ConnectionSettings()
        self.nickname = self.versionName

        #: The reactor in use on this client.  This may be overridden
        #: when a deterministic clock is needed, such as in unit tests.
        self.reactor = reactor

        #: The time of the last PONG seen from the server.
        self.last_pong = None

        #: An `~twisted.internet.interfaces.IDelayedCall` used to detect
        #: timeouts that occur after connecting to the server, but
        #: before receiving the ``RPL_WELCOME`` message that starts the
        #: normal PING heartbeat.
        self.signon_timeout = None

        self.log.info('Assuming default CASEMAPPING "rfc1459"')
        #: The `.CaseMapping` currently in effect on this connection.
        #: Defaults to ``rfc1459`` if none is explicitly provided by the
        #: server.
        self.case_mapping = mapping.by_name('rfc1459')

        #: A mapping of channels to the set of nicks present in each
        #: channel.
        self.channel_names = {}

        #: A mapping of channels to a mapping containing message buffers
        #: for each channel, keyed by nick.
        self.message_buffers = {PRIVATE_CHANNEL: {}}

        #: If the bot is currently firing callbacks, a queue of
        #: `.Message` objects for which the bot has yet to fire
        #: callbacks.  Otherwise, `None`.
        self.message_queue = None

        #: If joins are suspended, a list of channels to join when joins
        #: are resumed.  Otherwise, `None`.
        self.suspended_joins = None

    # Utility methods

    def _case_mapped_dict(self, initial=None):
        """Return a `.CaseMappedDict` using this connection's current
        case mapping."""
        return mapping.CaseMappedDict(initial, case_mapping=self.case_mapping)

    def _lower(self, string):
        """Convenience alias for ``self.case_mapping.lower``."""
        return self.case_mapping.lower(string)

    def _upper(self, string):
        """Convenience alias for ``self.case_mapping.upper``."""
        return self.case_mapping.upper(string)

    def is_channel(self, name):
        """Return `True` if *name* belongs to a channel, according to
        the server-provided list of channel prefixes, or `False`
        otherwise."""
        # We can assume the CHANTYPES feature will always be present,
        # since Twisted gives it a default value.
        return name[0] in self.supported.getFeature('CHANTYPES')

    def suspend_joins(self):
        """Suspend all channel joins until `.resume_joins` is called."""
        # If suspended_joins is not None, then we've already suspended
        # joins for this client, and we shouldn't clobber the queue.
        if self.suspended_joins is not None:
            return
        self.log.info('Suspending channel joins')
        self.suspended_joins = []

    def resume_joins(self):
        """Resume immediate joining of channels after suspending it with
        `.suspend_joins`, and perform any channel joins that have been
        queued in the interim."""
        if self.suspended_joins is None:
            return
        self.log.info('Resuming channel joins')
        suspended_joins = self.suspended_joins
        self.suspended_joins = None
        for channel in suspended_joins:
            self.join(channel)

    # Connection maintenance

    def connectionMade(self):
        """Called when a connection has been successfully made to the
        IRC server."""
        self.log.info('Connected to server')
        super(Connection, self).connectionMade()
        self.signon_timeout = self.reactor.callLater(
            self.max_lag, self.signon_timed_out)

    def signon_timed_out(self):
        """Called when a timeout occurs after connecting to the server,
        but before receiving the ``RPL_WELCOME`` message that starts the
        normal PING heartbeat."""
        self.log.info('Sign-on timeout ({log_source.max_lag} seconds); '
                      'disconnecting')
        self.transport.abortConnection()

    def _createHeartbeat(self):
        heartbeat = super(Connection, self)._createHeartbeat()
        heartbeat.clock = self.reactor
        return heartbeat

    def _sendHeartbeat(self):
        lag = self.reactor.seconds() - self.last_pong
        if lag > self.max_lag:
            self.log.info('Ping timeout ({lag} > {log_source.max_lag} '
                          'seconds); disconnecting', lag=lag)
            self.transport.abortConnection()
            return
        super(Connection, self)._sendHeartbeat()

    def startHeartbeat(self):
        self.last_pong = self.reactor.seconds()
        super(Connection, self).startHeartbeat()

    def after_reload(self):
        """Join or part channels after a settings reload."""
        for channel in self.settings.autojoin_channels:
            if channel not in self.channel_names:
                self.join(channel)
        for channel in self.settings.autopart_channels:
            if channel in self.channel_names:
                self.leave(channel)

    def connectionLost(self, reason):
        """Called when the connection to the IRC server has been lost
        or disconnected."""
        self.log.info('Disconnected from server')
        self.respond_to(Message(self, False, 'disconnected'))
        super(Connection, self).connectionLost(reason)

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
                self.log.info('Ignoring unsupported server CASEMAPPING '
                              '"{name}"', name=name)
            else:
                self.log.info('Using server-provided CASEMAPPING '
                              '"{name}"', name=name)

    def privmsg(self, prefix, channel, message):
        """Called when we receive a message from another user."""
        if not self.is_channel(channel):
            self.log.info('Message from {prefix} for {channel}: {message}',
                          prefix=prefix, channel=channel, message=message)

    def joined(self, channel):
        """Called when the bot successfully joins the given *channel*."""
        self.log.info('Successfully joined {channel}', channel=channel)
        self.channel_names[channel] = set()
        self.message_buffers[channel] = {}

    def left(self, channel):
        """Called when the bot leaves the given *channel*."""
        self.log.info('Leaving {channel}', channel=channel)
        del self.channel_names[channel]
        del self.message_buffers[channel]

    def noticed(self, prefix, channel, message):
        """Called when we receive a notice from another user."""
        if not self.is_channel(channel):
            self.log.info('Notice from {prefix} for {channel}: {message}',
                          prefix=prefix, channel=channel, message=message)

    def signedOn(self):
        """Called after successfully signing on to the server."""
        self.log.info('Successfully signed on to server')
        if self.signon_timeout:
            self.signon_timeout.cancel()
        self.respond_to(Message(self, False, 'connected'))
        # Resetting the connection delay when a successful connection is
        # made, instead of at IRC sign-on, overlooks situations such as
        # host bans where the server accepts a connection and then
        # immediately disconnects the client.  In these cases, the delay
        # should continue to increase, especially if the problem is that
        # there are too many connections!
        if self.factory:
            self.factory.resetDelay()
        for channel in self.settings.autojoin_channels:
            self.join(channel)

    def kickedFrom(self, channel, kicker, message):
        """Called when the bot is kicked from the given *channel*."""
        self.log.info('Kicked from {channel} by {kicker}: {message}',
                      channel=channel, kicker=kicker, message=message)
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
        `.suspend_joins`, add the channel to the join queue and actually
        join it when `.resume_joins` is called."""
        if self.suspended_joins is not None:
            self.log.info('Adding {channel} to join queue', channel=channel)
            self.suspended_joins.append(channel)
            return
        self.log.info('Joining {channel}', channel=channel)
        super(Connection, self).join(channel)

    def kick(self, channel, nick, reason=None):
        """Kick the the given *nick* from the given *channel*."""
        super(Connection, self).kick(channel, nick, reason)
        self.channel_names[channel].discard(nick)
        self.message_buffers[channel].pop(nick, None)

    def setNick(self, nickname):
        """Change the bot's nickname."""
        oldnick = self.nickname
        super(Connection, self).setNick(nickname)
        for channel in self.channel_names:
            if oldnick in self.channel_names[channel]:  # sanity check
                self.channel_names[channel].discard(oldnick)
                self.channel_names[channel].add(nickname)
        for channel in self.message_buffers:
            # We should never have a buffer for ourselves.
            self.message_buffers[channel].pop(oldnick, None)

    def quit(self, message=''):
        """Quit from the IRC server."""
        super(Connection, self).quit(message)
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

    #
    # Event plugin hooks
    #

    def respond_to(self, msg):
        """Start the appropriate event plugin callbacks for *msg*, and
        return a `~twisted.internet.defer.DeferredList`."""
        if self.message_queue is not None:
            # We're already firing callbacks.  Bail.
            self.message_queue.append(msg)
            return
        self.message_queue = [msg]
        deferreds = []
        while self.message_queue:
            msg = self.message_queue.pop(0)
            # Build the set of plugins that should be fired.
            plugins = set()
            if msg.action == 'command':
                plugins.update(
                    msg.settings.plugins_by_keyword(msg.subaction))
            elif msg.venue:
                plugins.update(msg.settings.active_plugins().iterkeys())
            elif msg.actor:
                # Forward the message only to plugins enabled in at
                # least one channel where the actor is present.
                #
                # This implementation does this by creating a synthetic
                # message for every one of those channels and asking the
                # settings object for each of those message's active
                # plugins.  This is an ugly hack and should be replaced
                # with something less unsightly.
                for channel, names in self.channel_names.iteritems():
                    if msg.actor.nick not in names:
                        continue
                    channel_msg = msg._replace(venue=channel)
                    plugins.update(
                        channel_msg.settings.active_plugins().iterkeys())
            else:
                # Neither a venue nor an actor.  Forward the message to
                # every plugin active on this connection.
                plugins.update(self.settings.loaded_plugins.itervalues())
            for plugin in plugins:
                deferred = plugin.respond_to(msg)
                if msg.action == 'command':
                    deferred.addCallback(self.buffer_and_reply, msg)
                    deferred.addErrback(self.reply_from_error, msg)
                else:
                    deferred.addErrback(self.log.failure,
                        'Error in plugin {name} responding to {msg}',
                        name=plugin.__class__.name, msg=msg)
                deferreds.append(deferred)
            # Extract any command invocations and fire events for them.
            if msg.private:
                command_prefixes = None
            else:
                # Make a copy so we don't accidentally change the value.
                command_prefixes = tuple(
                    msg.settings.get('command_prefixes', default=[]))
                if msg.settings.get('direct_addressing', default=True):
                    command_prefixes += (self.nickname + ':',
                                         self.nickname + ',')
            command_msg = msg.extract_command(prefixes=command_prefixes)
            if command_msg is not None:
                # Get the command message in immediately after the
                # current privmsg, as they come from the same event.
                self.message_queue.insert(0, command_msg)
        self.message_queue = None
        return DeferredList(deferreds)

    #
    # Command replies and message buffering
    #

    @inlineCallbacks
    def buffer_and_reply(self, response, request):
        """Add the :ref:`command reply <command-replies>` *response* to
        the appropriate user's reply buffer according to the invocation
        `.Message` *request*, and reply with the first message."""
        venue = PRIVATE_CHANNEL if request.private else request.venue
        if response is None:
            self.message_buffers[venue].pop(request.actor.nick, None)
            returnValue(None)
        buf = ReplyBuffer(response, request)
        reply_string = (yield maybeDeferred(next, buf, None)) or 'No results.'
        remaining = length_hint(buf)
        tail = ' (+{} more)'.format(remaining) if remaining else ''
        self.message_buffers[venue][request.actor.nick] = buf
        self.reply(reply_string, request, tail=tail)

    def reply(self, string, request, tail=''):
        """Send a reply *string*, truncated to `MAX_REPLY_LENGTH`
        characters, with `tail` appended.  If the request venue is a
        channel, send the reply to the venue as a standard message
        addressed to *request*'s `~.Message.target`, formatted using the
        `~.Message.venue`'s reply format.  Otherwise, send the reply as
        a notice to *request*'s `~.Message.actor`."""
        if not string:
            return
        string = string.replace('\n', ' / ')
        if isinstance(string, unicode):
            encoding = request.encoding
            truncated = truncate_unicode(string, MAX_REPLY_LENGTH, encoding)
            if truncated.decode(encoding) != string:
                truncated += u'...'.encode(encoding)
            string = truncated
        else:
            if len(string) > MAX_REPLY_LENGTH:
                string = string[:MAX_REPLY_LENGTH] + '...'
        string += tail
        if request.private:
            self.log.info('Private reply for {request.actor.nick}: {string}',
                          request=request, string=string)
            self.notice(request.actor.nick, string)
            return
        self.log.info('Reply for {request.actor.nick} in {request.venue}: '
                      '{string}', request=request, string=string)
        reply_format = request.settings.get(
            'reply_format', default='\x0314{target}: {message}')
        self.msg(request.venue, reply_format.format(
            target=request.target, message=string))

    def reply_from_error(self, failure, request):
        """Call `.reply` with information on a *failure* that occurred
        in the callback invoked to handle a command request. If
        *failure* wraps a `.UserVisibleError`, or the ``show_errors``
        configuration option is true, reply with its exception string.
        Otherwise, log the error and reply with a generic message.

        This method is automatically called whenever an unhandled
        exception occurs in a plugin's command callback, and should
        never need to be invoked manually.
        """
        error_request = request._replace(target=request.actor.nick)
        if failure.check(UserVisibleError):
            self.reply(failure.getErrorMessage(), error_request)
            return
        message = 'Command \x02{}\x02 encountered an error'.format(
            request.subaction)
        if request.settings.get('show_errors', default=False):
            message += ': \x02{}\x02'.format(failure.getErrorMessage())
        self.log.failure('Error during command callback: '
                         '{request.subaction} {request.content}',
                         failure=failure, request=request)
        self.reply(message + '.', error_request)

    def _lineReceived(self, line):
        # Twisted doesn't like it when `lineReceived` returns a value,
        # but we need to do so for some unit tests.
        deferred = self.respond_to(Message.from_raw(self, False, line))
        super(Connection, self).lineReceived(line)
        return deferred

    def lineReceived(self, line):
        """Overrides `.IRCClient.lineReceived`."""
        self._lineReceived(line)

    def sendLine(self, line):
        """Overrides `.IRCClient.sendLine`."""
        deferred = self.respond_to(Message.from_raw(
            self, True, line, actor=self.nickname))
        super(Connection, self).sendLine(line)
        return deferred


class ConnectionFactory(ReconnectingClientFactory):
    """Creates `.Connection` instances."""
    protocol = Connection
    log = Logger()

    def __init__(self):
        #: The `ConnectionSettings` object associated with this factory.
        self.settings = ConnectionSettings()
        #: A `WeakSet` containing associated `Connection` objects.
        self.protocols = WeakSet()

    def startedConnecting(self, connector):
        self.log.info('Attempting to connect to server')

    def buildProtocol(self, addr):
        protocol = ReconnectingClientFactory.buildProtocol(self, addr)
        protocol.settings = self.settings
        # Set various properties defined by Twisted's IRCClient.
        protocol.nickname = self.settings.nickname or protocol.nickname
        protocol.password = self.settings.password or protocol.password
        protocol.realname = self.settings.realname or protocol.realname
        protocol.username = self.settings.username or protocol.username
        protocol.userinfo = self.settings.userinfo or protocol.userinfo
        self.protocols.add(protocol)
        return protocol

    def reload_settings(self, dct):
        """Update this connection's settings using *dct*, then call
        `after_reload` on each of this factory's active connections."""
        self.log.info('Reloading settings')
        self.settings.replace(dct)
        for protocol in self.protocols:
            protocol.after_reload()
