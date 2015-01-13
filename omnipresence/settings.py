# -*- test-case-name: omnipresence.test.test_settings -*-
"""Configuration file parsing and representation."""


import yaml


class Settings(object):
    """Represents a bot's configuration."""

    def __init__(self, settings_dict):
        pass

    @classmethod
    def from_yaml(cls, yaml):
        """Return a new :py:class:`~.Settings` object based on a YAML
        string or open file object pointing to a YAML file."""
        return cls(yaml.load(yaml_file))

    @classmethod
    def from_v2_file(cls, config_file):
        """Return a new :py:class:`~.Settings` object based on an open
        file object pointing to an Omnipresence 2.x configuration file.
        """
        raise NotImplementedError

    # Core settings

    def connections(self):
        """Return a list of connection names."""
        raise NotImplementedError

    def channels(self, connection_name):
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
