import sys

from twisted.python.log import ILogObserver, FileLogObserver

class FilteredLogFileObserver(FileLogObserver):
    """Filter out unwanted log messages, especially during development."""

    ignored_messages = ['keepalive@openssh.com', 'POST /terminal/management', 'GET /favicon.ico']
    ignored_systems = ['SSHServerTransport', 'SSHChannel']

    def emit(self, eventDict):

        system = eventDict.get('system','')
        message = eventDict.get('message','')
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
