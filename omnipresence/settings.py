# -*- test-case-name: omnipresence.test.test_settings -*-
"""Operations on Omnipresence configuration files."""


import collections
import shlex

from twisted.words.protocols.irc import CHANNEL_PREFIXES

from . import mapping
from .hostmask import Hostmask
from .plugin import load_plugin


#: A sentinel "channel" used for direct messages to users.
PRIVATE_CHANNEL = '@'


def parse_directive(directive):
    """Split a directive into a tuple consisting of a command and a
    list of arguments.  Raise `ValueError` if the directive is invalid.
    """
    try:
        args = shlex.split(directive)
    except ValueError:
        raise ValueError('unparsable directive: ' + directive)
    try:
        command = args.pop(0)
    except IndexError:
        raise ValueError('empty directive')
    return (command, args)


def list_or_raise(obj, error_message):
    """If *obj* is a non-string iterable, return *obj*.  Otherwise,
    raise a `TypeError` with the given error message."""
    if (not isinstance(obj, collections.Sequence) or
            isinstance(obj, basestring)):
        raise TypeError('{}: {}'.format(error_message, obj))
    return obj


def pop_or_raise(args, missing_error, extra_error):
    """Pop a single argument from *args* and return it.  If there are
    zero or extra elements in *args*, raise a `ValueError` with message
    *missing_error* or *extra_error*, respectively."""
    try:
        arg = args.pop(0)
    except IndexError:
        raise ValueError(missing_error)
    if args:
        raise ValueError('{}: {}'.format(extra_error, ' '.join(args)))
    return arg


def scopes_for(message):
    """Return a list of potential scopes that may apply to *message*,
    from the most specific to the least specific."""
    if message is None:
        return [None]
    if message.private:
        return [PRIVATE_CHANNEL, None]
    if message.venue:
        return [message.venue, None]
    return [None]


#: A container for a list of hostmasks and a list of plugins to either
#: include or exclude from an ignore rule.
IgnoreRule = collections.namedtuple(
    'IgnoreRule', ('hostmasks', 'exclusive', 'plugins'))


