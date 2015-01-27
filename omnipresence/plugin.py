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
import types


#: The root package name to use for relative plugin module searches.
PLUGIN_ROOT = 'omnipresence.plugins'


class EventPlugin(object):
    """A container for callbacks that Omnipresence fires when IRC
    messages are received."""

    def __init__(self):
        self.callbacks = {}

    def on(self, *actions):
        """Return a decorator that registers a function as a callback to
        be fired when this plugin receives a message with one of the
        :ref:`message types <message-types>` given in *actions*, with
        this plugin and a :py:class:`~.Message` object as positional
        parameters."""
        def decorator(function):
            # Make the callback behave like an instance method of this
            # object, such that calling ``self.callbacks[action](msg)``
            # implicitly inserts this object as the first argument.
            method = types.MethodType(function, self)
            for action in actions:
                self.callbacks[action] = method
            return function
        return decorator

    def respond_to(self, msg):
        """Fire any callbacks this plugin defines for *msg*."""
        if msg.action in self.callbacks:
            self.callbacks[msg.action](msg)


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
