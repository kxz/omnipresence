"""Versioning functions for Omnipresence."""
import os.path
from subprocess import Popen, PIPE

__version__ = '2.2'

# With thanks to Douglas Creager <https://gist.github.com/300803>;
# command invocation ported from Git to Mercurial.
try:
    if os.path.basename(__file__) == 'setup.py':
        repository_root = os.path.dirname(__file__)
    else:
        repository_root = os.path.join(os.path.dirname(__file__), '..')
    p = Popen(['hg', 'log',
               '-R', repository_root,
               '-r', '.',
               '--template', '{latesttag}-{latesttagdistance}-{node|short}'],
              stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    __version__ = out.strip()
except:
    pass
