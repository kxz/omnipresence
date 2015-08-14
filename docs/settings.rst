.. highlight:: yaml

Configuration
*************

Omnipresence reads its configuration from a YAML file passed in on the
twistd command line:

.. code-block:: console

   $ twistd -no omnipresence settings.yaml

This page details the syntax and basic directives of configuration
files.
For information on the settings provided by Omnipresence's built-in
event plugins, see :doc:`builtins`.

.. seealso::

   The `Wikipedia article on YAML <https://en.wikipedia.org/wiki/YAML>`_
   gives a rundown of the basic structure and syntax of a YAML file.


Essentials
==========

A directive is made up of a command and associated value, which are
represented in the YAML format as a mapping key and value, respectively.
Each command is a string made up of an initial keyword and zero or more
arguments, which are parsed in a shell-like fashion (see `shlex.split`),
while the value's type depends on the directive.

The directives for :ref:`plugins <settings-plugin>`, :ref:`variables
<settings-variable>`, and :ref:`ignore rules <settings-ignore>` cascade
down into individual channels unless explicitly overridden.
For example, given the configuration file::

    set foo: 12345
    channel redstapler:
        set foo: 67890

the variable ``foo`` is assumed to have the value ``12345`` everywhere
except for the #redstapler channel, where it is ``67890``.

The particular order of directives at the same nesting level does not
matter; in other words, there is no concept of "earlier" or "later" in
a file, only "shallower" and "deeper."
This means that the following configuration is equivalent to the last
one::

    channel redstapler:
        set foo: 67890
    set foo: 12345

Avoid giving the same directive more than once inside a block.
The configuration parser may choose to use the value of either one
depending on the whims of the YAML parser.


.. _settings-connection:

Connections
===========

The following directives are only valid at the root of a configuration
file, and specify the details of the connection to the IRC server:

* ``host`` is the hostname of the server.
  This directive is mandatory.

* ``port`` is the port to connect to on the server.
  It defaults to 6667.

* ``ssl`` determines whether to use SSL.
  It defaults to `False`.

* ``nickname`` is the bot's initial nickname.
  It defaults to ``"Omnipresence"``.

* ``username`` is the username to use in the bot's hostmask if one is
  not provided by identd.
  It defaults to the value of ``nickname``.

* ``realname`` is the bot's "real name," visible in WHOIS.
  It has no default value.

* ``password`` is the server password to use.
  It has no default value.


.. _settings-channel:

Channels
========

The ``channel`` and ``private`` directives give settings specific to a
channel or direct messages for the bot, respectively::

    private:
        plugin .nickserv: on
    channel foo:
        plugin foo.specific: [foo]
    channel bar:
        enabled: off

Like the connection control directives, these directives are only valid
at the root of a configuration file.

The ``channel`` directive takes the name of a channel as its sole
argument.
The ``#`` prefix is optional and is automatically added if no other
known channel prefix is present.
As ``#`` is also used to indicate comments in YAML, the directive must
be quoted if it is given::

    "channel #foo":
        plugin foo.specific: [foo]

Needless to say, leaving it off is generally easier.

Inside a ``channel`` block, the value of the ``enabled`` directive
controls Omnipresence's automatic join and part behavior.
If it is true, the default for all explicitly configured channels, the
channel is automatically joined on bot start and configuration reload.
If false, the channel is not joined on bot start, and is parted from on
reload if the bot is present there.
If set to the string ``"soft"``, the default for all channels not
explicitly mentioned in the configuration, the channel is not joined on
bot start, but is not parted from on reload.


.. _settings-plugin:

Plugins
=======

The ``plugin`` directive enables or disables a plugin in the current
block and all blocks below it, unless overridden::

    plugin .rss: on
    plugin .wikipedia: [w, wp]
    plugin .wikipedia/Random: [wr]
    plugin foo.custom: [foo]

It takes the plugin's configuration name as its sole argument.
Names that begin with a period (``.``) refer to :doc:`built-in plugins
<builtins>`, while others are custom plugins provided by third-party
packages.
If a package provides multiple plugins, alternatives are available by
adding a slash and a second name (``/Random``).

The value is either a list of command keywords to use for plugins that
provide a command, or Boolean `True` or `False`.
`False` disables the plugin.


.. _settings-variable:

Variables
=========

The ``set`` directive sets the value of a configuration variable::

    set nickname: Omnipresence
    set google.key: 0123456789abcdef

It takes the name of the variable to set as its sole argument.
By convention, names not containing a period (``.``) are used for
Omnipresence core settings, while those with a period belong to plugins.
The value depends on the specific variable being set.
Note that Omnipresence does not parse directives inside variable blocks,
so the following configuration syntax is valid::

    set deliberately.unused.variable:
        channel example: hello world

(You should use :ref:`data blocks <settings-data>` instead of abusing
variable blocks to store arbitrary data for later reuse, however.)

To unset a variable, set it to `None` using a tilde character (``~``)::

    set rss.feeds: ~

The following variables affect Omnipresence's behavior:

* ``command_prefixes`` is a list of prefixes Omnipresence searches for
  in public channels to indicate a command.
  It has no default value.

* ``direct_addressing`` allows the bot's configured or current nickname,
  followed by a colon or a comma, to be a command prefix.
  It defaults to `True`.

* ``reply_format`` is a :ref:`format string <python:formatstrings>` used
  for replies to public channels.
  The strings ``{target}`` and ``{message}`` are replaced by the target
  nickname and content of the reply, respectively.
  The default is ``"\x0314{target}: {message}"``, which colors the
  response text gray.

* ``encoding`` is the name of a :ref:`Python character encoding
  <python:standard-encodings>` used to encode and decode messages.
  The default is ``"utf-8"``.


.. _settings-ignore:

Ignore rules
============

The ``ignore`` directive tells Omnipresence to not pass messages from
certain user hostmasks to certain plugins::

    ignore no_google_for_you:
        hostmasks: [*!*@foo.example]
        include: [google]
    ignore otherbots:
        hostmasks: [foobot, barbot]
        exclude: [.chanlog]

It takes an arbitrary name as its sole argument.
This name can be used in nested blocks to disable the ignore rule::

    channel mercy:
        ignore no_google_for_you: off

The value is either Boolean `False`, or a mapping containing a
``hostmasks`` directive and at most one of ``include`` or ``exclude``.
The value of ``hostmasks`` is a list of hostmasks the ignore rule
applies to.
If ``include`` is given, its value is used as an exhaustive list of
plugins that should not respond to events from the given hostmasks.
Otherwise, all plugins except those given in ``exclude``, if present,
ignore those hostmasks.
If more than one ignore rule applies to a particular user, any rules
with ``exclude`` take precedence over those with ``include``; in either
case, all values for each are combined.


.. _settings-data:

Data blocks
===========

The ``data`` directive opens a block that can store arbitrary data.
Its contents are not parsed at all::

    data:
        ignore totalanarchy:
            channel thismakesnosense: hello world
        but_here_are_some_defaults: &defaults
            plugin .help: [h, help]
            plugin .more: [m, more]

This feature allows the use of YAML references to define repeated
configuration templates where they will explicitly not be parsed.
For example, the ``defaults`` value from the data block above can now be
used for specific channel settings::

    channel bar:
        <<: *defaults
    channel baz:
        <<: *defaults
        plugin baz.plugin: [quux]


.. _settings-reload:

Reloading
=========

To reload the bot configuration, send a SIGUSR1 to the running process.
Omnipresence will join and part channels according to :ref:`the channel
configuration <settings-channel>`.
Changes to :ref:`connection directives <settings-connection>` are
ignored; they require a full restart of the bot.
