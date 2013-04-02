import logging
import logging.config
import os
import re

from twisted.python import log
from zope.component import getUtility
from zope.authentication.interfaces import IAuthentication

from opennode.oms.config import get_config


try:
    import yaml
except ImportError:
    yaml = None

try:
    import json
except ImportError:
    json = None


class OmsPythonLoggingObserver(log.PythonLoggingObserver):
    """Filter out unwanted log messages, especially during development."""

    def emit(self, eventDict):
        text = log.textFromEventDict(eventDict)

        if text is None:
            return

        if 'logLevel' in eventDict:
            level = eventDict['logLevel']
        elif eventDict['isError']:
            level = logging.ERROR
        else:
            level = logging.INFO

        self.logger.log(level, text, extra={'system': eventDict.get('system', '')})


class MessageRegexFilter(logging.Filter):
    """
    Filters logging records by excluding messages matching with banlist regexes
    """

    def __init__(self, banlist=[]):
        self.banlist = banlist

    def filter(self, record):
        if any([re.match(msgre, record.getMessage()) for msgre in self.banlist]):
            return False

        return True


class TwistedSystemFilter(logging.Filter):
    """
    Filters Twisted logging records by the extra system parameter (using a list of exclusions)
    """

    def __init__(self, banlist=[]):
        self.banlist = banlist

    def filter(self, record):
        if not hasattr(record, 'system'):
            return True

        if record.system in self.banlist:
            return False

        return True


def setup_logging():
    for filename in get_config_filenames():
        if os.path.exists(filename):
            load_config_in_varous_formats(filename)
            break
    else:
        config_defaults()

    logging.warn('Logging level is set to %s' %
                 logging.getLevelName(logging.getLogger('root').getEffectiveLevel()))

    observer = OmsPythonLoggingObserver()
    return observer.emit


def load_config_in_varous_formats(filename):
    if yaml is not None:
        try:
            s = yaml.load(open(filename, 'r').read())
        except:
            pass
        else:
            logging.config.dictConfig(s)
            return
    else:
        print 'YAML parsing capability is missing'

    if json is not None:
        try:
            s = json.load(open(filename, 'r'))
        except:
            pass
        else:
            logging.config.dictConfig(s)
            return
    else:
        print 'JSON parsing capability is missing'

    config_defaults()
    logging.config.fileConfig(filename, disable_existing_loggers=False)


def config_defaults():
    log_filename = get_config().get('logging', 'file')
    log_level = get_config().getstring('logging', 'level', 'INFO')

    default_ignored_messages = ['.*keepalive@openssh.com',
                                '.*POST .*/webterm',
                                '.*GET /favicon.ico',
                                '.*POST /+stream', '.*OPTIONS /',
                                '.*GET /plugins/onc/root/',
                                'got channel session request',
                                'channel open',
                                'remote close',
                                'sending close 0',
                                'disabling diffie-hellman-group-exchange because we cannot find moduli file']

    if log_filename == 'stdout':
        root_handlers = ['stderr']
    else:
        root_handlers = ['default']

    logging.config.dictConfig({
        'formatters': {
            'default': {'format': '%(asctime)s %(thread)x %(name)s %(levelname)s %(message)s'},
            'twisted': {'format': '%(asctime)s %(thread)x %(name)s %(levelname)s %(system)s %(message)s'}},
        'handlers': {'default': {'class': 'logging.handlers.WatchedFileHandler',
                                 'filename': log_filename,
                                 'formatter': 'default'},
                     'twisted': {'class': 'logging.handlers.WatchedFileHandler',
                                 'filename': log_filename,
                                 'formatter': 'twisted'},
                     'stderr': {'class': 'logging.StreamHandler', 'formatter': 'default'}},
        'filters': {
            'twisted-system': {'()': 'opennode.oms.log.TwistedSystemFilter',
                               'banlist': ['SSHServerTransport', 'SSHService']},
            'excluded-messages': {'()': 'opennode.oms.log.MessageRegexFilter',
                                  'banlist': default_ignored_messages}},
        'root': {'handlers': root_handlers, 'level': log_level},
        'loggers': {'twisted': {'level': 'INFO', 'handlers': ['twisted'], 'propagate': False,
                                'filters': ['twisted-system', 'excluded-messages']},
                    'txn': {'level': 'WARNING'},
                    'ZEO.zrpc': {'level': 'WARNING'},
                    'ZEO.ClientStorage': {'level': 'WARNING'},
                    'salt': {'level': 'WARNING'}},
        'version': 1,
        'disable_existing_loggers': False
    })


def get_config_filenames():
    return ['logging.conf', '~/.oms-logging.conf', '/etc/opennode/logging.conf']


class UserLogger(object):
    logger = logging.getLogger('opennode.oms.userlog')

    def __init__(self, principal=None, subject=None, owner=None):
        self.subject = subject
        self.owner = owner

        if principal is None:
            auth = getUtility(IAuthentication, context=None)
            self.principal = auth.getPrincipal('root')
        else:
            self.principal = principal

    def log(self, msg, *args, **kw):
        self.logger.log(logging.INFO, msg, *args,
                        extra={'username': self.principal.id if self.principal else '-',
                               'subject': self.subject or '-',
                               'owner': self.owner[0] if self.owner else '-'}, **kw)
