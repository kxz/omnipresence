"""A raw message parser implementation for Message.from_raw()."""
# pylint: disable=missing-docstring


from twisted.words.protocols.irc import parsemsg, X_DELIM

from ..hostmask import Hostmask


class RawMessageParser(object):
    _optionals = ['venue', 'target', 'subaction', 'content']

    def __init__(self):
        self.functions = {}

    def command(self, *commands):
        """A decorator that registers a function as a parameter parser
        for messages of the types given in *commands*."""
        def decorator(function):
            for command in commands:
                self.functions[command] = function
            return function
        return decorator

    def parse(self, raw):
        """Return a dict representation of a raw IRC message string,
        in the form of keyword arguments for the :py:meth:`~.Message`
        constructor (sans *connection*)."""
        prefix, command, params = parsemsg(raw)
        kwargs = {field: None for field in self._optionals}
        kwargs['actor'] = Hostmask.from_string(prefix)
        if command in self.functions:
            kwargs['action'] = command.lower()
            kwargs.update(self.functions[command](params))
        else:
            kwargs['action'] = 'unknown'
            kwargs['subaction'] = command
            splits = 2 if raw.startswith(':') else 1
            kwargs['content'] = raw.split(None, splits)[splits]
        return kwargs


_parser = RawMessageParser()

@_parser.command('PRIVMSG', 'NOTICE')
def parse_privmsg(params):
    # Ignore CTCP messages.
    if params[1].startswith(X_DELIM):
        return None
    return {'venue': params[0], 'content': params[1]}

parse = _parser.parse
