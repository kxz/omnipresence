Built-in plugins
****************

.. module:: omnipresence.plugins

The following plugins are included in the Omnipresence distribution.

Some plugins have additional dependencies beyond what the Omnipresence
setup script automatically installs for you.
They are listed in the documentation below, and each such plugin in the
Omnipresence source distribution also has a :file:`requirements.txt`
file in its directory that can be used with `pip`__:

__ https://pip.pypa.io/

.. code-block:: console

   $ pip install -r omnipresence/plugins/url/requirements.txt


``.help``
=========

.. automodule:: omnipresence.plugins.help
   :members: Default


``.more``
=========

.. automodule:: omnipresence.plugins.more
   :members: Default


``.anidb``
==========

.. automodule:: omnipresence.plugins.anidb
   :members: Default


``.autorejoin``
===============

.. automodule:: omnipresence.plugins.autorejoin
   :members: Default


``.autovoice``
==============

.. automodule:: omnipresence.plugins.autovoice
   :members: Default


``.dice``
=========

.. automodule:: omnipresence.plugins.dice
   :members: Default


``.geonames``
=============

.. automodule:: omnipresence.plugins.geonames
   :members: Time, Weather


``.google``
===========

.. automodule:: omnipresence.plugins.google
   :members: Default


``.url``
========

.. automodule:: omnipresence.plugins.url
   :members: Default


``.vndb``
=========

.. automodule:: omnipresence.plugins.vndb
   :members: Default


``.wwwjdic``
============

.. automodule:: omnipresence.plugins.wwwjdic
   :members: Default
