# -*- coding: utf-8 -*-

import os
import re
import signal
from . import time

class Until(object):
    '''
    Time management class.
    '''

    RE_SECONDS  = re.compile(r'(\d+)[sS]?')
    RE_MINUTES  = re.compile(r'(\d+)[mM]')
    RE_HOURS    = re.compile(r'(\+?\d+)[hH]')
    RE_DAYS     = re.compile(r'(\+?\d+)[dD]')

    RE_TIME_CPU  = re.compile(r'[cC]')
    RE_TIME_WALL = re.compile(r'[wW]')

    def __init__(self,  timespec, timetype='wall'):
        assert timetype in ['cpu', 'wall'], 'Invalid timetype specified.'
        self.timespec = self.parse_timespec(timespec)
        self.timetype = timetype
        self.delay()

    @staticmethod
    def parse_timespec(timespec):
        '''
        Parse a time specification::

            >>> Until.parse_timespec('1m2s')
            62
            >>> Until.parse_timespec('2d')
            172800

        '''
        spec = 0
        
        test = Until.RE_SECONDS.search(timespec)
        if test: 
            spec += int(test.group(1))
        test = Until.RE_MINUTES.search(timespec)
        if test:
            spec += int(test.group(1)) * 60
        test = Until.RE_HOURS.search(timespec)
        if test:
            spec += int(test.group(1)) * 3600
        test = Until.RE_DAYS.search(timespec)
        if test:
            spec += int(test.group(1)) * 86400

        return spec

    def delay(self):
        '''
        Kill current process if ``self.timespec`` has passed.
        '''
        ppid = os.getpid()

        if self.timetype == 'cpu': # monitor CPU-times
            # initialise pipe for inter-process communications
            child, parent = os.pipe()

            # fork
            pid = os.fork()
            if pid == 0:
                def signal_info(*args):
                    '''
                    Handle the SIGINFO signal, reply with the current time
                    consumed by the process.
                    '''
                    times = str(sum(os.times()[:4]))
                    os.write(parent, times.ljust(32, '0'))
                
                signal.signal(signal.SIGHUP, signal_info)
            else:
                def signal_chld(*args):
                    '''
                    Handle the SIGCHLD signal, which kills the child.
                    '''
                    os._exit(0)

                signal.signal(signal.SIGCHLD, signal_chld)

                burnt = 0
                while burnt < self.timespec:
                    time.sleep(self.timespec)
                    os.kill(pid, signal.SIGHUP)
                    times = os.read(child, 32)
                    burnt = float(times)

                os.close(child)
                os.close(parent)
                os.kill(pid, signal.SIGTERM)
                os.kill(ppid, signal.SIGTERM)
                os._exit(1)

        else: # monitor wall clock time
            pid = os.fork()
            if not pid:
                return
            
            def signal_alrm(*args):
                '''
                Handle the SIGALARM signal, which kills the parent.
                '''
                os.kill(ppid, signal.SIGTERM)
                os._exit(1)

            signal.signal(signal.SIGALRM, signal_alrm)
            signal.alarm(self.timespec)
            os.wait()
            os._exit(0)

if __name__ == '__main__':
    tests = (
        ['1s',       1],
        ['1s2m',     121],
        ['1s2m3h',   10921],
        ['1s2m3h4d', 356521],
    )

    for i, o in tests:
        print(i, end=' ')
        s = Until.parse_timespec(i)
        print(s, end=' ')
        print(s == o)

    print('my pid:', os.getpid())
    print('allowing for 1s execution time')
    Until('1s', 'cpu')
    time.sleep(10)

