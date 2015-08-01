# -*- test-case-name: omnipresence.test.test_settings -*-
"""Operations on Omnipresence configuration files."""


import collections
import shlex

import yaml


def parse_key(key):
    """Split a key string into a tuple consisting of a command and a
    list of arguments.  Raise `ValueError` if the key is invalid."""
    try:
        args = shlex.split(key)
    except ValueError:
        raise ValueError('unparsable key: ' + key)
    try:
        command = args.pop(0)
    except IndexError:
        raise ValueError('empty key')
    return (command, args)


class ConnectionSettings(object):
    # XXX:  Docstring.

    def __init__(self):
        self.variables = {}  # mock without scope support

    @classmethod
    def from_dict(cls, dict_):
        if not isinstance(dict_, collections.Mapping):
            raise TypeError('settings must be a mapping, not ' +
                            type(settings_dict).__name__)

    @classmethod
    def from_yaml(cls, yaml_):
        """Return a new `.ConnectionSettings` object based on a YAML
        string or open file object pointing to a YAML file."""
        return cls(yaml.load(yaml_))

    def set_case_mapping(self, case_mapping):
        raise NotImplementedError

    # Core settings

    def autojoin_channels(self):
        """Return a list of channels to automatically join."""
        return []

    @property
    def server(self):
        raise NotImplementedError

    @property
    def port(self):
        raise NotImplementedError

    @property
    def ssl(self):
        raise NotImplementedError

    # Configuration variables

    def set(self, key, value, scope=None):
        """Set the configuration variable *key* to *value*."""
        self.variables[key] = value

    def get(self, key, scope=None, default=None):
        """Return the value of the configuration variable *key*, or
        *default* if it has not been set."""
        return self.variables.get(key, default)

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
