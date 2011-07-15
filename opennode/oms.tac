# You can run this file directly with:
#    twistd -ny oms.tac

import os

import sqlite3
from twisted.application import service, internet
from twisted.web import static, server

from opennode.oms.endpoint.occi.root import OCCIServer
from opennode.oms.db import DB_NAME, create_connection_pool


def create_application():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE TABLE compute (
                id        INTEGER PRIMARY KEY,
                name      TEXT,
                hostname  TEXT,
                ip        TEXT,
                category  TEXT
            )
            """
        )

        hosts = [
            (1, 'tomcat5-1', 'tomcat5-1.opennodecloud.com', '192.168.1.1', 'VM'),
            (2, 'tomcat5-2', 'tomcat5-2.opennodecloud.com', '192.168.1.2', 'VM'),
            (3, 'tomcat5-3', 'tomcat5-3.opennodecloud.com', '192.168.1.3', 'VM'),
            (4, 'drupal', 'drupal.opennodecloud.com', '192.168.1.4', 'CMS'),
        ]
        for t in hosts:
            cur.execute('INSERT INTO compute VALUES (?,?,?,?,?)', t)

        conn.commit()
    except:  # XXX: Should catch a DB specific Exception class here, catch-all is error-prone.
        # probably table already exists
        pass
    finally:
        cur.close()
        conn.close()

    # OCCI-compliant endpoint
    occi_server = OCCIServer(create_connection_pool())
    occi_site = server.Site(resource=occi_server)
    # TODO: WebSocket endpoint
    tcp_server = internet.TCPServer(8080, occi_site)

    application = service.Application("OpenNode Management Service")
    tcp_server.setServiceParent(application)

    return application


application = create_application()
