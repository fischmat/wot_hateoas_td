import os
import threading

import time

import subprocess


class FailureDetector(object):

    host = None

    port = None

    failure_callback = None

    failure_callback_called = False

    is_failed = False

    def __init__(self, netloc, failure_callback = None):
        """
        Initializes the failure detector.
        @type netloc tuple|str
        @param netloc The address and port of the host to check.
        Either tuple (hostname, port) or string 'hostname:port'
        @type failure_callback callable
        @param failure_callback Is called on failure. Gets this FD as single argument.
        """
        if isinstance(netloc, tuple) and isinstance(netloc[0], str) and isinstance(netloc[1], int):
            self.host = netloc[0]
            self.port = netloc[1]
        elif isinstance(netloc, str):
            split = netloc.split(':')
            try:
                self.host = split[0]
                self.port = int(split[1])
            except IndexError:
                raise ValueError('netloc must have format host:port')
        else:
            raise ValueError()
        if failure_callback:
            self.failure_callback = failure_callback



class PingFailureDetector(FailureDetector):

    def __init__(self, netloc, failure_callback=None, interval=200):
        super().__init__(netloc, failure_callback)
        self.interval = interval

        thread = threading.Thread(target=self._check, args=())
        thread.daemon = True
        thread.start()

    def _check(self):
        while True:
            try:
                with open(os.devnull, 'wb') as devnull:
                    subprocess.check_call(['ping', '-c', '1', self.host], stdout=devnull, stderr=subprocess.STDOUT)
                    self.is_failed = False
                    self.failure_callback_called = False
            except subprocess.CalledProcessError as e:
                self.is_failed = True

            if self.is_failed and self.failure_callback and not self.failure_callback_called:
                self.failure_callback(self)
                self.failure_callback_called = True
            time.sleep(self.interval/1000.0)