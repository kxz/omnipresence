# -*- test-case-name: omnipresence.plugins.url.test_url
"""Event plugins for previewing the content of mentioned URLs."""


import re


# Based on django.utils.html.urlize from the Django project.
TRAILING_PUNCTUATION = ['.', ',', ':', ';', '.)', '"', "'", '!']
WRAPPING_PUNCTUATION = [('(', ')'), ('<', '>'), ('[', ']'),
                        ('"', '"'), ("'", "'")]
WORD_SPLIT_RE = re.compile(r'''([\s<>"']+)''')
SIMPLE_URL_RE = re.compile(r'^https?://\[?\w', re.IGNORECASE)


def extract_urls(text):
    """Return an iterator yielding URLs contained in *text*."""
    for word in WORD_SPLIT_RE.split(text):
        if not ('.' in word or ':' in word):
            continue
        # Deal with punctuation.
        lead, middle, trail = '', word, ''
        for punctuation in TRAILING_PUNCTUATION:
            if middle.endswith(punctuation):
                middle = middle[:-len(punctuation)]
                trail = punctuation + trail
        for opening, closing in WRAPPING_PUNCTUATION:
            if middle.startswith(opening):
                middle = middle[len(opening):]
                lead = lead + opening
            # Keep parentheses at the end only if they're balanced.
            if (middle.endswith(closing)
                    and middle.count(closing) == middle.count(opening) + 1):
                middle = middle[:-len(closing)]
                trail = closing + trail
        # Yield the resulting URL.
        if SIMPLE_URL_RE.match(middle):
            yield middle
