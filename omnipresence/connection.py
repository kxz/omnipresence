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

from . import __version__, __source__
from .case_mapping import CaseMapping, CaseMappedDict
from .compat import length_hint
from .hostmask import Hostmask
from .message import Message, MessageType, ReplyBuffer, truncate_unicode
from .plugin import UserVisibleError
from .settings import ConnectionSettings, PRIVATE_CHANNEL


#: The maximum length of a single command reply, in bytes.
MAX_REPLY_LENGTH = 288


class ConnectionBase(IRCClient, object):
    """Provides fundamental functionality for connection mixins."""

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
        self.case_mapping = CaseMapping.by_name('rfc1459')

    # Utility methods

    def _case_mapped_dict(self, initial=None):
        """Return a `.CaseMappedDict` using this connection's current
        case mapping."""
        return CaseMappedDict(initial, case_mapping=self.case_mapping)

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

    # Connection maintenance

    def connectionMade(self):
        """See `IRCClient.connectionMade`."""
        self.log.info('Connected to server')
        super(ConnectionBase, self).connectionMade()
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
        heartbeat = super(ConnectionBase, self)._createHeartbeat()
        heartbeat.clock = self.reactor
        return heartbeat

    def _sendHeartbeat(self):
        lag = self.reactor.seconds() - self.last_pong
        if lag > self.max_lag:
            self.log.info('Ping timeout ({lag} > {log_source.max_lag} '
                          'seconds); disconnecting', lag=lag)
            self.transport.abortConnection()
            return
        super(ConnectionBase, self)._sendHeartbeat()

    def startHeartbeat(self):
        self.last_pong = self.reactor.seconds()
        super(ConnectionBase, self).startHeartbeat()

    def irc_PONG(self, prefix, secs):
        self.last_pong = self.reactor.seconds()

    def connectionLost(self, reason):
        """See `IRCClient.connectionLost`."""
        self.log.info('Disconnected from server')
        super(ConnectionBase, self).connectionLost(reason)

    # Callbacks inherited from IRCClient

    def isupport(self, options):
        """See `IRCClient.isupport`."""
        # Update the connection case mapping if one is available.
        case_mappings = self.supported.getFeature('CASEMAPPING')
        if case_mappings:
            name = case_mappings[0]
            try:
                case_mapping = CaseMapping.by_name(name)
            except ValueError:
                self.log.info('Ignoring unsupported server CASEMAPPING '
                              '"{name}"', name=name)
            else:
                if self.case_mapping != case_mapping:
                    self.case_mapping = case_mapping
                    self.settings.set_case_mapping(self.case_mapping)
                    self.log.info('Using server-provided CASEMAPPING '
                                  '"{name}"', name=name)

    def privmsg(self, prefix, channel, message):
        """See `IRCClient.privmsg`."""
        if not self.is_channel(channel):
            self.log.info('Message from {prefix} for {channel}: {message}',
                          prefix=prefix, channel=channel, message=message)

    def joined(self, channel):
        """See `IRCClient.joined`."""
        self.log.info('Successfully joined {channel}', channel=channel)

    def left(self, channel):
        """See `IRCClient.left`."""
        self.log.info('Leaving {channel}', channel=channel)

    def noticed(self, prefix, channel, message):
        """See `IRCClient.noticed`."""
        if not self.is_channel(channel):
            self.log.info('Notice from {prefix} for {channel}: {message}',
                          prefix=prefix, channel=channel, message=message)

    def signedOn(self):
        """See `IRCClient.signedOn`."""
        self.log.info('Successfully signed on to server')
        if self.signon_timeout:
            self.signon_timeout.cancel()
        # Resetting the connection delay when a successful connection is
        # made, instead of at IRC sign-on, overlooks situations such as
        # host bans where the server accepts a connection and then
        # immediately disconnects the client.  In these cases, the delay
        # should continue to increase, especially if the problem is that
        # there are too many connections!
        if self.factory:
            self.factory.resetDelay()

    def kickedFrom(self, channel, kicker, message):
        """See `IRCClient.kickedFrom`."""
        self.log.info('Kicked from {channel} by {kicker}: {message}',
                      channel=channel, kicker=kicker, message=message)

    def join(self, channel):
        """See `IRCClient.join`."""
        self.log.info('Joining {channel}', channel=channel)
        super(ConnectionBase, self).join(channel)

    #
    # Command replies
    #

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


