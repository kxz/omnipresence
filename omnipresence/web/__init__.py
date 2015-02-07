"""Operations on Web resources."""


from .http import request

try:
    from .html import textify as textify_html
except ImportError:
    pass
