#!/usr/bin/env python
import sys

from setuptools import setup, find_packages
from setuptools.command.test import test


class Tox(test):
    def finalize_options(self):
        test.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import tox
        errno = tox.cmdline(self.test_args)
        sys.exit(errno)


execfile('omnipresence/version.py')
setup(name='Omnipresence',
      version=__version__,
      packages=find_packages() + ['twisted.plugins'],
      package_data={'twisted': 'plugins/omnipresence_plugin.py'},
      zip_safe=False,

      install_requires=['Twisted>=12.0.0',
                        'pyOpenSSL',
                        'sqlobject>=0.10',
                        'beautifulsoup4'],
      tests_require=['tox'],

      cmdclass={'test': Tox},

      author='Kevin Xiwei Zheng',
      author_email='blankplacement+omnipresence@gmail.com',
      url='https://github.com/kxz/omnipresence',
      description='An IRC utility bot',
      license='X11'
)
