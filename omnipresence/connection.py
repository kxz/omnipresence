# -*- test-case-name: omnipresence.test.test_connection -*-
"""Core IRC connection protocol class and supporting machinery."""


import collections
from copy import copy
from itertools import tee
import re

import sqlobject
from twisted.internet import reactor
from twisted.internet.defer import DeferredList, maybeDeferred, succeed
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log
from twisted.python.failure import Failure
from twisted.words.protocols.irc import IRCClient

from . import __version__, __source__, mapping
from .message import Message, chunk, truncate_unicode
from .plugin import UserVisibleError
from .settings import ConnectionSettings, PRIVATE_CHANNEL


#: The length to chunk string command replies to, in bytes.
CHUNK_LENGTH = 256

#: The maximum length of a single command reply, in bytes.
MAX_REPLY_LENGTH = 320


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

class Connection(IRCClient):
    """Omnipresence's core IRC client protocol."""

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

        log.msg('Assuming default CASEMAPPING "rfc1459"')
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
        log.msg('Suspending channel joins')
        self.suspended_joins = []

    def resume_joins(self):
        """Resume immediate joining of channels after suspending it with
        `.suspend_joins`, and perform any channel joins that have been
        queued in the interim."""
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
        """Called when we receive a notice from another user."""
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
        if self.factory:
            self.factory.resetDelay()
        for channel in self.settings.autojoin_channels:
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
        `.suspend_joins`, add the channel to the join queue and actually
        join it when `.resume_joins` is called."""
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
                deferred = maybeDeferred(plugin.respond_to, msg)
                if msg.action == 'command':
                    deferred.addCallback(self.buffer_reply, msg)
                    deferred.addCallback(self.reply_from_buffer, msg)
                    deferred.addErrback(self.reply_from_error, msg)
                else:
                    deferred.addErrback(log.err,
                        'Error in plugin %s responding to %s' %
                        (plugin.__class__.name, msg))
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

    def buffer_reply(self, response, request):
        """Add the :ref:`command reply <command-replies>` *response* to
        the appropriate user's reply buffer according to the invocation
        `.Message` *request*."""
        venue = PRIVATE_CHANNEL if request.private else request.venue
        if not response:
            self.message_buffers[venue].pop(request.actor.nick, None)
            return request.actor.nick
        if isinstance(response, basestring):
            buf = chunk(response, request.encoding, CHUNK_LENGTH)
        elif isinstance(response, collections.Iterable):
            buf = response
        else:
            raise TypeError('invalid command reply type ' +
                            type(response).__name__)
        self.message_buffers[venue][request.actor.nick] = buf
        return request.actor.nick

    def copy_buffer(self, venue, source, target):
        """Copy a reply buffer from the *source* nick to the *target*
        nick in *venue*, and return the copy."""
        buf = self.message_buffers[venue].get(source, [])
        if self.case_mapping.equates(source, target):
            return buf
        if isinstance(buf, collections.Sequence):
            new = copy(buf)
            self.message_buffers[venue][target] = new
            return new
        # Assume an iterator.
        one, two = tee(buf)
        self.message_buffers[venue][source] = one
        self.message_buffers[venue][target] = two
        return two

    def reply_from_buffer(self, nick, request, reply_when_empty=False):
        """Call `.reply` with the next reply from the reply buffer
        belonging to *nick* in the `~.Message.venue` of the invocation
        `~.Message` *request*.  Return a
        `~twisted.internet.defer.Deferred` yielding either the reply's
        contents, or `None` if no reply was made because of an empty
        reply buffer."""
        venue = PRIVATE_CHANNEL if request.private else request.venue
        buf = self.copy_buffer(venue, nick, request.actor.nick)
        if isinstance(buf, collections.Sequence):
            next_reply = None
            if buf:
                next_reply = buf.pop(0)
                remaining_chars = sum(map(len, buf))
                if remaining_chars:
                    next_reply = '{} (+{} more characters)'.format(
                        next_reply, remaining_chars)
            deferred = succeed(next_reply)
        else:  # assume an iterator
            deferred = maybeDeferred(next, buf)
            # Return None on StopIteration.  It looks weird, yes.
            deferred.addErrback(lambda f: f.trap(StopIteration) and None)
        if reply_when_empty:
            deferred.addCallback(lambda s: s or 'No text in buffer.')
        deferred.addCallback(self.reply, request)
        deferred.addErrback(self.reply_from_error, request)
        return deferred

    def reply(self, string, request):
        """Send a reply *string*.  If the request venue is a channel,
        send the reply to the venue as a standard message addressed to
        *request*'s `~.Message.target`, formatted using the
        `~.Message.venue`'s reply format.  Otherwise, send the reply as
        a notice to *request*'s `~.Message.actor`."""
        if not string:
            return
        string = string.replace('\n', ' / ')
        if isinstance(string, unicode):
            encoding = request.encoding
            truncated = truncate_unicode(string, MAX_REPLY_LENGTH, encoding)
            if truncated.decode(encoding) != string:
                string = truncated + u'...'.encode(encoding)
        else:
            if len(string) > MAX_REPLY_LENGTH:
                string = string[:MAX_REPLY_LENGTH] + '...'
        if request.private:
            log.msg('Private reply for %s: %s' % (request.actor.nick, string))
            self.notice(request.actor.nick, string)
            return
        log.msg('Reply for %s in %s: %s' %
                (request.target, request.venue, string))
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
        log.err(failure, 'Error during command callback: %s %s' %
                (request.subaction, request.content))
        self.reply(message + '.', error_request)

    def lineReceived(self, line):
        """Overrides `.IRCClient.lineReceived`."""
        deferred = self.respond_to(Message.from_raw(self, False, line))
        IRCClient.lineReceived(self, line)
        return deferred

    def sendLine(self, line):
        """Overrides `.IRCClient.sendLine`."""
        deferred = self.respond_to(Message.from_raw(
            self, True, line, actor=self.nickname))
        IRCClient.sendLine(self, line)
        return deferred


class ConnectionFactory(ReconnectingClientFactory):
    """Creates `.Connection` instances."""
    protocol = Connection

    def __init__(self):
        #: The `ConnectionSettings` object associated with this factory.
        self.settings = ConnectionSettings()

    def startedConnecting(self, connector):
        log.msg('Attempting to connect to server')

    def buildProtocol(self, addr):
        protocol = ReconnectingClientFactory.buildProtocol(self, addr)
        protocol.settings = self.settings
        # Set various properties defined by Twisted's IRCClient.
        protocol.nickname = self.settings.nickname or protocol.nickname
        protocol.password = self.settings.password or protocol.password
        protocol.realname = self.settings.realname or protocol.realname
        protocol.username = self.settings.username or protocol.username
        protocol.userinfo = self.settings.userinfo or protocol.userinfo
        return protocol
