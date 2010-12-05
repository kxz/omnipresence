#!/usr/bin/env python
import os.path
from subprocess import Popen, PIPE

from setuptools import setup, find_packages

# With thanks to Douglas Creager <https://gist.github.com/300803>.
def call_git_describe(abbrev=4):
    try:
        p = Popen(['git', 'describe', '--abbrev=%d' % abbrev],
                  stdout=PIPE, stderr=PIPE)
        p.stderr.close()
        line = p.stdout.readlines()[0]
        return line.strip()
    except:
        return None


VERSION = call_git_describe()

if VERSION is None:
    VERSION = '2.0.0alpha2'

setup(name='Omnipresence',
      version=VERSION,
      packages=find_packages() + ['twisted.plugins'],
      package_data={'twisted': 'plugins/omnipresence_plugin.py'},
      zip_safe=False,

      install_requires=['Twisted>=8.2.0',
                        'pyOpenSSL',
                        'httplib2>=0.4.0',
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
