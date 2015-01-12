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
#   Plugins are classes (not objects, *classes*) that are expected to
#   implement a zope.interface.
#
# - Decorators are pretty cool, don't you think?


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
