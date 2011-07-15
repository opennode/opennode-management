# You can run this file directly with:
#    twistd -ny oms.tac

import os

import sqlite3
from twisted.application import service, internet
from twisted.web import static, server

from opennode.oms.endpoint.occi.root import OCCIServer
from opennode.oms.db import DB_NAME, create_connection_pool


def create_application():
    # OCCI-compliant endpoint
    authz_avatar = None
    occi_server = OCCIServer(authz_avatar)
    occi_site = server.Site(resource=occi_server)

    tcp_server = internet.TCPServer(8080, occi_site)
    # TODO: WebSocket endpoint

    application = service.Application("OpenNode Management Service")
    tcp_server.setServiceParent(application)


    return application


application = create_application()
