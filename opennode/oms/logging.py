import sys

from twisted.python.log import FileLogObserver


class FilteredLogFileObserver(FileLogObserver):
    """Filter out unwanted log messages, especially during development."""

    ignored_messages = ['keepalive@openssh.com', 'POST /terminal/', 'GET /favicon.ico', 'POST /stream', 'OPTIONS ']
    #ignored_systems = ['SSHServerTransport', 'SSHChannel']
    ignored_systems = ['SSHServerTransport']

    def emit(self, eventDict):

        system = eventDict.get('system', '')
        message = eventDict.get('message', '')
        if message:
            message = message[0]

        for msg in self.ignored_messages:
            if msg in message:
                return

        for s in self.ignored_systems:
            if system.startswith(s):
                return

        FileLogObserver.emit(self, eventDict)


def setup_logging():
    return FilteredLogFileObserver(sys.stdout).emit
