#!/usr/bin/env python
from setuptools import setup, find_packages

from omnipresence.version import VERSION_NUMBER


setup(name='Omnipresence',
      version=VERSION_NUMBER,
      packages=find_packages() + ['twisted.plugins'],
      package_data={'twisted': 'plugins/omnipresence_plugin.py'},
      zip_safe=False,

      install_requires=['Twisted>=12.0.0',
                        'pyOpenSSL',
                        'sqlobject>=0.10',
                        'BeautifulSoup>=3.0',
                        'pytz',
                        'PIL==1.1.7'],

      # PIL on PyPI is packaged incorrectly.
      # <http://stackoverflow.com/questions/2485295#2486396>
      dependency_links=['http://dist.plone.org/thirdparty/'],

      author='Kevin Xiwei Zheng',
      author_email='blankplacement+omnipresence@gmail.com',
      description='An IRC utility bot',
      license='X11'
)
