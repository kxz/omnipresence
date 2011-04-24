import platform
import re

import httplib2
import sqlobject
from twisted.internet import defer, protocol, task, threads
from twisted.plugin import getPlugins
from twisted.python import failure, log
from twisted.words.protocols import irc

from omnipresence import iomnipresence, plugins, ircutil, version


VERSION_NAME = 'Omnipresence'
VERSION_NUM = version.VERSION_NUMBER
VERSION_ENV = platform.platform()
SOURCE_URL = 'https://bitbucket.org/kxz/omnipresence'


class IRCClient(irc.IRCClient):
    """Omnipresence's core IRC client protocol class.  Common parameters
    for callbacks and class methods include:
    
    *prefix*
        A full ``nick!user@host`` mask.
    *channel* or *nick*
        An IRC channel, for commands directed at an entire channel; or
        specific nickname, for commands directed at a single user.
        Despite their names, parameters with either name will usually
        take both channels and nicks as values.  To distinguish between
        the two in a callback, use the Twisted constant
        :py:const:`CHANNEL_PREFIXES`::

            from twisted.words.protocols.irc import CHANNEL_PREFIXES

            class Handler(object):
                # ...
                def callback(self, prefix, channel):
                    if channel[0] in irc.CHANNEL_PREFIXES:
                        # addressed to a channel
                    else:
                        # addressed to the bot specifically
        """
    # Instance variables handled by t.w.p.irc.IRCClient.
    versionName = VERSION_NAME
    versionNum = VERSION_NUM
    versionEnv = VERSION_ENV
    sourceURL = SOURCE_URL

    # Ping tracking variables.
    ping_count = 0
    ping_timer = None

    # Suspended join queue.
    suspended_joins = None
    
    # Dictionary mapping channels to the nicks present in each channel.
    channel_names = {}

    # Utility methods

    def ping_server(self, servername):
        if self.ping_count > 2:
            log.err('Sent three PINGs without receiving a PONG reply.')
            self.ping_timer.stop()
            self.transport.loseConnection()
            return

        self.sendLine('PING ' + servername)
        self.ping_count += 1

    def suspend_joins(self):
        """Suspend all channel joins until :py:meth:`resume_joins` is
        called."""
        # If suspended_joins is not None, then we've already suspended
        # joins for this client, and we shouldn't clobber the queue.
        if self.suspended_joins is not None:
            return

        log.msg('Suspending channel joins.')
        self.suspended_joins = set()

    def resume_joins(self):
        """Resume immediate joining of channels after suspending it with
        :py:meth:`suspend_joins`, and perform any channel joins that
        have been queued in the interim."""
        if self.suspended_joins is None:
            return

        log.msg('Resuming channel joins.')

        for channel in self.suspended_joins:
            self._join(channel)

        self.suspended_joins = None

    def call_handlers(self, event, channel, args=[]):
        # If the channel is None, this is a server event not associated with a 
        # specific channel, such as a successful sign-on or a quit.  Send the 
        # event to every registered handler.
        if channel is None:
            handlers = set()
            
            # If this is a quit or nick change, only invoke callbacks on the 
            # handlers that are active for the channels where the relevant 
            # user is present.
            if event in ('userQuit', 'userRenamed'):
                for channel in self.factory.handlers:
                    if (channel in self.channel_names and
                      args[0].split('!', 1)[0] in self.channel_names[channel]):
                        handlers.update(self.factory.handlers[ircutil.canonicalize(channel)])
            else:
                for channel in self.factory.handlers:
                    handlers.update(self.factory.handlers[ircutil.canonicalize(channel)])
        else:
            # If the channel doesn't start with an IRC channel prefix, treat 
            # the event as a private one.  Some networks send notices to "AUTH" 
            # when performing ident lookups, for example.
            if channel[0] not in irc.CHANNEL_PREFIXES:
                channel = '@'
    
            try:
                handlers = self.factory.handlers[ircutil.canonicalize(channel)]
            except KeyError:
                # How'd we get in this channel?
                log.err(None, 'Received event for non-configured channel "%s".'
                               % channel)
                return

        for handler in handlers:
            if hasattr(handler, event):
                d = defer.maybeDeferred(getattr(handler, event), self, *args)
                d.addErrback(log.err, 'Handler "%s" encountered an error.'
                                       % handler.name)

    def run_commands(self, prefix, channel, message):
        # First, get rid of formatting codes in the message.
        message = ircutil.remove_control_codes(message)
        
        # Second, see if the message matches any of the command prefixes 
        # specified in the configuration file.  We read directly from 
        # `self.factory.config` on every message, because the 
        # "current_nickname" default may change while the bot is being run.
        defaults = {'current_nickname': self.nickname}
        command_prefixes = self.factory.config.getspacelist('core',
                                                            'command_prefixes',
                                                            False, defaults)

        for command_prefix in command_prefixes:
            if message.lower().startswith(command_prefix.lower()):
                message = message[len(command_prefix):].strip()
                break
        else:
            # The message doesn't start with any of the given command prefixes.  
            # Continue command parsing if this is a private message; otherwise, 
            # bail out.
            if channel[0] in irc.CHANNEL_PREFIXES:
                return
            
            # Strip excess leading and trailing whitespace for
            # unprefixed commands sent through private messages.
            message = message.strip()

        args = message.split()
        if not args:
            return

        keyword = args[0].lower()
        if keyword not in self.factory.commands:
            return

        # Handle command redirection in the form of "args > nickname",
        # as long as the command is invoked in a public channel.
        reply_target = prefix
        if '>' in message and channel[0] in irc.CHANNEL_PREFIXES:
            (message, reply_target) = message.rsplit('>', 1)
            message = message.strip()
            reply_target = reply_target.strip()
        
        if reply_target != prefix:
            log.msg('Command from %s directed at %s on channel %s: %s'
                     % (prefix, reply_target, channel, message))
        else:
            log.msg('Command from %s on channel %s: %s'
                     % (prefix, channel, message))
        
        d = defer.maybeDeferred(self.factory.commands[keyword].execute,
                                self, prefix, reply_target, channel, message)
        d.addErrback(self.reply_with_error, prefix, channel, keyword)

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
        """
        if prefix:
            nick = prefix.split('!', 1)[0].strip()
            log.msg('Reply for %s on channel %s: %s'
                     % (nick, channel, message))
            
            if channel == self.nickname:
                self.notice(nick, message)
                return
            
            message = '%s: %s' % (nick, message)
        else:
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

    # Inherited from twisted.internet.protocol.BaseProtocol

    def connectionMade(self):
        """Called when a connection has been successfully made to the
        IRC server."""
        self.call_handlers('connectionMade', None)
        irc.IRCClient.connectionMade(self)
        log.msg('Connected to server.')

    # Inherited from twisted.internet.protocol.Protocol

    def connectionLost(self, reason):
        """Called when the connection to the IRC server has been lost
        or disconnected."""
        self.call_handlers('connectionLost', None, [reason])
        irc.IRCClient.connectionLost(self, reason)
        log.msg('Disconnected from server.')

    # Inherited from twisted.words.protocols.irc.IRCClient

    def myInfo(self, servername, version, umodes, cmodes):
        """Called with information about the IRC server at logon."""
        # Once myInfo is called, we know which server we are connected
        # to, so we can start performing keep-alive pings.
        self.ping_count = 0
        self.ping_timer = task.LoopingCall(self.ping_server, servername)
        self.ping_timer.start(60, False)

    def privmsg(self, prefix, channel, message):
        """Called when we receive a message from another user."""
        if channel[0] not in irc.CHANNEL_PREFIXES:
            log.msg('Message from %s for %s: %s' % (prefix, channel, message))

        self.call_handlers('privmsg', channel, [prefix, channel, message])
        self.run_commands(prefix, channel, message)
        
    def joined(self, prefix, channel):
        """Called when the bot successfully joins the given *channel*.
        Use this to perform channel-specific initialization."""
        log.msg('Successfully joined channel %s.' % channel)
        self.call_handlers('joined', channel, [prefix, channel])
        self.channel_names[channel] = set()
    
    def left(self, prefix, channel):
        """Called when the bot leaves the given *channel*."""
        self.call_handlers('left', channel, [prefix, channel])
    
    def noticed(self, prefix, channel, message):
        """Called when we receive a notice from another user.  Behaves
        largely the same as :py:meth:`privmsg`."""
        if channel[0] not in irc.CHANNEL_PREFIXES:
            log.msg('Notice from %s for %s: %s' % (prefix, channel, message))

        self.call_handlers('noticed', channel, [prefix, channel, message])
    
    def modeChanged(self, prefix, channel, set, modes, args):
        """Called when a channel's mode is changed.  See `the Twisted
        documentation
        <http://twistedmatrix.com/documents/current/api/twisted.words.protocols.irc.IRCClient.html#modeChanged>`_
        for information on this method's parameters."""
        self.call_handlers('modeChanged', channel,
                           [prefix, channel, set, modes, args])
    
    def signedOn(self):
        """Called after successfully signing on to the server."""
        log.msg('Successfully signed on to server.')

        # Resetting the connection delay when a successful connection is
        # made, instead of at IRC sign-on, overlooks situations such as
        # host bans where the server accepts a connection and then
        # immediately disconnects the client.  In these cases, the delay
        # should continue to increase, especially if the problem is that
        # there are too many connections!
        self.factory.resetDelay()

        self.call_handlers('signedOn', None)
        for channel in self.factory.config.options('channels'):
            # Skip over "@", which has a special meaning to the bot.
            if channel != '@':
                self.join(channel)

    def kickedFrom(self, channel, kicker, message):
        """Called when the bot is kicked from the given *channel*."""
        self.call_handlers('kickedFrom', channel, [channel, kicker, message])
        self.channel_names[channel].clear()
    
    def nickChanged(self, nick):
        """Called when the bot's nickname is changed."""
        self.call_handlers('nickChanged', None, [nick])
        irc.IRCClient.nickChanged(self, nick)
    
    def userJoined(self, prefix, channel):
        """Called when another user joins the given *channel*."""
        self.call_handlers('userJoined', channel, [prefix, channel])
        self.channel_names[channel].add(prefix.split('!', 1)[0])
    
    def userLeft(self, prefix, channel):
        """Called when another user leaves the given *channel*."""
        self.call_handlers('userLeft', channel, [prefix, channel])
        self.channel_names[channel].discard(prefix.split('!', 1)[0])
    
    def userQuit(self, prefix, quitMessage):
        """Called when another user has quit the IRC server."""
        self.call_handlers('userQuit', None, [prefix, quitMessage])
        for channel in self.channel_names:
            self.channel_names[channel].discard(prefix.split('!', 1)[0])

    def userKicked(self, kickee, channel, kicker, message):
        """Called when another user kicks a third party from the given
        *channel*."""
        self.call_handlers('userKicked', channel,
                           [kickee, channel, kicker, message])
        self.channel_names[channel].discard(kickee)

    def action(self, prefix, channel, data):
        """Called when a ``/me`` action is performed in the given
        *channel*."""
        self.call_handlers('action', channel, [prefix, channel, data])

    def topicUpdated(self, nick, channel, newTopic):
        """Called when the topic of the given *channel* is changed."""
        self.call_handlers('topicUpdated', channel, [nick, channel, newTopic])
    
    def userRenamed(self, oldname, newname):
        """Called when another user changes nick."""
        self.call_handlers('userRenamed', None, [oldname, newname])
        for channel in self.channel_names:
            if oldname in self.channel_names[channel]:
                self.channel_names[channel].discard(oldname)
                self.channel_names[channel].add(newname)

    def _join(self, channel):
        log.msg('Joining channel %s.' % channel)
        irc.IRCClient.join(self, channel)

    def join(self, channel):
        """Join the given *channel*.  If joins have been suspended with
        :py:meth:`suspend_joins`, add the channel to the join queue and
        actually join it when :py:meth:`resume_joins` is called."""
        # If joins are suspended, add this one to the queue; otherwise,
        # just go ahead and join the channel immediately.
        if self.suspended_joins is not None:
            log.msg('Joins suspended; adding channel %s to join queue.'
                     % channel)
            self.suspended_joins.add(channel)
            return

        self._join(channel)

    def leave(self, channel, reason=None):
        """Leave the given *channel*."""
        self.call_handlers('leave', channel, [channel, reason])
        self.channel_names[channel].clear()
        irc.IRCClient.leave(self, channel, reason)
    
    def kick(self, channel, nick, reason=None):
        """Kick the the given *nick* from the given *channel*."""
        self.call_handlers('kick', channel, [channel, nick, reason])
        irc.IRCClient.kick(self, channel, nick, reason)
        self.channel_names[channel].discard(nick)

    def topic(self, channel, topic=None):
        """Change the topic of *channel* if a *topic* is provided;
        otherwise, ask the IRC server for the current channel topic,
        which will be provided through the :py:meth:`topicUpdated`
        callback."""
        self.call_handlers('topic', channel, [channel, topic])
        irc.IRCClient.topic(self, channel, topic)
    
    def mode(self, chan, set, modes, limit=None, user=None, mask=None):
        """Change the mode of the given *channel*.  See `the Twisted
        documentation
        <http://twistedmatrix.com/documents/current/api/twisted.words.protocols.irc.IRCClient.html#mode>`_
        for information on this method's parameters."""
        self.call_handlers('mode', chan,
                           [chan, set, modes, limit, user, mask])
        irc.IRCClient.mode(self, chan, set, modes, limit, user, mask)
    
    # def say(...) is not necessary, as it simply delegates to msg().
    
    def msg(self, nick, message):
        """Send a message to the nickname or channel specified by
        *nick*."""
        self.call_handlers('msg', nick, [nick, message])
        irc.IRCClient.msg(self, nick, message)

    def notice(self, nick, message):
        """Send a notice to the nickname or channel specified by
        *nick*."""
        self.call_handlers('notice', nick, [nick, message])
        irc.IRCClient.notice(self, nick, message)
    
    def setNick(self, nickname):
        """Change the bot's nickname."""
        oldnick = self.nickname
        self.call_handlers('setNick', None, [nickname])
        irc.IRCClient.setNick(self, nickname)
        for channel in self.channel_names:
            if oldnick in self.channel_names[channel]: # sanity check
                self.channel_names[channel].discard(oldnick)
                self.channel_names[channel].add(nickname)
    
    def quit(self, message=''):
        """Quit from the IRC server."""
        self.call_handlers('quit', None, [message])
        irc.IRCClient.quit(self, message)
        self.channel_names = {}
    
    def me(self, channel, action):
        """Perform an action in the given *channel*."""
        self.call_handlers('me', channel, [channel, action])
        irc.IRCClient.me(self, channel, action)

    def irc_ERR_NICKNAMEINUSE(self, prefix, params):
        """Called when the bot attempts to use a nickname that is
        already taken by another user."""
        self.call_handlers('irc_ERR_NICKNAMEINUSE', self.nickname)
        irc.IRCClient.irc_ERR_NICKNAMEINUSE(self, prefix, params)

    def irc_JOIN(self, prefix, params):
        nick = prefix.split('!', 1)[0]
        channel = params[-1]
        if nick == self.nickname:
            self.joined(prefix, channel)
        else:
            self.userJoined(prefix, channel)

    def irc_PART(self, prefix, params):
        nick = prefix.split('!', 1)[0]
        channel = params[0]
        if nick == self.nickname:
            self.left(prefix, channel)
        else:
            self.userLeft(prefix, channel)

    def irc_QUIT(self, prefix, params):
        self.userQuit(prefix, params[0])

    # IRC methods not defined by t.w.p.irc.IRCClient

    def irc_PONG(self, prefix, secs):
        self.ping_count = 0
    
    def names(self, *channels):
        """Ask the IRC server for a list of nicknames in the given
        channels.  Plugins generally should not need to call this
        method, as it is automatically invoked on join."""
        for ch in channels:
            self.sendLine("NAMES " + ch)

    def irc_RPL_NAMREPLY(self, prefix, params):
        channel = params[2]
        names = params[3].split()
        self.namesArrived(channel, names)

    def irc_RPL_ENDOFNAMES(self, prefix, params):
        channel = params[1]
        self.endNames(channel)

    def namesArrived(self, channel, names):
        # Liberally strip out all user mode prefixes such as @%+.  Some
        # networks support more prefixes, so this removes any prefixes with
        # characters not valid in nicknames.
        names = map(lambda x: re.sub(r'^[^A-Za-z0-9\-\[\]\\`^{}]+', '', x),
                    names)
        self.channel_names[channel].update(names)

    def endNames(self, channel):
        self.call_handlers('endNames', channel, [channel])