#
# State tracking
#

USER_MODE_PREFIX = re.compile(r'^[^A-Za-z0-9\-\[\]\\`^{}]+')


class VenueUserInfo(object):
    """A container for information about a user's state in a particular
    venue."""

    def __init__(self):
        #: This user's current channel reply buffer.
        self.reply_buffer = []


class VenueInfo(object):
    """A container for information about a venue."""

    def __init__(self, case_mapping=None):
        #: A dictionary mapping nicks to `.VenueUserInfo` objects.
        self.nicks = CaseMappedDict(case_mapping=case_mapping)

        #: This channel's topic, or the empty string if none is set.
        self.topic = ''

    def add_nick(self, nick):
        self.nicks.setdefault(nick, VenueUserInfo())

    def remove_nick(self, nick):
        try:
            del self.nicks[nick]
        except KeyError:
            pass


class StateTrackingMixin(object):
    """A connection mixin providing venue state tracking."""

    def __init__(self):
        super(StateTrackingMixin, self).__init__()
        self._clear_venues()

    def _clear_venues(self):
        """Reset this mixin's venue information."""
        #: A mapping of venue names to `VenueInfo` objects.
        self.venues = CaseMappedDict(case_mapping=self.case_mapping)
        self.venues[PRIVATE_CHANNEL] = VenueInfo(
            case_mapping=self.case_mapping)

    def isupport(self, options):
        """See `IRCClient.isupport`."""
        # If the case mapping changed, update any CaseMappedDict objects
        # we know about.
        old_case_mapping = self.case_mapping
        super(StateTrackingMixin, self).isupport(options)
        if self.case_mapping != old_case_mapping:
            self.venues = CaseMappedDict(self.venues,
                                         case_mapping=self.case_mapping)
            for venue_info in self.venues.itervalues():
                venue_info.nicks = CaseMappedDict(
                    venue_info.nicks, case_mapping=self.case_mapping)

    def joined(self, channel):
        """See `IRCClient.joined`."""
        super(StateTrackingMixin, self).joined(channel)
        self.venues[channel] = VenueInfo(case_mapping=self.case_mapping)

    def irc_RPL_NAMREPLY(self, prefix, params):
        channel = params[2]
        names = params[3].split()
        self.names_arrived(channel, names)

    def names_arrived(self, channel, names):
        # Liberally strip out all user mode prefixes such as @%+.  Some
        # networks support more prefixes, so this removes any prefixes
        # with characters not valid in nicknames.
        for nick in names:
            nick = USER_MODE_PREFIX.sub('', nick)
            self.venues[channel].add_nick(nick)

    def userJoined(self, prefix, channel):
        """See `IRCClient.userJoined`."""
        super(StateTrackingMixin, self).userJoined(prefix, channel)
        self.venues[channel].add_nick(Hostmask.from_string(prefix).nick)

    def userLeft(self, prefix, channel):
        """See `IRCClient.userLeft`."""
        super(StateTrackingMixin, self).userLeft(prefix, channel)
        self.venues[channel].remove_nick(Hostmask.from_string(prefix).nick)

    def userQuit(self, nick, quitMessage):
        """See `IRCClient.userQuit`."""
        super(StateTrackingMixin, self).userQuit(nick, quitMessage)
        for venue_info in self.venues.itervalues():
            venue_info.remove_nick(nick)

    def userKicked(self, kickee, channel, kicker, message):
        """See `IRCClient.userKicked`."""
        super(StateTrackingMixin, self).userKicked(
            kickee, channel, kicker, message)
        # Our own kicks are echoed back to us, so we don't need to do
        # anything special for them.
        del self.venues[channel].nicks[kickee]

    def _renamed(self, old, new):
        """Called when a user changes nicknames."""
        for venue_info in self.venues.itervalues():
            if old in venue_info.nicks:
                venue_info.nicks[new] = venue_info.nicks[old]
                venue_info.remove_nick(old)
            else:  # must have been asleep at the wheel
                venue_info.add_nick(new)

    def userRenamed(self, old, new):
        """See `IRCClient.userRenamed`."""
        super(StateTrackingMixin, self).userRenamed(old, new)
        self._renamed(old, new)

    def setNick(self, new):
        """See `IRCClient.setNick`."""
        super(StateTrackingMixin, self).setNick(new)
        self._renamed(self.nickname, new)

    def topicUpdated(self, nick, channel, topic):
        """See `IRCClient.topicUpdated`."""
        self.venues[channel].topic = topic

    def left(self, channel):
        """See `IRCClient.left`."""
        super(StateTrackingMixin, self).left(channel)
        del self.venues[channel]

    def kickedFrom(self, channel, kicker, message):
        """See `IRCClient.kickedFrom`."""
        super(StateTrackingMixin, self).kickedFrom(channel)
        del self.venues[channel]

    def quit(self, message=''):
        """See `IRCClient.quit`."""
        super(StateTrackingMixin, self).quit(message)
        self._clear_venues()


