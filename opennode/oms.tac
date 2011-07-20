#!/usr/bin/env twistd -ny
from twisted.application import service, internet
from twisted.web import server

from opennode.oms.endpoint.httprest.root import HttpRestServer


def create_application():
    occi_server = HttpRestServer(authz_avatar=None)
    occi_site = server.Site(resource=occi_server)

    tcp_server = internet.TCPServer(8080, occi_site)
    # TODO: WebSocket endpoint

    application = service.Application("OpenNode Management Service")
    tcp_server.setServiceParent(application)

    return application


application = create_application()
