from twisted.enterprise import adbapi


DB_NAME = 'oms.db'


class DBPool():
    dbpool = None

    def get_connection(self):
        import sqlite3
        sqlite3.enable_callback_tracebacks(True)
        if self.dbpool is None:
            self.dbpool = adbapi.ConnectionPool('sqlite3', DB_NAME, cp_max=50, cp_noisy=True, check_same_thread=False)
        return self.dbpool
