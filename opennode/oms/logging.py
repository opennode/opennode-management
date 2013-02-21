import re
import time
import threading

from twisted.python import failure
from twisted.python import log
from twisted.python import context


class ThreadInfoLogPublisher(log.LogPublisher):
    def __init__(self, oldpublisher):
        self.observers = oldpublisher.observers

    def msg(self, *message, **kw):
        """
        Log a new message, just like with twisted.python.log.msg, but record thread info as well.
        """
        if not context:
            return
        actualEventDict = (context.get(log.ILogContext) or {}).copy()
        actualEventDict.update(kw)
        actualEventDict['message'] = message
        actualEventDict['time'] = time.time()
        actualEventDict['thread'] = threading.current_thread()

        for i in range(len(self.observers) - 1, -1, -1):
            try:
                self.observers[i](actualEventDict)
            except KeyboardInterrupt:
                # Don't swallow keyboard interrupt!
                raise
            except UnicodeEncodeError:
                raise
            except:
                observer = self.observers[i]
                self.observers[i] = lambda event: None
                try:
                    self._err(failure.Failure(), "Log observer %s failed." % (observer,))
                except:
                    # Sometimes err() will throw an exception,
                    # e.g. RuntimeError due to blowing the stack; if that
                    # happens, there's not much we can do...
                    pass
                self.observers[i] = observer


# Monkeypatch Twisted log publisher
if not isinstance(log.theLogPublisher, ThreadInfoLogPublisher):
    log.theLogPublisher = ThreadInfoLogPublisher(log.theLogPublisher)
    log.msg = log.theLogPublisher.msg


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

        log.PythonLoggingObserver.emit(self, eventDict)
