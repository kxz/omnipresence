from twisted.internet import defer, protocol, task
from twisted.plugin import getPlugins
from twisted.python import log
from twisted.words.protocols import irc

import platform
import sqlobject

from omnipresence import iomnipresence, plugins, util


VERSION_NAME = 'Omnipresence'
VERSION_NUM = '2.0.0test0'
VERSION_ENV = platform.platform()
SOURCE_URL = 'http://repo.or.cz/w/omnipresence.git'


class IRCClient(irc.IRCClient):
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
        # If suspended_joins is not None, then we've already suspended joins 
        # for this client, and we shouldn't clobber the queue.
        if self.suspended_joins is not None:
            return

        log.msg('Suspending channel joins.')
        self.suspended_joins = set()

    def resume_joins(self):
        if self.suspended_joins is None:
            return

        log.msg('Resuming channel joins.')

        for channel in self.suspended_joins:
            self._join(channel)

        self.suspended_joins = None

    def call_handlers(self, event, channel, args=[]):
        # If the channel doesn't start with an IRC channel prefix, treat the 
        # event as a private one.  Some networks send notices to "AUTH" when 
        # performing ident lookups, for example.
        if channel[0] not in irc.CHANNEL_PREFIXES:
            channel = '@'

        try:
            channel_handlers = self.factory.handlers[channel]
        except KeyError:
            # How'd we get in this channel?
            log.err(None, 'Received event for non-configured channel "%s".' % channel)
            return

        for handler in channel_handlers:
            if hasattr(handler, event):
                try:
                    getattr(handler, event)(self, *args)
                except:
                    log.err(None, 'Handler "%s" encountered an error.' % handler.name)

    def run_commands(self, user, channel, message):
        # First, see if the message matches any of the command prefixes 
        # specified in the configuration file.  We read directly from 
        # `self.factory.config` on every message, because the 
        # "current_nickname" default may change while the bot is being run.
        defaults = {'current_nickname': self.nickname}
        prefixes = self.factory.config.getspacelist('core',
                                                    'command_prefixes',
                                                    False, defaults)

        for prefix in prefixes:
            if message.lower().startswith(prefix.lower()):
                message = message[len(prefix):].strip()
                break
        else:
            # The message doesn't start with any of the given command prefixes.  
            # Continue command parsing if this is a private message; otherwise, 
            # bail out.
            if channel != self.nickname:
                return

        keyword = message.split()[0].lower()
        if keyword in self.factory.commands:
            try:
                self.factory.commands[keyword].execute(self, user, channel, message)
            except:
                log.err(None, 'Command "%s" encountered an error.' % keyword)

    def reply(self, user, channel, message):
        user = user.split('!', 1)[0]
        
        if channel == self.nickname:
            self.notice(user, message)
            return
        
        self.msg(channel, '\x0314%s' % message)

    # Inherited from twisted.internet.protocol.BaseProtocol

    def connectionMade(self):
        self.call_handlers('connectionMade', self.nickname)
        irc.IRCClient.connectionMade(self)
        log.msg('Connected to server.')

    # Inherited from twisted.internet.protocol.Protocol

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)
        log.msg('Disconnected from server.')

    # Inherited from twisted.words.protocols.irc.IRCClient
    # <http://twistedmatrix.com/documents/8.2.0/api/twisted.words.protocols.irc.IRCClient.html>

    def myInfo(self, servername, version, umodes, cmodes):
        # Once myInfo is called, we know which server we are connected to, so 
        # we can start performing keep-alive pings.
        self.ping_count = 0
        self.ping_timer = task.LoopingCall(self.ping_server, servername)
        self.ping_timer.start(60, False)

    def privmsg(self, user, channel, message):
        try:
            message = message.decode(self.factory.encoding)
        except UnicodeDecodeError:
            log.err(None, 'Could not decode message from %s on channel %s.'
                           % (user, channel))
            return

        if channel[0] not in irc.CHANNEL_PREFIXES:
            log.msg('Message from %s for %s: %s' % (user, channel, message))

        self.call_handlers('privmsg', channel, [user, channel, message])
        self.run_commands(user, channel, message)
        
    def noticed(self, user, channel, message):
        try:
            message = message.decode(self.factory.encoding)
        except UnicodeDecodeError:
            log.err(None, 'Could not decode notice from %s on channel %s.'
                           % (user, channel))
            return
        
        if channel[0] not in irc.CHANNEL_PREFIXES:
            log.msg('Notice from %s for %s: %s' % (user, channel, message))

        self.call_handlers('noticed', channel, [user, channel, message])

    def signedOn(self):
        log.msg('Successfully signed on to server.')
        self.call_handlers('signedOn', self.nickname)
        for channel in self.factory.config.options('channels'):
            # Skip over "@", which has a special meaning to the bot.
            if channel != '@':
                self.join(channel)

    def _join(self, channel):
        log.msg('Joining channel %s.' % channel)
        irc.IRCClient.join(self, channel)

    def join(self, channel):
        # If joins are suspended, add this one to the queue; otherwise, just go 
        # ahead and join the channel immediately.
        if self.suspended_joins is not None:
            log.msg('Joins suspended; adding channel %s to join queue.' % channel)
            self.suspended_joins.add(channel)
            return

        self._join(channel)

    def msg(self, user, message):
        self.call_handlers('msg', user, [user, message])

        try:
            message = message.encode(self.factory.encoding)
        except UnicodeEncodeError:
            log.err(None, 'Could not encode message to %s.' % user)
            return

        irc.IRCClient.msg(self, user, message)

    def notice(self, user, message):
        self.call_handlers('notice', user, [user, message])

        try:
            message = message.encode(self.factory.encoding)
        except UnicodeEncodeError:
            log.err(None, 'Could not encode notice to %s.' % user)
            return

        irc.IRCClient.notice(self, user, message)

    def irc_ERR_NICKNAMEINUSE(self, prefix, params):
        self.call_handlers('irc_ERR_NICKNAMEINUSE', self.nickname)
        irc.IRCClient.irc_ERR_NICKNAMEINUSE(self, prefix, params)

    # IRC methods not defined by t.w.p.irc.IRCClient

    def irc_PONG(self, user, secs):
        self.ping_count = 0