class SettingsParser(object):
    """A parser that initializes a `ConnectionSettings` object according
    to a settings dictionary."""

    def __init__(self, settings):
        self.settings = settings

    def parse(self, dct):
        self.parse_scope(None, dct)

    def parse_scope(self, scope, dct):
        if not isinstance(dct, collections.Mapping):
            if scope is None:
                scope_str = 'connection'
            elif scope is PRIVATE_CHANNEL:
                scope_str = 'private messages'
            else:
                scope_str = scope
            raise TypeError('settings for {} must be a mapping, not {}'
                            .format(scope_str, type(dct).__name__))
        for directive, value in dct.iteritems():
            command, args = parse_directive(directive)
            try:
                parse_method = getattr(self, 'parse_{}'.format(command))
            except AttributeError:
                raise ValueError('invalid directive: {}'.format(directive))
            parse_method(scope, args, value)

    def parse_data(self, scope, args, value):
        pass

    def parse_set(self, scope, args, value):
        name = pop_or_raise(args, '"set" command without variable name',
                                  'too many arguments to "set" command')
        self.settings.set(name, value, scope=scope)

    def parse_ignore(self, scope, args, value):
        name = pop_or_raise(args, '"ignore" command without ignore name',
                                  'too many arguments to "ignore" command')
        if value is False:
            self.settings.unignore(name, scope=scope)
            return
        if not isinstance(value, collections.Mapping):
            raise TypeError('expected mapping for ignore rule "{}": {}'
                            .format(name, value))
        extra_keys = (frozenset(value) -
                      frozenset(['hostmasks', 'include', 'exclude']))
        if extra_keys:
            raise ValueError(
                'extraneous keys for ignore rule "{}": {}'
                .format(name, ', '.join(extra_keys)))
        if 'include' in value and 'exclude' in value:
            raise ValueError('both "include" and "exclude" specified '
                             'for ignore rule "{}"'.format(name))
        elif 'include' in value:
            plugins = list_or_raise(
                value['include'],
                'expected list of inclusions for ignore rule "{}"'.format(name))
        elif 'exclude' in value:
            plugins = list_or_raise(
                value['exclude'],
                'expected list of exclusions for ignore rule "{}"'.format(name))
        else:
            raise ValueError('neither "include" nor "exclude" '
                             'specified for ignore rule "{}"'.format(name))
        hostmasks = list_or_raise(
            value.get('hostmasks'),
            'expected list of hostmasks for ignore rule "{}"'.format(name))
        rule = IgnoreRule([Hostmask.from_string(h) for h in hostmasks],
                          'exclude' in value, plugins)
        self.settings.ignore(name, rule, scope=scope)

    def parse_plugin(self, scope, args, value):
        name = pop_or_raise(args, '"plugin" command without plugin name',
                                  'too many arguments to "plugin" command')
        # We deliberately check against False instead of using "if not"
        # because an empty list of keywords is falsy, but should still
        # enable the plugin.
        if value is False:
            self.settings.disable(name, scope=scope)
            return
        if value is True:
            value = []
        value = list_or_raise(value,
                              'expected list of keywords or boolean '
                              'for plugin "{}"'.format(name))
        self.settings.enable(name, keywords=value, scope=scope)

    # Connection directives

    def _parse_connection(self, command, scope, args, value):
        if scope:
            raise ValueError('"{}" command outside of root'.format(command))
        if args:
            raise ValueError('too many arguments to "{}" command: '
                             '{}'.format(command, ' '.join(args)))
        setattr(self.settings, command, value)

    def parse_host(self, scope, args, value):
        self._parse_connection('host', scope, args, value)

    def parse_port(self, scope, args, value):
        self._parse_connection('port', scope, args, value)

    def parse_ssl(self, scope, args, value):
        self._parse_connection('ssl', scope, args, value)

    def parse_nickname(self, scope, args, value):
        self._parse_connection('nickname', scope, args, value)

    def parse_password(self, scope, args, value):
        self._parse_connection('password', scope, args, value)

    def parse_realname(self, scope, args, value):
        self._parse_connection('realname', scope, args, value)

    def parse_username(self, scope, args, value):
        self._parse_connection('username', scope, args, value)

    def parse_userinfo(self, scope, args, value):
        self._parse_connection('userinfo', scope, args, value)

    # Channel directives

    def parse_channel(self, scope, args, value):
        name = pop_or_raise(args, '"channel" command without channel name',
                                  'too many arguments to "channel" command')
        if scope:
            raise ValueError('"channel" command outside of root')
        if not (name[0] in CHANNEL_PREFIXES or name is PRIVATE_CHANNEL):
            name = '#' + name
        self.settings.autojoin_channels.add(name)
        self.parse_scope(name, value)

    def parse_private(self, scope, args, value):
        if args:
            raise ValueError('too many arguments to "private" command: '
                             '{}'.format(' '.join(args)))
        self.parse_channel(scope, [PRIVATE_CHANNEL], value)

    def parse_enabled(self, scope, args, value):
        if args:
            raise ValueError('too many arguments to "enabled" command: '
                             '{}'.format(' '.join(args)))
        if not scope:
            raise ValueError('"enabled" command outside of channel')
        if scope is PRIVATE_CHANNEL:
            raise ValueError('"enabled" command inside "private" block')
        if value is False:
            self.settings.autojoin_channels.discard(scope)
            self.settings.autopart_channels.add(scope)
        elif value == 'soft':
            self.settings.autojoin_channels.discard(scope)


