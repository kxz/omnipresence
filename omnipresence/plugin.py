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


from collections import defaultdict
import importlib
import types

from twisted.internet.defer import maybeDeferred, succeed
from twisted.python import log


#: The root package name to use for relative plugin module searches.
PLUGIN_ROOT = 'omnipresence.plugins'


class EventPluginMeta(type):
    """:py:class:`~.EventPlugin`'s metaclass."""

    def __new__(cls, clsname, bases, dct):
        #: A mapping of actions to ``(callback, options)`` tuples.
        dct['_callbacks'] = {}
        return super(EventPluginMeta, cls).__new__(cls, clsname, bases, dct)

    @property
    def name(cls):
        """Return this plugin's configuration name."""
        if cls.__name__ == 'Default':
            return cls.__module__
        return '{0.__module__}/{0.__name__}'.format(cls)


class EventPlugin(object):
    """A container for callbacks that Omnipresence fires when IRC
    messages are received."""

    __metaclass__ = EventPluginMeta

    def __init__(self, bot):
        pass

    @classmethod
    def register(cls, callback, *actions, **options):
        """Register *callback* to be fired when an instance of this
        plugin receives a message with one of the :ref:`message types
        <message-types>` in *actions*, with a :py:class:`~.Message`
        object as the sole parameter.  By default, outgoing messages
        from the bot are ignored unless the *outgoing* keyword argument
        is true."""
        for action in actions:
            cls._callbacks[action] = (callback, options)

    def respond_to(self, msg):
        """Start any callbacks this plugin defines for *msg*, and return
        a :py:class:`twisted.internet.defer.Deferred`."""
        if msg.action in self._callbacks:
            callback, options = self._callbacks[msg.action]
            if msg.outgoing and not options.get('outgoing'):
                return succeed(None)
            # Bind the callback back to this plugin object.
            method = types.MethodType(callback, self)
            deferred = maybeDeferred(method, msg)
            deferred.addErrback(log.err,
                                'Error in plugin %s responding to %s'
                                % (self.__class__.name, msg))
            return deferred
        return succeed(None)


def on(*actions, **options):
    def decorator(function):
        function.register_for = (actions, options)
        return function
    return decorator


def load_plugin(name):
    """Load and return an event plugin class, given the *name* used to
    refer to it in an Omnipresence configuration file."""
    module_name, _, member_name = name.partition('/')
    if not member_name:
        member_name = 'Default'
    module = importlib.import_module(module_name, package=PLUGIN_ROOT)
    member = getattr(module, member_name)
    if not issubclass(member, EventPlugin):
        raise TypeError('{} is {}, not EventPlugin subclass'.format(
            name, type(member).__name__))
    return member
