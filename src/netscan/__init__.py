import os

import subprocess

def _ping(host):
    try:
        with open(os.devnull, 'wb') as devnull:
            subprocess.check_call(['ping', '-c', '1', host], stdout=devnull, stderr=subprocess.STDOUT)
            return True
    except subprocess.CalledProcessError as e:
        return False

class NetworkScan(object):
    def scan(self):
        pass


class HostListScanner(NetworkScan):
    def __init__(self, hosts):
        self.__hosts = hosts

    def scan(self):
        return [h for h in self.__hosts if _ping(h)]
