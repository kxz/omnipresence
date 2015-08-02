"""Run an interactive test session."""


import argparse
import sys

from twisted.internet import reactor
from twisted.python import log
from twisted.test.proto_helpers import StringTransport

from ..connection import ConnectionFactory, PRIVATE_CHANNEL
from ..settings import ConnectionSettings


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
        'settings_path', metavar='SETTINGS_PATH', nargs='?',
        help='path to Omnipresence settings file')
    args = parser.parse_args()
    factory = ConnectionFactory()
    if args.settings_path:
        with open(args.settings_path) as settings_file:
            factory.settings = ConnectionSettings.from_yaml(settings_file)
    protocol = factory.buildProtocol(('127.0.0.1', 6667))
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
