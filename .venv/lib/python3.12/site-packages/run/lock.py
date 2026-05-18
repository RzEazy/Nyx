import fcntl
import sys

from run.base import AlreadyLocked

def lock(handle):
    '''
    Lock a file descriptor using ``fcntl`` locks.
    '''
    if not hasattr(handle, 'fileno'):
        handle = file(handle)
    if not fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB):
        raise AlreadyLocked(handle)

