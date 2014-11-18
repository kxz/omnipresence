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


setup(
    name='omnipresence',
    description='An IRC utility bot',
    version='2.4-dev',
    author='Kevin Xiwei Zheng',
    author_email='blankplacement+omnipresence@gmail.com',
    url='https://github.com/kxz/omnipresence',
    license='X11',
    packages=find_packages() + ['twisted.plugins'],
    package_data={
        'twisted': [
            'plugins/omnipresence_plugin.py']},
    install_requires=[
        'Twisted>=14.0.0',
        'pyOpenSSL',
        'service_identity',
        'sqlobject>=0.10'],
    extras_require={
        'html': [
            'beautifulsoup4']},
    tests_require=[
        'beautifulsoup4',
        'tox'],
    cmdclass={
        'test': Tox},
    zip_safe=False)
