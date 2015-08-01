#!/usr/bin/env python
"""Install the optional dependencies of all built-in plugins."""


from glob import glob
from itertools import chain, repeat, izip
import os.path

import pip


def main():
    requirements = glob(os.path.join(
        os.path.dirname(__file__),
        '..', 'omnipresence', 'plugins', '*', 'requirements.txt'))
    args = ['install']
    for requirement in requirements:
        args.append('-r')
        args.append(requirement)
    pip.main(args)


if __name__ == '__main__':
    main()
