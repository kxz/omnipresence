# -*- test-case-name: omnipresence.test.test_plugin
"""Omnipresence event plugin framework."""


import importlib


#: The root package name to use for relative plugin module searches.
PLUGIN_ROOT = 'omnipresence.plugins'


class EventPlugin(object):
    """A container for callbacks that Omnipresence fires when IRC
    messages are received."""

    def __init__(self):
        self.callbacks = {}
        self.registered = None
        self.help = None

    def on(self, *actions):
        """Return a decorator that registers a function as a callback to
        be fired when this plugin receives a message with one of the
        :ref:`message types <message-types>` given in *actions*, with
        this plugin and a :py:class:`~.Message` object as positional
        parameters."""
        def decorator(function):
            for action in actions:
                self.callbacks[action] = function
            return function
        return decorator

    def on_configuration(self, settings):
        # XXX:  For a future configuration API.
        raise NotImplementedError

    def on_registration(self, function):
        """Register *function* as a callback to be fired when this
        plugin has been loaded, with this plugin and the current bot
        instance as positional parameters."""
        self.registered = function
        return function

    def on_help(self, function):
        """Register *function* as a callback to be fired when command
        help is requested using the ``help`` plugin, with this plugin,
        the command keyword, and any trailing arguments as positional
        arguments."""
        # XXX:  Maybe this should just be @plugin.on('cmdhelp').
        self.help = function
        return function


def load_plugin(name):
    """Load and return an :py:meth:`~.EventPlugin`, given the *name*
    used to refer to it in an Omnipresence configuration file."""
    module_name, _, member_name = name.partition('/')
    if not member_name:
        member_name = 'default'
    module = importlib.import_module(module_name, package=PLUGIN_ROOT)
    member = getattr(module, member_name)
    if not isinstance(member, EventPlugin):
        raise TypeError('{} is {}, not EventPlugin'.format(
            name, type(member).__name__))
    return member
