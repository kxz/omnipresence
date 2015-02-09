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


.. _settings-variable:

Variables
=========


.. _settings-ignore:

Ignore rules
============
