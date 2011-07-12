# You can run this file directly with:
#    twistd -ny oms.tac

import os
from twisted.application import service, internet
from twisted.web import static, server

from opennode.oms.endpoint.occi.root import OCCIServer
from opennode.oms.db import DB_NAME, DBPool

def init_db():
    """ quick-n-dirty init """
    import sqlite3
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Create tables  
    try:
        # compute
        c.execute('''
            CREATE TABLE compute
            (
             id INTEGER PRIMARY KEY,
             name TEXT, 
             hostname TEXT, 
             ip TEXT,
             category TEXT
             )''')
        
        # Larger example
        for t in [(1, 'tomcat5-1', 'tomcat5-1.opennodecloud.com', "192.168.1.1", "VM"),
                  (2, 'tomcat5-2', 'tomcat5-2.opennodecloud.com', "192.168.1.2", "VM"),
                  (3, 'tomcat5-3', 'tomcat5-3.opennodecloud.com', "192.168.1.3", "VM"),
                  (4, 'drupal', 'drupal.opennodecloud.com', "192.168.1.4", "CMS"),
                ]:
            c.execute('INSERT INTO compute VALUES (?,?,?,?,?)', t)      
        
        # Save (commit) the changes
        conn.commit()
        # We can also close the cursor if we are done with it
        c.close()
    except:
        # probably table already exists
        c.close()

def get_oms():
    """
    Return an instance of the OMS service. 
    """
    # OCCI-compliant endpoint
    db_pool = DBPool()
    occiServer = server.Site(resource=OCCIServer(db_pool.get_connection()))
    # TODO: WebSocket endpoint    
    return internet.TCPServer(8080, occiServer)

# init db
init_db()

# application object
application = service.Application("OpenNode Management Service")

# attach the service to its parent application
service = get_oms()
service.setServiceParent(application)
