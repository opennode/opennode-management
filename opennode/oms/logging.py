import re
import sys

from twisted.python.log import FileLogObserver

from opennode.oms.config import get_config


class FilteredLogFileObserver(FileLogObserver):
    """Filter out unwanted log messages, especially during development."""

    ignored_messages = ['.*keepalive@openssh.com', '.*POST .*/webterm', '.*GET /favicon.ico', '.*POST /+stream', '.*OPTIONS ',
                        'got channel session request', 'channel open', 'remote close', 'sending close 0',
                        'disabling diffie-hellman-group-exchange because we cannot find moduli file']
    #ignored_systems = ['SSHServerTransport', 'SSHChannel']
    ignored_systems = ['SSHServerTransport', 'SSHService']

    def emit(self, eventDict):

        system = eventDict.get('system', '')
        message = eventDict.get('message', '')
        if message:
            message = message[0]

        for msg in self.ignored_messages:
            if re.match(msg, message):
                return

        for s in self.ignored_systems:
            if system.startswith(s):
                return

        FileLogObserver.emit(self, eventDict)


def setup_logging():
    log_filename = get_config().get('logging', 'file')
    if not log_filename or log_filename == 'stdout':
        log_file = sys.stdout
    else:
        log_file = open(log_filename, 'a')

    return FilteredLogFileObserver(log_file).emit
