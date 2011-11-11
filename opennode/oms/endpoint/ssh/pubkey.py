import os

from twisted.conch.checkers import SSHPublicKeyDatabase
from twisted.conch.ssh import keys


class InMemoryPublicKeyCheckerDontUse(SSHPublicKeyDatabase):
    """Loads the public key from ~/.ssh/id_[rd]sa.pub at startup, and accepts logins for those keys
    Designed for testing, especially local testing.
    """

    def __init__(self):
        # Super is old-style class without constructor
        self.publicKey = None

    def checkKey(self, credentials):
        """Accepts any user name"""

        home = os.environ["HOME"]
        with open('%s/.ssh/authorized_keys' % home) as f:
            for key in f:
                if self._checkKey(credentials, key):
                    return True
        return  False

    def _checkKey(self, credentials, key):
        return keys.Key.fromString(data=key).blob() == credentials.blob
