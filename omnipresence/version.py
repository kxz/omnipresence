"""Versioning functions for Omnipresence."""
import os.path
from subprocess import Popen, PIPE

BASE_VERSION = '2.0.0alpha3'

# With thanks to Douglas Creager <https://gist.github.com/300803>;
# command invocation ported from Git to Mercurial.
try:
    p = Popen(['hg', 'log',
               '-R', os.path.join(os.path.dirname(__file__), '..'),
               '-r', '.',
               '--template',
               '{latesttag}-{latesttagdistance}-{node|short}'],
              stdout=PIPE, stderr=PIPE)
    p.stderr.close()
    line = p.stdout.readlines()[0]
    VERSION_NUMBER = line.strip()
except:
    VERSION_NUMBER = BASE_VERSION
