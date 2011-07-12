# You can run this file directly with:
#    twistd -ny oms.tac

import os
from twisted.application import service, internet
from twisted.web import static, server

from opennode.oms.endpoint.occi.root import OCCI_server

def get_oms():
    """
    Return an instance of the OMS service. 
    """
    # OCCI-compliant endpoint
    occiServer = server.Site(resource=OCCI_server())
    # TODO: WebSocket endpoint    
    return internet.TCPServer(8080, occiServer)

# application object
application = service.Application("OpenNode Management Service")

# attach the service to its parent application
service = get_oms()
service.setServiceParent(application)
