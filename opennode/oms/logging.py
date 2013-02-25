import logging
import re
from twisted.python import log


class FilteredPythonLoggingObserver(log.PythonLoggingObserver):
    """Filter out unwanted log messages, especially during development."""

    ignored_messages = ['.*keepalive@openssh.com', '.*POST .*/webterm', '.*GET /favicon.ico',
                        '.*POST /+stream', '.*OPTIONS /',
                        '.*GET /plugins/onc/root/',
                        'got channel session request', 'channel open', 'remote close', 'sending close 0',
                        'disabling diffie-hellman-group-exchange because we cannot find moduli file']
    ignored_systems = ['SSHServerTransport', 'SSHService']

    def emit(self, eventDict):
        system = eventDict.get('system', '')
        message = eventDict.get('message', '')
        if message:
            message = message[0]
        else:
            message = ''

        for msg in self.ignored_messages:
            if re.match(msg, message):
                return

        for s in self.ignored_systems:
            if system.startswith(s):
                return

        text = log.textFromEventDict(eventDict)

        if text is None:
            return

        if 'logLevel' in eventDict:
            level = eventDict['logLevel']
        elif eventDict['isError']:
            level = logging.ERROR
        else:
            level = logging.INFO
        text = log.textFromEventDict(eventDict)
        if text is None:
            return
        self.logger.log(level, text, extra={'system': eventDict.get('system', '')})
