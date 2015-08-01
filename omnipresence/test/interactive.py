"""Run an interactive test session."""


import argparse
import sys

from twisted.internet import reactor
from twisted.python import log
from twisted.test.proto_helpers import StringTransport

from ..connection import Connection, ConnectionFactory, PRIVATE_CHANNEL
from ..config import ConfigParser
from ..plugin import load_plugin
from .helpers import DummyFactory


PROLOGUE = [
    ':127.0.0.1 001 {0} :Welcome to the Internet Relay Chat Network {0}',
    ':127.0.0.1 002 {0} :Your host is 127.0.0.1[127.0.0.1/6667], running version dummy',
    ':127.0.0.1 003 {0} :This server was created Thu Jan 1 1970 at 00:00:00 UTC',
    ':127.0.0.1 004 {0} 127.0.0.1 dummy DQRSZagiloswz CFILPQTbcefgijklmnopqrstvz bkloveqjfI'
]


def interact(protocol):
    while True:
        try:
            msg = raw_input()
        except EOFError:
            reactor.callFromThread(reactor.stop)
            return
        if msg.startswith('/'):
            msg = msg[1:]
        else:
            msg = ':nick!u@h PRIVMSG {} :{}'.format(protocol.nickname, msg)
        reactor.callFromThread(protocol.lineReceived, msg)


def main():
    log.startLogging(sys.stderr, setStdout=False)
    parser = argparse.ArgumentParser(
        description=sys.modules[__name__].__doc__)
    parser.add_argument(
        'config_path', metavar='CONFIG_PATH', nargs='?',
        help='path to Omnipresence configuration file')
    parser.add_argument(
        '-p', '--event-plugin', metavar='NAME:KEYWORD', action='append',
        help='enable an event plugin with the given options')
    args = parser.parse_args()
    if args.config_path:
        config = ConfigParser()
        config.read(args.config_path)
        factory = ConnectionFactory(config)
    else:
        factory = DummyFactory()
    protocol = Connection(factory)
    for spec in args.event_plugin:
        name, _, keyword = spec.partition(':')
        keywords = keyword.split(',')
        protocol.add_event_plugin(load_plugin(name),
                                  {PRIVATE_CHANNEL: keywords})
    transport = StringTransport()
    # Total hack.  Should add formatting support sometime.
    transport.io = sys.stdout
    protocol.makeConnection(transport)
    for line in PROLOGUE:
        protocol.lineReceived(line.format(protocol.nickname))
    reactor.callInThread(interact, protocol)
    reactor.run()


if __name__ == '__main__':
    main()
