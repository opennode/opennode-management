from twisted.conch.checkers import SSHPublicKeyDatabase
from twisted.conch.ssh import keys

import os

class InMemoryPublicKeyCheckerDontUse(SSHPublicKeyDatabase):
    """Loads the public key from ~/.ssh/id_[rd]sa.pub at startup, and accepts logins for those keys
    Designed for testing, especially local testing.
    """

    def __init__(self):
        # Super is old-style class without constructor
        self.publicKey = None

        home = os.environ["HOME"]
        for pubkey in ["id_dsa.pub", "id_rsa.pub"]:
            name = "%s/.ssh/%s" % (home, pubkey)
            if os.path.exists(name):
                f = open(name, 'r')
                self.publicKey = f.read()
                break

    def checkKey(self, credentials):
        """Accepts any user name"""
        if not self.publicKey:
            return False
        return keys.Key.fromString(data=self.publicKey).blob() == credentials.blob
