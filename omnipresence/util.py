"""General utility functions used within Omnipresence.

.. deprecated:: 2.4
    The majority of this module's functions have moved to the much more
    concretely named :py:mod:`~.humanize`.
"""


from .humanize import ago, andify, duration_to_timedelta, readable_duration
