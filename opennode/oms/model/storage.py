
class Storage():
    size = None # 1.1 GiB
    state = None # online | offline | backup | snapshot | resize | degraded

    def online(self):
        self.state = 'online'

    def offline(self):
        self.state = 'offline'

    def backup(self):
        self.state = 'backup'
        # on complete
        self.state = 'online'

    def snapshot(self):
        self.state = 'snapshot'
        # on complete
        self.state = 'online'

    def degrade(self):
        self.state = 'degrade'
        # on complete
        self.state = 'offline'
