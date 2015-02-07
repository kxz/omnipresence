Built-in plugins
****************

.. module:: omnipresence.plugins

The following plugins are included in the Omnipresence distribution.

``.help``
=========

.. module:: omnipresence.plugins.help

Provides a command that shows detailed help for other commands, or lists
all available commands if no argument is given.

.. parsed-literal::

   <human> help
   -bot- Available commands: **alpha**, **beta**, **help**. For further help, use **help**
         *keyword*. To redirect a command reply to another user, use *command*
         **>** *nick*.
   <human> help alpha
   -bot- **alpha** *argument* - Help for command **alpha**.

``.more``
=========

.. module:: omnipresence.plugins.more

Provides a command that shows additional text from a user's reply
buffer.

.. parsed-literal::

   <human> count
   -bot- 1
   <human> more
   -bot- 2
   <human> more
   -bot- 3
