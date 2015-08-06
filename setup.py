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
    version='3.0-dev',
    author='Kevin Xiwei Zheng',
    author_email='blankplacement+omnipresence@gmail.com',
    url='https://github.com/kxz/omnipresence',
    license='X11',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
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
            'test/data/*'],
        'twisted': [
            'plugins/omnipresence_plugin.py']},
    install_requires=[
        'Twisted>=14.0.0',
        'pyOpenSSL',
        'service_identity',
        'ipaddress',
        'PyYAML',
        'SQLObject>=0.10'],
    extras_require={
        'html': [
            'beautifulsoup4']},
    tests_require=[
        'stenographer',
        'tox'],
    cmdclass={
        'test': Tox},
    dependency_links=[
        'git+https://github.com/kxz/stenographer.git#egg=stenographer-0.1-dev'],
    zip_safe=False)
