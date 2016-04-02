"""Raw message parser implementations."""
# pylint: disable=missing-docstring


from twisted.words.protocols.irc import ctcpExtract, parsemsg, X_DELIM

from . import Message
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

    def parse(self, connection, outgoing, raw, **kwargs):
        """Parse a raw IRC message string and return a corresponding
        `.Message` object.  Any keyword arguments override field values
        returned by the parser."""
        try:
            prefix, command, params = parsemsg(raw)
        except IndexError:
            parsed_kwargs = {'action': 'unknown'}
        else:
            parsed_kwargs = {'actor': Hostmask.from_string(prefix)}
            if command in self.functions:
                try:
                    parsed_kwargs['action'] = command.lower()
                    parsed_kwargs.update(
                        self.functions[command](command, params))
                except IndexError:
                    del parsed_kwargs['action']
            if 'action' not in parsed_kwargs:
                parsed_kwargs['action'] = 'unknown'
                parsed_kwargs['subaction'] = command
                splits = 2 if raw.startswith(':') else 1
                params = raw.split(None, splits)
                if len(params) > splits:
                    parsed_kwargs['content'] = params[splits]
                else:
                    parsed_kwargs['content'] = ''
        parsed_kwargs.update(kwargs)
        return Message(connection, outgoing, raw=raw, **parsed_kwargs)


#: A parser for the standard IRC version 2 protocol.
IRCV2_PARSER = RawMessageParser()

@IRCV2_PARSER.command('QUIT', 'NICK')
def parse_undirected_message(command, params):
    return {'content': params[0]}

@IRCV2_PARSER.command('TOPIC')
def parse_directed_message(command, params):
    return {'venue': params[0], 'content': params[1]}

@IRCV2_PARSER.command('PRIVMSG', 'NOTICE')
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

@IRCV2_PARSER.command('JOIN')
def parse_join(command, params):
    return {'venue': params[0]}

@IRCV2_PARSER.command('PART', 'MODE')
def parse_part_mode(command, params):
    return {'venue': params[0], 'content': ' '.join(params[1:])}

@IRCV2_PARSER.command('KICK')
def parse_kick(command, params):
    return {'venue': params[0], 'target': params[1], 'content': params[2]}
