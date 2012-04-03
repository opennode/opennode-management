#!/usr/bin/env twistd -ny
from zope.interface import implements

from twisted.application import service, internet
from twisted.conch.insults import insults
from twisted.conch.manhole_ssh import ConchFactory
from twisted.cred import portal
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor
from twisted.python.log import ILogObserver
from twisted.web import server, guard, resource
from zope.component import handle

from opennode.oms.config import get_config
from opennode.oms.core import setup_environ, AfterApplicationInitalizedEvent
from opennode.oms.logging import setup_logging


def create_http_server():
    from opennode.oms.endpoint.httprest.root import HttpRestServer

    rest_server = HttpRestServer(avatar=None)
    site = server.Site(resource=rest_server)
    tcp_server = internet.TCPServer(get_config().getint('rest', 'port'), site)

    return tcp_server


def create_ssh_server():
    from opennode.oms.endpoint.ssh.protocol import OmsShellProtocol
    from opennode.oms.endpoint.ssh.session import OmsTerminalSession, OmsTerminalRealm
    from opennode.oms.security.authentication import checkers


    def chainProtocolFactory():
        return insults.ServerProtocol(OmsShellProtocol)

    the_portal = portal.Portal(OmsTerminalRealm())

    for ch in checkers():
        the_portal.registerChecker(ch)

    conch_factory = ConchFactory(the_portal)
    ssh_server = internet.TCPServer(get_config().getint('ssh', 'port'), conch_factory)

    return ssh_server


def create_application():
    setup_environ()

    from opennode.oms.endpoint.httprest.root import HttpRestServer
    from opennode.oms.endpoint.ssh.protocol import OmsShellProtocol
    from opennode.oms.endpoint.ssh.session import OmsTerminalSession, OmsTerminalRealm
    from opennode.oms.security.authentication import checkers


    application = service.Application("OpenNode Management Service")

    create_http_server().setServiceParent(application)
    create_ssh_server().setServiceParent(application)
    # TODO: create_websocket_server().setServiceParent(application)

    def after_startup():
        handle(AfterApplicationInitalizedEvent())
    reactor.addSystemEventTrigger('after', 'startup', after_startup)

    return application


application = create_application()

application.setComponent(ILogObserver, setup_logging())