#
# Join suspension
#

class JoinSuspensionMixin(object):
    """A connection mixin providing join suspension."""

    def __init__(self):
        super(JoinSuspensionMixin, self).__init__()
        #: If joins are suspended, a list of channels to join when joins
        #: are resumed.  Otherwise, `None`.
        self.suspended_joins = None

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

    def join(self, channel):
        """Join the given *channel*.  If joins have been suspended with
        `.suspend_joins`, add the channel to the join queue and actually
        join it when `.resume_joins` is called."""
        if self.suspended_joins is not None:
            self.log.info('Adding {channel} to join queue', channel=channel)
            self.suspended_joins.append(channel)
            return
        super(JoinSuspensionMixin, self).join(channel)


#
# Mix it all together
#

class Connection(StateTrackingMixin,
                 JoinSuspensionMixin,
                 ConnectionBase):
    """Omnipresence's core IRC client protocol."""

    def __init__(self):
        super(Connection, self).__init__()

        #: If the bot is currently firing callbacks, a queue of
        #: `.Message` objects for which the bot has yet to fire
        #: callbacks.  Otherwise, `None`.
        self.message_queue = None

    def signedOn(self):
        """See `IRCClient.signedOn`."""
        super(Connection, self).signedOn()
        self.respond_to(Message(self, False, 'connected'))
        for channel in self.settings.autojoin_channels:
            self.join(channel)

    def after_reload(self):
        """Join or part channels after a settings reload."""
        for channel in self.settings.autojoin_channels:
            if channel not in self.venues:
                self.join(channel)
        for channel in self.settings.autopart_channels:
            if channel in self.venues:
                self.leave(channel)

    def connectionLost(self, reason):
        """See `IRCClient.connectionLost`."""
        self.respond_to(Message(self, False, 'disconnected'))
        super(Connection, self).connectionLost(reason)

    #
    # Event plugin hooks
    #
    # These are defined down here because they need StateTrackingMixin.
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
            if msg.action is MessageType.command:
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
                for channel, venue_info in self.venues.iteritems():
                    if msg.actor.nick not in venue_info.nicks:
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
                if msg.action is MessageType.command:
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

    @inlineCallbacks
    def buffer_and_reply(self, response, request):
        """Add the :ref:`command reply <command-replies>` *response* to
        the appropriate user's reply buffer according to the invocation
        `.Message` *request*, and reply with the first message."""
        venue = PRIVATE_CHANNEL if request.private else request.venue
        venue_info = self.venues[venue]
        if response is None:
            if request.actor.nick in venue_info.nicks:
                del venue_info.nicks[request.actor.nick]
            returnValue(None)
        buf = ReplyBuffer(response, request)
        reply_string = (yield maybeDeferred(next, buf, None)) or 'No results.'
        remaining = length_hint(buf)
        tail = ' (+{} more)'.format(remaining) if remaining else ''
        venue_info.nicks.setdefault(request.actor.nick, VenueUserInfo())
        venue_info.nicks[request.actor.nick].reply_buffer = buf
        self.reply(reply_string, request, tail=tail)

    def _lineReceived(self, line):
        # Twisted doesn't like it when `lineReceived` returns a value,
        # but we need to do so for some unit tests.
        deferred = self.respond_to(Message.from_raw(self, False, line))
        super(ConnectionBase, self).lineReceived(line)
        return deferred

    def lineReceived(self, line):
        """Overrides `.IRCClient.lineReceived`."""
        self._lineReceived(line)

    def sendLine(self, line):
        """Overrides `.IRCClient.sendLine`."""
        deferred = self.respond_to(Message.from_raw(
            self, True, line, actor=self.nickname))
        super(ConnectionBase, self).sendLine(line)
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
