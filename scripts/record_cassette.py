"""Record an HTTP interaction in JSON-serialized VCR cassette format."""


import os.path
import sys

from betamax import Betamax
from requests import Session

from omnipresence.web.http import USER_AGENT


def main():
    with Betamax.configure() as config:
        config.cassette_library_dir = '.'

    session = Session()
    session.headers['User-Agent'] = USER_AGENT
    cassette_path = os.path.splitext(sys.argv[-1])[0]
    with Betamax(session).use_cassette(cassette_path):
        for uri in sys.argv[1:-1]:
            session.get(uri).content


if __name__ == '__main__':
    main()
