"""Reply buffering and chunking functions."""


from collections import Iterable, Iterator, Sequence
import itertools

from ..compat import length_hint
from . import DEFAULT_ENCODING
from .formatting import remove_formatting, unclosed_formatting


#: The length to chunk string command replies to, in bytes.
CHUNK_LENGTH = 256


def truncate_unicode(string, byte_limit, encoding=DEFAULT_ENCODING):
    """Truncate a Unicode *string* so that it fits within *byte_limit*
    when encoded using *encoding*.  Return the truncated string as a
    byte string."""
    # Per Denis Otkidach on SO <http://stackoverflow.com/a/1820949>.
    encoded = string.encode(encoding)[:byte_limit]
    return encoded.decode(encoding, 'ignore').encode(encoding)


def chunk(string, encoding=DEFAULT_ENCODING, max_length=CHUNK_LENGTH):
    """Return a list containing chunks of at most *max_length* bytes
    from *string*.  Breaks are made at whitespace instead of in the
    middle of words when possible.  If *string* is a Unicode string,
    it is converted to a byte string using *encoding* before calculating
    the byte length.

    Any mIRC-style formatting codes present in *string* are repeated at
    the beginning of each subsequent chunk until they are overridden or
    a newline is encountered.

    Omnipresence uses this function internally to perform command reply
    buffering, as the name implies.  Plugin authors should not need to
    call it themselves.
    """
    if not isinstance(string, basestring):
        raise TypeError('expected basestring, not ' + type(string).__name__)
    chunks = []
    remaining = string
    while remaining:
        if isinstance(remaining, unicode):
            # See if the encoded string is longer than the maximum
            # reply length by truncating it and then comparing it to
            # the original.  If so, place the rest in the buffer.
            truncated = truncate_unicode(remaining, max_length, encoding)
            if truncated.decode(encoding) == remaining:
                remaining = ''
            else:
                # Try and find whitespace to split the string on.
                truncated = truncated.rsplit(None, 1)[0]
                remaining = remaining[len(truncated.decode(encoding)):]
        else:
            # We don't have to be so careful about length comparisons
            # with byte strings; just use slice notation.
            if len(remaining) <= max_length:
                truncated = remaining
                remaining = ''
            else:
                truncated = remaining[:max_length].rsplit(None, 1)[0]
                remaining = remaining[len(truncated):]
        truncated = truncated.strip()
        remaining = ''.join(unclosed_formatting(truncated)) + remaining.strip()
        # If all that's left are formatting codes, there's basically no
        # real content remaining in the string.
        if not remove_formatting(remaining):
            remaining = ''
        chunks.append(truncated)
    return chunks


class ReplyBuffer(Iterator):
    """An iterator wrapping the :ref:`command reply <command-replies>`
    *response* for the invocation `.Message` *request*."""

    def __init__(self, response, request=None):
        if isinstance(response, ReplyBuffer):
            self.response = response.response
        elif isinstance(response, basestring):
            if request is None:
                encoding = DEFAULT_ENCODING
            else:
                encoding = request.encoding
            self.response = chunk(response, encoding)
        elif isinstance(response, (Iterable, Sequence)):
            self.response = response
        else:
            raise TypeError('invalid command reply type ' +
                            type(response).__name__)

    def next(self):
        if isinstance(self.response, Sequence):
            if not self.response:
                raise StopIteration
            reply_string = self.response[0]
            self.response = self.response[1:]
            return reply_string
        return next(self.response)

    def tee(self, num=2):
        """Return *num* independent reply buffers from this one, like
        `itertools.tee`, but without making unnecessary copies of the
        underlying response."""
        if isinstance(self.response, Sequence):
            return (ReplyBuffer(self.response),) * num
        return tuple(ReplyBuffer(t) for t in itertools.tee(self.response, num))

    def __length_hint__(self):
        return length_hint(self.response)

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, repr(self.response))
