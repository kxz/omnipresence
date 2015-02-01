.. highlight:: console

Installation
************

Omnipresence requires Python 2.7 or later.
There is no Python 3 support at this time.

Installation can be performed with the provided setup script::

    $ python setup.py install

The following dependencies should be automatically installed by the setup script:

* `Twisted <http://twistedmatrix.com/>`_ 14.0.0 or later
* `pyOpenSSL <http://pythonhosted.org/pyOpenSSL/>`_ and `service_identity <https://service-identity.readthedocs.org/>`_
* `SQLObject <http://sqlobject.org/>`_ 0.10 or later
* `Beautiful Soup <http://www.crummy.com/software/BeautifulSoup/>`_ 4

You will need to install an additional package to provide support for the specific database engine you wish to use.
For example, MySQL support is provided by the *mysql-python* package.
Some plugins have their own dependencies; consult the sample configuration in *docs/omnipresence.sample.cfg* for more details.

Omnipresence is installed as a Twisted application plugin executable through twistd, which handles daemonizing and logging.
The twistd command takes the location of the bot configuration file as its sole argument.
For example, to run Omnipresence in the foreground and log to stdout, use::

  $ twistd -no omnipresence omnipresence.cfg

The following command starts Omnipresence as a daemon, logging to the file *messages* and using the PID file *pid*::

  $ twistd -l messages --pidfile pid omnipresence omnipresence.cfg

For full information on the available options, consult the twistd documentation.
