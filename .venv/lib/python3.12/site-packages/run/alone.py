import os
import sys
from run import called_from
from run.base import AlreadyLocked
from run.lock import lock

filename = os.path.abspath(called_from())
try:
    lock(filename)
except AlreadyLocked:
    sys.stderr.write('A copy of %s is already locked\n' % (filename,))
    sys.exit(1)

