import inspect
from run.time import Until

def called_from():
    '''
    Ask the stack what module is calling.
    '''
    stack = inspect.stack()
    try:
        return stack[2][1]
    finally:
        del stack

def until(timespec, timetype='wall'):
    '''
    Run until a specified timespec, if the process runs
    longer, it will be killed:

        >>> import run
        >>> run.until('23m42s')
        >>> ...

    You can also choose to limit on the amount of CPU-time
    being consumed (default is wall clock time):

        >>> run.until('42s', 'cpu')
    '''
    Until(timespec, timetype)
