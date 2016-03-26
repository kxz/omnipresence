# -*- test-case-name: omnipresence.test.test_plugin
"""Omnipresence event plugin framework."""

# A brief digression on why event plugins aren't Twisted plugins:
#
# - Twisted's plugin discovery is designed to find and import every
#   plugin found under the target package.  Such behavior is perfectly
#   reasonable when you really *are* looking for as many plugins as
#   possible, but not so much when you have explicit instructions from
#   the user on what plugins to enable.
#
# - Twisted handles import errors encountered during discovery by just
#   logging them and moving on.  It's not possible to implement more
#   sophisticated error handling without reimplementing large parts of
#   the plugin library.
#
# - The Twisted plugin API is far too Java-like for a Python library.
#   Plugin classes are expected to implement a zope.interface and are
#   instantiated exactly once.


import importlib

from twisted.internet.defer import maybeDeferred, succeed
from twisted.logger import Logger


#: The root package name to use for relative plugin module searches.
PLUGIN_ROOT = 'omnipresence.plugins'


class EventPluginMeta(type):
    """`~.EventPlugin`'s metaclass, used for name lookups."""

    @property
    def name(cls):
        """Return the configuration name of this plugin's class."""
        if cls.__name__ == 'Default':
            return cls.__module__
        return '{0.__module__}/{0.__name__}'.format(cls)


class EventPlugin(object):
    """A container for callbacks that Omnipresence fires when IRC
    messages are received."""

    __metaclass__ = EventPluginMeta

    log = Logger()

    def respond_to(self, msg):
        """Start any callback this plugin defines for *msg*.  Return a
        `Deferred` yielding its return value, or `None` if no callback
        exists for this message."""
        callback_name = 'on_' + msg.action.name
        if not hasattr(self, callback_name):
            return succeed(None)
        callback = getattr(self, callback_name)
        if msg.outgoing and not getattr(callback, 'outgoing', False):
            return succeed(None)
        self.log.debug('Passing message {msg} to {plugin} callback {name}',
                       msg=msg, plugin=type(self).name, name=callback_name)
        return maybeDeferred(callback, msg)


class SubcommandEventPlugin(EventPlugin):
    """A base class for command plugins that invoke subcommands given in
    the first argument by invoking one of the following methods:

    #. ``on_empty_subcommand(msg)``, if no arguments are present.  The
       default implementation raises a `UserVisibleError` asking the
       user to provide a valid subcommand.

    #. ``on_subcommand_KEYWORD(msg, remaining_args)``, if such a method
       exists.

    #. Otherwise, ``on_invalid_subcommand(msg, keyword,
       remaining_args)``, which by default raises an "unrecognized
       command" `UserVisibleError`.

    ``on_cmdhelp`` is similarly delegated to ``on_subcmdhelp`` methods:

    #. ``on_empty_subcmdhelp(msg)``, if no arguments are present.  The
       default implementation lists all available subcommands.

    #. ``on_subcmdhelp_KEYWORD(msg)``, if such a method exists.

    #. Otherwise, ``on_invalid_subcmdhelp(msg, keyword)``, which by
       default simply calls ``on_empty_subcmdhelp``.

    As with ``on_cmdhelp``, the subcommand keyword is automatically
    added to the help string, after the containing command's keyword and
    before the rest of the string.
    """

    @property
    def _subcommands(self):
        return sorted(name[14:] for name in dir(self)
                      if name.startswith('on_subcommand_'))

    def on_command(self, msg):
        args = msg.content.split(None, 1)
        if args:
            callback_name = 'on_subcommand_' + args[0]
            subargs = '' if len(args) < 2 else args[1]
            if hasattr(self, callback_name):
                return getattr(self, callback_name)(msg, subargs)
            return self.on_invalid_subcommand(msg, args[0], subargs)
        return self.on_empty_subcommand(msg)

    def on_cmdhelp(self, msg):
        if not msg.content:
            return self.on_empty_subcmdhelp(msg)
        callback_name = 'on_subcmdhelp_' + msg.content
        if hasattr(self, callback_name):
            return '\x02{}\x02 {}'.format(
                msg.content, getattr(self, callback_name)(msg))
        return self.on_invalid_subcmdhelp(msg, msg.content)

    def on_empty_subcommand(self, msg):
        raise UserVisibleError(
            'Please provide a subcommand: \x02{}\x02.'
            .format('\x02, \x02'.join(self._subcommands)))

    def on_empty_subcmdhelp(self, msg):
        return '\x02{}\x02'.format('\x02|\x02'.join(self._subcommands))

    def on_invalid_subcommand(self, msg, keyword, args):
        raise UserVisibleError(
            'Unrecognized subcommand \x02{}\x02. Valid subcommands: '
            '\x02{}\x02.'.format(
                keyword, '\x02, \x02'.join(self._subcommands)))

    def on_invalid_subcmdhelp(self, msg, keyword):
        return self.on_empty_subcmdhelp(msg)


def plugin_class_by_name(name):
    """Return an event plugin class given the *name* used to refer to
    it in an Omnipresence configuration file."""
    module_name, _, member_name = name.partition('/')
    if not member_name:
        member_name = 'Default'
    module = importlib.import_module(module_name, package=PLUGIN_ROOT)
    member = getattr(module, member_name)
    if not issubclass(member, EventPlugin):
        raise TypeError('{} is {}, not EventPlugin subclass'.format(
            name, type(member).__name__))
    return member


class UserVisibleError(Exception):
    """Raise this inside a command callback if you need to return an
    error message to the user, regardless of whether or not the
    ``show_errors`` configuration option is enabled.  Errors are always
    given as replies to the invoking user, even if command redirection
    is requested."""
