#!/usr/bin/env python
from setuptools import setup, find_packages


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

      author='Kevin Xiwei Zheng',
      author_email='blankplacement+omnipresence@gmail.com',
      url='https://github.com/kxz/omnipresence',
      description='An IRC utility bot',
      license='X11'
)
