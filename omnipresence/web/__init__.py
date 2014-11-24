"""Utilities for retrieving and manipulating data from Web resources."""


from .http import request
from .plugin import WebCommand

__all__ = ['request', 'WebCommand']