class ConnectionSettings(object):
    """A container for bot configuration options."""

    def __init__(self, *args, **kwargs):
        #: A dictionary mapping plugin names to plugin objects.
        #
        # This should persist even across configuration reloads, which
        # is why it's defined here and not in `replace`.
        self.loaded_plugins = {}
        self.replace(*args, **kwargs)

    def replace(self, dct=None, case_mapping=None):
        #: The `CaseMapping` used for channel name case folding.
        self.case_mapping = case_mapping or mapping.by_name('rfc1459')
        #: A `CaseMappedDict` mapping channel names to another dict of
        #: variable names and their values.
        self.variables = mapping.CaseMappedDict(
            case_mapping=self.case_mapping)
        #: A `CaseMappedDict` mapping channel names to another dict of
        #: ignore rule names and either an `IgnoreRule` object for
        #: enabled rules, or `False` for disabled rules.
        self.ignore_rules = mapping.CaseMappedDict(
            case_mapping=self.case_mapping)
        #: A `CaseMappedDict` mapping channel names to another dict of
        #: plugin objects and either a list of associated keywords for
        #: enabled plugins, or `False` for disabled plugins.
        self.plugin_rules = mapping.CaseMappedDict(
            case_mapping=self.case_mapping)
        #: The set of channels to automatically join after signing on.
        self.autojoin_channels = set()
        #: The set of channels to forcibly part from after signing on.
        self.autopart_channels = set()
        #: Connection details.
        self.host = None
        self.port = 6667
        self.ssl = False
        self.nickname = None
        self.password = None
        self.realname = None
        self.username = None
        self.userinfo = None
        # Let `SettingsParser` do its legwork.
        SettingsParser(self).parse(dct or {})

    # Configuration variables

    def set(self, name, value, scope=None):
        """Set the configuration variable *name* to *value*."""
        self.variables.setdefault(scope, {})[name] = value

    def get(self, name, message=None, default=None):
        """Return the value of the configuration variable *name*, or
        *default* if it has not been set."""
        for scope in scopes_for(message):
            value = self.variables.get(scope, {}).get(name)
            if value is not None:
                return value
        return default

    # Ignore rules

    def ignore(self, name, rule, scope=None):
        """Enable an ignore rule."""
        self.ignore_rules.setdefault(scope, {})[name] = rule

    def unignore(self, name, scope=None):
        """Disable the ignore rule with the given name."""
        # Same logic as for disabling plugins.
        self.ignore_rules.setdefault(scope, {})[name] = False

    # Plugins

    def enable(self, name, keywords=None, scope=None):
        """Enable a plugin and return the loaded plugin instance."""
        self.loaded_plugins.setdefault(name, load_plugin(name)())
        self.plugin_rules.setdefault(scope, {})[name] = keywords or []
        return self.loaded_plugins[name]

    def disable(self, name, scope=None):
        """Disable the given plugin."""
        # This is an explicit disabling, so we set `False` instead of
        # deleting the plugin key outright.
        self.plugin_rules.setdefault(scope, {})[name] = False

    def active_plugins(self, message=None):
        """Return a dict mapping enabled plugin objects to any keywords
        that have been specified for them."""
        plugin_rules = {}
        ignore_rules = {}
        for scope in reversed(scopes_for(message)):
            plugin_rules.update(self.plugin_rules.get(scope, {}))
            if message and message.actor:
                ignore_rules.update(self.ignore_rules.get(scope, {}))
        # Figure out which plugins should ignore this message, if any.
        exclusive = False
        plugins = set()
        if message and message.actor:
            for ignore_rule in ignore_rules.itervalues():
                if not ignore_rule:  # explicit False
                    continue
                if any(message.actor.matches(hostmask)
                       for hostmask in ignore_rule.hostmasks):
                    if ignore_rule.exclusive:
                        if not exclusive:
                            plugins.clear()
                        exclusive = True
                        plugins.update(ignore_rule.plugins)
                    elif not exclusive:
                        plugins.update(ignore_rule.plugins)
        return {self.loaded_plugins[name]: keywords
                for name, keywords in plugin_rules.iteritems()
                if not (plugin_rules[name] is False or
                        (exclusive and name not in plugins) or
                        (not exclusive and name in plugins))}

    def plugins_by_keyword(self, keyword, message=None):
        """Return a list of enabled plugin objects with the given
        keyword."""
        plugins = []
        for plugin, keywords in self.active_plugins(message).iteritems():
            if keyword in keywords:
                plugins.append(plugin)
        return plugins
