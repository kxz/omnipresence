"""A raw message parser implementation for Message.from_raw()."""
# pylint: disable=missing-docstring


from twisted.words.protocols.irc import ctcpExtract, parsemsg, X_DELIM

from ..hostmask import Hostmask


class RawMessageParser(object):
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
        """Return a dict representation of a raw IRC message string, in
        the form of keyword arguments for the `.Message` constructor."""
        try:
            prefix, command, params = parsemsg(raw)
        except IndexError:
            return {'action': 'unknown'}
        kwargs = {'actor': Hostmask.from_string(prefix)}
        if command in self.functions:
            try:
                kwargs['action'] = command.lower()
                kwargs.update(self.functions[command](command, params))
            except IndexError:
                del kwargs['action']
        if 'action' not in kwargs:
            kwargs['action'] = 'unknown'
            kwargs['subaction'] = command
            splits = 2 if raw.startswith(':') else 1
            params = raw.split(None, splits)
            if len(params) > splits:
                kwargs['content'] = params[splits]
            else:
                kwargs['content'] = ''
        return kwargs


parser = RawMessageParser()

@parser.command('QUIT', 'NICK')
def parse_undirected_message(command, params):
    return {'content': params[0]}

@parser.command('TOPIC')
def parse_directed_message(command, params):
    return {'venue': params[0], 'content': params[1]}

@parser.command('PRIVMSG', 'NOTICE')
def parse_ctcpable_directed_message(command, params):
    kwargs = parse_directed_message(command, params)
    if params[1].startswith(X_DELIM):
        # CTCP extended message quoting is pathologically designed, but
        # nobody actually sends more than one at a time.  Thankfully.
        tag, data = ctcpExtract(params[1])['extended'][0]
        kwargs['content'] = data
        if tag.lower() == 'action':
            kwargs['action'] = 'action'
        else:
            kwargs['action'] = ('ctcpquery' if command == 'PRIVMSG'
                                else 'ctcpreply')
            kwargs['subaction'] = tag
    return kwargs

@parser.command('JOIN')
def parse_join(command, params):
    return {'venue': params[0]}

@parser.command('PART', 'MODE')
def parse_part_mode(command, params):
    return {'venue': params[0], 'content': ' '.join(params[1:])}

@parser.command('KICK')
def parse_kick(command, params):
    return {'venue': params[0], 'target': params[1], 'content': params[2]}

parse = parser.parse
