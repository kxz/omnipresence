.. highlight:: console

Installation
************

Omnipresence requires Python 2.7 or later.
There is no Python 3 support at this time.

We recommend installing Omnipresence through PyPI::

    $ pip install omnipresence[html]

If you have a source distribution::

    $ pip install -e .[html]

Some :doc:`built-in plugins <builtins>` have additional dependencies,
which are listed in their documentation and in requirements files inside
the plugin source directory.

Omnipresence is installed as an application plugin for twistd, which
handles daemonizing and logging.
The twistd command takes the location of the :doc:`bot settings
<settings>` file as its sole argument.
To run Omnipresence in the foreground and log to stdout, run::

    $ twistd -no omnipresence settings.yaml

To start Omnipresence as a daemon, writing its process ID to *pid* and
logging to the file *messages*, run::

    $ twistd -l messages --pidfile pid omnipresence settings.yaml

For full information on available options, consult the twistd man page.
