"""Operations on Web resources."""


from .http import request
from .plugin import WebCommand

try:
    from .html import textify as textify_html
except ImportError:
    pass
