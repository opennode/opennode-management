import os
from logging import DEBUG

from twisted.conch.checkers import SSHPublicKeyDatabase
from twisted.conch.ssh import keys
from twisted.python import log


class InMemoryPublicKeyCheckerDontUse(SSHPublicKeyDatabase):
    """Loads the public key from ~/.ssh/id_[rd]sa.pub at startup, and accepts logins for those keys
    Designed for testing, especially local testing.
    """

    def __init__(self):
        # Super is old-style class without constructor
        self.publicKey = None

    def checkKey(self, credentials):
        """Accepts any user name"""
        log.msg('Checking key for creds: %s' % credentials, system='ssh-pubkey', logLevel=DEBUG)
        home = os.environ["HOME"]
        with open('%s/.ssh/authorized_keys' % home) as f:
            for key in f:
                if self._checkKey(credentials, key):
                    log.msg('Check success, found matching key', system='ssh-pubkey', logLevel=DEBUG)
                    return True
        log.msg('Check failed: pubkey not found in authorized list', system='ssh-pubkey', logLevel=DEBUG)
        return False

    def _checkKey(self, credentials, key):
        try:
            return keys.Key.fromString(data=key).blob() == getattr(credentials, 'blob', None)
        except Exception:
            log.err(system='ssh-pubkey')
