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
    description='The ominously-named friendly IRC bot framework',
    version='3.0alpha2',
    author='Kevin Xiwei Zheng',
    author_email='blankplacement+omnipresence@gmail.com',
    url='https://github.com/kxz/omnipresence',
    license='X11',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Twisted',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: Communications :: Chat :: Internet Relay Chat',
        'Topic :: Software Development :: Libraries :: Application Frameworks'],
    packages=find_packages() + ['twisted.plugins'],
    package_data={
        'omnipresence': [
            'test/fixtures/cassettes/*/*',
            'test/fixtures/settings/*'],
        'twisted': [
            'plugins/omnipresence_plugin.py']},
    install_requires=[
        'Twisted>=15.3.0',
        'pyOpenSSL',
        'service_identity',
        'ipaddress',
        'PyYAML',
        'enum34'],
    extras_require={
        'html': [
            'beautifulsoup4']},
    tests_require=[
        'tox'],
    cmdclass={
        'test': Tox},
    zip_safe=False)
