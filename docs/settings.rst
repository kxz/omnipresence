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
down into individual connections and channels unless explicitly
overridden.
For example, given the configuration file::

    set foo: 12345
    connection initech:
        channel redstapler:
            set foo: 67890

the variable ``foo`` is assumed to have the value ``12345`` everywhere
except for the #redstapler channel on initech, where it is ``67890``.

The particular order of directives at the same nesting level does not
matter; in other words, there is no concept of "earlier" or "later" in
a file, only "shallower" and "deeper."
This means that the following configuration is equivalent to the last
one::

    connection initech:
        channel redstapler:
            set foo: 67890
    set foo: 12345

Avoid giving the same directive more than once inside a block.
The configuration parser may choose to use the value of either one
depending on the whims of the YAML parser.


.. _settings-connection:

Connections
===========

The ``connection`` directive specifies a connection to an IRC server.
It takes a single argument, an arbitrary string name (though special
characters may require that the directive be quoted)::

    connection example:
        host: irc.server.example
        port: 6697
        ssl: yes
        autojoin: yes

        set nickname: Omnipresence
        set username: omni
        set realname: Just another IRC bot
        set password: really_secret_111

    "connection '::: weird name'":
        host: irc.server.example

The ``host``, ``port``, and ``ssl`` directives are only valid directly
inside a ``connection`` block, and specify the hostname of the server,
the port to connect to, and whether to use SSL, respectively.
If the ``autojoin`` directive is set to false, Omnipresence does not
connect to the server when it is started.
This is useful for temporarily disabling a connection.
The ``host`` directive is mandatory; ``port`` defaults to 6667, ``ssl``
to false, and ``autojoin`` to true.

The following :ref:`variables <settings-variable>` also affect
connections:

* ``nickname`` is the bot's initial nickname.

* ``username`` is the username to use in the bot's hostmask if one is
  not provided by identd.

* ``realname`` is the bot's "real name," visible in WHOIS.

* ``password`` is the server password to use.

Unlike with the ``host``, ``port``, ``ssl``, and ``autojoin``
directives, these variables may also be specified at the root level,
where they cascade to any connections that do not override them.

It is an error to place a ``connection`` directive at any level of the
configuration file except the root.


.. _settings-channel:

Channels
========

The ``channel`` and ``private`` directives give settings specific to a
channel or direct messages for the bot, respectively::

    connection example:
        private:
            plugin .nickserv: on
        channel foo:
            plugin foo.specific: [foo]
        channel bar:
            autojoin: off

These directives are only valid directly inside a ``connection`` block,
and cause an error if placed anywhere else.

The ``channel`` directive takes the name of a channel as its sole
argument.
The ``#`` prefix is optional and is automatically added if no other
known channel prefix is present.
As ``#`` is also used to indicate comments in YAML, the directive must
be quoted if it is given::

    connection example:
        "channel #foo":
            plugin foo.specific: [foo]

Needless to say, leaving it off is generally easier.

As with connections, the ``autojoin`` directive inside a ``channel``
block controls whether Omnipresence joins that channel upon connecting
to the server.
The ``autojoin`` directive is meaningless inside ``private`` blocks, on
the other hand, and therefore it is an error to put one there.


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
Any value that evaluates to false disables the plugin.

.. warning::

   In Python, an empty list is considered false, so providing a list of
   no keywords for a plugin will disable it.


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
        connection example: hello world

(You should use :ref:`data blocks <settings-data>` instead of abusing
variable blocks to store arbitrary data for later reuse, however.)

To unset a variable, set it to `None` using a tilde character (``~``)::

    set rss.feeds: ~

In addition to the variables mentioned in :ref:`settings-connection`,
Omnipresence also understands the following:

* ``command_prefixes`` is a list of prefixes Omnipresence searches for
  in public channels to indicate a command.
  It has no default value.

* ``direct_addressing`` allows the bot's configured or current nickname,
  followed by a colon or a comma, to be a command prefix.
  It defaults to true.

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

    connection mercy:
        ignore no_google_for_you: off

The value is either Boolean `False`, or a mapping containing a
``hostmasks`` directive and at most one of ``include`` or ``exclude``.
The value of ``hostmasks`` is a list of hostmasks the ignore rule
applies to.
If ``include`` is given, its value is used as an exhaustive list of
plugins that should not respond to events from the given hostmasks.
Otherwise, all plugins except those given in ``exclude``, if present,
ignore those hostmasks.


.. _settings-data:

Data blocks
===========

The ``data`` directive opens a block that can store arbitrary data.
Its contents are not parsed at all::

    data:
        channel totalanarchy:
            connection thismakesnosense: hello world
        but_here_are_some_defaults: &defaults
            plugin .help: [h, help]
            plugin .more: [m, more]

This feature allows the use of YAML references to define repeated
configuration templates where they will explicitly not be parsed.
For example, the ``defaults`` value from the data block above can now be
used for specific channel settings::

    connection foo:
        channel bar:
            <<: *defaults
        channel baz:
            <<: *defaults
            plugin baz.plugin: [quux]
