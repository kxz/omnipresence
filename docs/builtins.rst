Built-in plugins
****************

.. module:: omnipresence.plugins

The following plugins are included in the Omnipresence distribution.


``.help``
=========

.. module:: omnipresence.plugins.help

Show detailed help for other commands, or list all available commands if
no argument is given.

:alice: help
:bot: Available commands: **alpha**, **beta**, **help**.
      For further help, use **help** *keyword*.
      To redirect a command reply to another user, use *command* **>**
      *nick*.
:alice: help alpha
:bot: **alpha** *argument* - Help for command **alpha**.


``.more``
=========

.. module:: omnipresence.plugins.more

Show additional text from a user's reply buffer.

:brian: count
:bot: 1
:brian: more
:bot: 2
:brian: more
:bot: 3

In public channels, an optional argument can be passed to view the
contents of another user's reply buffer.

:alice: count
:bot: alice: 1
:brian: more alice
:bot: brian: 2


``.anidb``
==========

.. module:: omnipresence.plugins.anidb

Look up an anime title on `AniDB`__.

__ http://anidb.net/

:alice: anidb bakemonogatari
:bot: http://anidb.net/a6327 —
      **Bakemonogatari** —
      TV Series, 12 episodes from 2009-07-03 to 2009-09-25 —
      rated 8.43 (7443)


``.dice``
=========

.. module:: omnipresence.plugins.dice

Manage dice pools.
The ``new``, ``add``, ``use``, and ``clear`` subcommands affect a
per-user bank of die rolls, while ``roll`` is used for one-off rolls
that should not be added to the bank.

:alice: dice new 4d6
:bot: Rolled **1 4 5 6** = 16.
      Bank now has **1 4 5 6** = 16.
:brian: dice new 4d6
:bot: Rolled **2 3 3 4** = 12.
      Bank now has **2 3 3 4** = 12.
:alice: dice
:bot: Bank has **1 4 5 6** = 16.
:alice: dice show brian
:bot: Bank has **2 3 3 4** = 12.
:brian: dice roll 2d20
:bot: Rolled **7 15** = 22.
:brian: dice use 3 3
:bot: Used **3 3** = 6. Bank now has **2 4** = 12.
:alice: dice clear
:bot: Bank cleared.


``.geonames``
=============

.. module:: omnipresence.plugins.geonames

The following plugins provide lookups backed by `GeoNames`__.
The ``geonames.username`` :ref:`settings variable <settings-variable>`
must be set to a valid GeoNames API username for them to function.

__ http://geonames.org/


``.geonames/Time``
------------------

Look up the current time in a world location.

:brian: time beijing
:bot: Beijing, Beijing, China (39.91, 116.40): 2015-08-14 11:10

If `pytz`__ is installed, case-sensitive tz database names are also
supported.

__ http://pythonhosted.org/pytz/

:alice: time UTC
:bot: UTC (tz database): 2015-08-14 03:10


``.geonames/Weather``
---------------------

Look up weather conditions in a world location.

:brian: weather london
:bot: London, England, United Kingdom (51.51, -0.13):
      19.0°C/66.2°F, broken clouds, 93% humidity
      from London City Airport (EGLC) as of 26 minutes ago


``.google``
===========

.. module:: omnipresence.plugins.google

Perform a Google search.
The ``google.key`` and ``google.cx`` :ref:`settings variables
<settings-variable>` must be set to valid Google Custom Search API
credentials.
For more information on setting up a Custom Search account, see the
Stack Overflow topic `"What are the alternatives now that the Google web
search API has been deprecated?"`__

__ http://stackoverflow.com/a/11206266

:alice: google far-out son of lung
:bot: https://en.wikipedia.org/wiki/Omnipresence —
      **Omnipresence - Wikipedia, the free encyclopedia**:
      **Omnipresence** or ubiquity is the property of being present
      everywhere.
      This property is most commonly used in a religious context as an
      attribute of a deity or ... (+147999 more)


``.vndb``
=========

.. module:: omnipresence.plugins.vndb

Look up a visual novel title on the `Visual Novel Database`__.

__ https://vndb.org/

:brian: vndb ever17
:bot: https://vndb.org/v17 —
      **Ever17 -The Out of Infinity-**,
      first release 2002-08-29 — rated 8.71 (3763) (+1 more)


``.wwwjdic``
============

.. module:: omnipresence.plugins.wwwjdic

Define a Japanese word or phrase using `Jim Breen's WWWJDIC`__.
If `Waapuro`__ is installed, Nihon-shiki romanizations are provided
alongside the kana spellings.

__ http://wwwjdic.org/
__ https://pypi.python.org/pypi/waapuro

:alice: wwwjdic kotoba
:bot: 言葉(P);詞;辞 [ことば (kotoba) (P); けとば (ketoba) (言葉)(ok)] (n)
      (1) (See 言語) language; dialect;
      (2) (See 単語) word; words; phrase; term; expression; remark;
      (3) speech; (manner of) speaking; (P) (+28 more)
