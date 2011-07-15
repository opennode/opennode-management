import sqlite3

from twisted.enterprise import adbapi


DB_NAME = 'oms.db'

sqlite3.enable_callback_tracebacks(True)


def create_connection_pool():
    return adbapi.ConnectionPool(
        'sqlite3', DB_NAME,
        cp_max=50,
        cp_noisy=True,
        check_same_thread=False
    )
