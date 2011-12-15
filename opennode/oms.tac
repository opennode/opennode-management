#!/usr/bin/env twistd -ny
from zope.interface import implements

from twisted.application import service, internet
from twisted.conch.insults import insults
from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm
from twisted.cred import portal
from twisted.cred.portal import IRealm, Portal
from twisted.python.log import ILogObserver
from twisted.web import server, guard, resource

from opennode.oms import setup_environ
from opennode.oms.endpoint.httprest.root import HttpRestServer
from opennode.oms.endpoint.ssh.protocol import OmsShellProtocol
from opennode.oms.logging import setup_logging
from opennode.oms.security.authentication import checkers


def create_http_server():
    rest_server = HttpRestServer(avatar=None)
    site = server.Site(resource=rest_server)
    tcp_server = internet.TCPServer(8080, site)

    return tcp_server


def create_ssh_server():
    def chainProtocolFactory():
        return insults.ServerProtocol(OmsShellProtocol)

    rlm = TerminalRealm()
    rlm.chainedProtocolFactory = chainProtocolFactory

    the_portal = portal.Portal(rlm)
    for ch in checkers:
        the_portal.registerChecker(ch)

    conch_factory = ConchFactory(the_portal)
    ssh_server = internet.TCPServer(6022, conch_factory)

    return ssh_server


def create_application():
    setup_environ()

    application = service.Application("OpenNode Management Service")

    create_http_server().setServiceParent(application)
    create_ssh_server().setServiceParent(application)
    # TODO: create_websocket_server().setServiceParent(application)

    return application


application = create_application()

application.setComponent(ILogObserver, setup_logging())
