# -*- test-case-name: omnipresence.test.test_settings -*-
"""Operations on Omnipresence configuration files."""


import collections
import shlex

import yaml


def parse_key(key):
    """Split a key string into a tuple consisting of a command and a
    list of arguments.  Raise `.ConfigurationError` if the key is
    invalid."""
    try:
        args = shlex.split(key)
    except ValueError:
        raise ConfigurationError('unparsable key: ' + key)
    try:
        command = args.pop(0)
    except IndexError:
        raise ConfigurationError('empty key')
    return (command, args)


class ConnectionSettings(object):
    # XXX:  Docstring.

    def __init__(self, settings_dict):
        raise NotImplementedError

    def set_case_mapping(self, case_mapping):
        raise NotImplementedError

    # Core settings

    def autojoin_channels(self):
        """Return a list of channels to automatically join."""
        raise NotImplementedError

    # Configuration variables

    def set(self, key, value, scope=None):
        """Set the configuration variable *key* to *value*."""
        raise NotImplementedError

    def get(self, key, scope=None, default=None):
        """Return the value of the configuration variable *key*, or
        *default* if it has not been set."""
        raise NotImplementedError

    # Plugins

    def enable(self, name, scope=None):
        """Enable the given plugin."""
        raise NotImplementedError

    def disable(self, name, scope=None):
        """Disable the given plugin."""
        raise NotImplementedError

    def enabled(self, scope=None):
        """Return a dict mapping the names of enabled plugins to any
        keywords that have been specified for them."""
        raise NotImplementedError

    # Ignore rules

    def ignore(self, name, hostmask,
               include=None, exclude=None, scope=None):
        """Add an ignore rule with the given name for the given hostmask
        and plugin."""
        raise NotImplementedError

    def unignore(self, name, scope=None):
        """Remove the ignore rule with the given name.  Do nothing if no
        such rule exists."""
        raise NotImplementedError

    def ignores(self, hostmask, plugin_name, scope=None):
        """Return a bool indicating whether the given plugin should
        ignore events from *hostmask*."""
        raise NotImplementedError

    # def plugins_responding_to(self, msg): ...
    # take into account both enabled plugins and ignore rules

    # validation on bot start or reload:
    # (1) check that all plugins exist
    # (2) actually instantiate and attach plugin objects


class BotSettings(object):
    # XXX:  Docstring.

    def __init__(self, settings_dict):
        if not isinstance(settings_dict, collections.Mapping):
            raise TypeError('settings must be a mapping, not ' +
                            type(settings_dict).__name__)
        #: A mapping from connection names, as given in *settings_dict*,
        #: to `.ConnectionSettings` objects.
        self.connections = {}
        # Split the settings into global and connection-specific dicts.
        bot_dict = {}
        connections_dict = {}
        for key, value in settings_dict.iteritems():
            command, args = parse_key(key)
            if command != 'connection':
                bot_dict[key] = value
                continue
            try:
                connection_name = args.pop(0)
            except IndexError:
                raise ValueError(
                    '"connection" command without connection name')
            if args:
                raise ValueError(
                    'too many arguments to "connection" command: ' + key)
            connections_dict[connection_name] = value
        for name, connection_dict in connections_dict.iteritems():
            connection_dict.update(bot_dict)
            self.connections[name] = ConnectionSettings(connection_dict)

    @classmethod
    def from_yaml(cls, yaml_):
        """Return a new `.BotSettings` object based on a YAML string or
        open file object pointing to a YAML file."""
        return cls(yaml.load(yaml_))