class IRCClientFactory(protocol.ReconnectingClientFactory):
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

    def __init__(self, config):
        self.config = config
        self.encoding = self.config.getdefault('core', 'encoding', self.encoding)

        # Set up the bot's SQLObject connection instance.
        sqlobject_uri = self.config.get('core', 'database')
        sqlobject.sqlhub.processConnection = sqlobject.connectionForURI(sqlobject_uri)

        # Load handler plug-ins through twisted.plugin, then map handlers to 
        # channels based on the specified configuration options.
        found_handlers = {}

        for handler in getPlugins(iomnipresence.IHandler, plugins):
            handler.factory = self
            found_handlers[handler.name] = handler

        channels = self.config.options('channels')
        for channel in channels:
            handler_names = self.config.getspacelist('channels', channel)
            # Since "#" can't be used to start a line in the configuration file 
            # (it gets parsed as a comment by ConfigParser), add "#" to the 
            # beginning of any channel name that's not special (i.e. "@").
            if channel[0] not in irc.CHANNEL_PREFIXES and channel != '@':
                channel = '#' + channel
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
        self.resetDelay()

        p = self.protocol()
        p.factory = self

        p.nickname = self.config.get('core', 'nickname')

        # Optional instance variables for irc.IRCClient.
        p.password = self.config.getdefault('core', 'password', None)
        p.realname = self.config.getdefault('core', 'realname', None)
        p.username = self.config.getdefault('core', 'username', None)
        p.userinfo = self.config.getdefault('core', 'userinfo', None)

        return p