class IRCClientFactory(protocol.ReconnectingClientFactory):
    """Creates :py:class:`.IRCClient` instances."""
    protocol = IRCClient

    # Stores the handler instances for each channel that we are connected to.  
    # Keys are channel names; values are an ordered list of handler instances 
    # to execute for each one.  "@" is a special key corresponding to handlers 
    # that should execute on private messages.
    handlers = {}

    # Stores the command instances for this bot.  Keys are the keywords used to 
    # invoke each command; values are the command instances themselves.
    commands = {}

    encoding = 'utf-8'
    
    http_cache_dir = None
    http_user_agent = ('%s/%s (bot; +%s)'
                        % (VERSION_NAME, VERSION_NUM, SOURCE_URL))

    def __init__(self, config):
        self.config = config
        self.encoding = self.config.getdefault('core', 'encoding',
                                               self.encoding)
        
        self.http_cache_dir = self.config.getdefault('core', 'http_cache_dir',
                                                     self.http_cache_dir)
        self.http_user_agent = self.config.getdefault('core',
                                                      'http_user_agent',
                                                      self.http_user_agent)

        # Set up the bot's SQLObject connection instance.
        sqlobject_uri = self.config.get('core', 'database')
        sqlobject.sqlhub.processConnection = \
          sqlobject.connectionForURI(sqlobject_uri)

        # Load handler plug-ins through twisted.plugin, then map handlers to 
        # channels based on the specified configuration options.
        found_handlers = {}

        for handler in getPlugins(iomnipresence.IHandler, plugins):
            handler.factory = self
            if hasattr(handler, 'registered'):
                getattr(handler, 'registered')()
            found_handlers[handler.name] = handler

        channels = self.config.options('channels')
        for channel in channels:
            handler_names = self.config.getspacelist('channels', channel)
            # Since "#" can't be used to start a line in the configuration file 
            # (it gets parsed as a comment by ConfigParser), add "#" to the 
            # beginning of any channel name that's not special (i.e. "@").
            if channel[0] not in irc.CHANNEL_PREFIXES and channel != '@':
                channel = '#' + channel
            channel = ircutil.canonicalize(channel)
            self.handlers[channel] = []
            for handler_name in handler_names:
                if handler_name: # ignore empty lists and list items
                    try:
                        self.handlers[channel].append(found_handlers[handler_name])
                    except KeyError:
                        log.err(None, 'Could not find handler with name "%s".'
                                       % handler_name)
                        raise

        # Load command plug-ins through twisted.plugin, then map commands to 
        # keywords based on the specified configuration options.
        found_commands = {}

        for command in getPlugins(iomnipresence.ICommand, plugins):
            command.factory = self
            if hasattr(command, 'registered'):
                getattr(command, 'registered')()
            found_commands[command.name] = command

        for (keyword, command_name) in self.config.items('commands'):
            # Force the keyword to lowercase.  This enables case-insensitive 
            # matching when parsing commands.
            keyword = keyword.lower()

            try:
                self.commands[keyword] = found_commands[command_name]
            except KeyError:
                log.err(None, 'Could not find command with name "%s".'
                               % command_name)
                raise

    def startedConnecting(self, connector):
        log.msg('Attempting to connect to server.')

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self

        p.nickname = self.config.get('core', 'nickname')

        # Optional instance variables for irc.IRCClient.
        p.password = self.config.getdefault('core', 'password', None)
        p.realname = self.config.getdefault('core', 'realname', None)
        p.username = self.config.getdefault('core', 'username', None)
        p.userinfo = self.config.getdefault('core', 'userinfo', None)

        return p

    # Not really sure where this belongs, since there are dependencies on 
    # configuration information.  Maybe yet another plugin infrastructure?
    def get_http(self, *args, **kwargs):
        """Make an :py:mod:`httplib2` :py:class:`~httplib2.Http` request
        with the given arguments, using the cache directory and
        user-agent string specified in the bot configuration file.
        
        By default, return this request wrapped in a Twisted
        :py:class:`~twisted.internet.defer.Deferred`.  If the *defer*
        keyword argument is passed and set to ``False``, simply return
        the result of the request as a ``(headers, content)`` tuple,
        without deferring to a thread.  This is useful in situations
        where :py:meth:`.get_http` is already being called from a
        separate thread created by
        :py:func:`twisted.internet.threads.deferToThread`.

        For further details, see the `httplib2 documentation
        <http://code.google.com/p/httplib2/wiki/Examples>`_.
        """
        h = httplib2.Http(self.http_cache_dir, 10.0)
        
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        if not 'User-Agent' in kwargs['headers']:
            kwargs['headers']['User-Agent'] = self.http_user_agent
        
        if 'defer' in kwargs:
            defer = kwargs['defer']
            del kwargs['defer']
        else:
            defer = True
        
        if defer:
            return threads.deferToThread(h.request, *args, **kwargs)

        return h.request(*args, **kwargs)
