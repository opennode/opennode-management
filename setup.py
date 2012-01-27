#!/usr/bin/env python
from setuptools import setup, find_packages
from opennode.utils.version import get_git_version


setup(
    name = "opennode.oms.core",
    version = get_git_version(),
    description = """OpenNode OMS""",
    author = "OpenNode Developers",
    author_email = "developers@opennodecloud.com",
    packages = find_packages(),
    package_data={'opennode.oms': ['../oms.tac',
                                   '../../opennode-oms.conf',
                                   '../../oms_permissions',
                                   '../../oms_groups',
                                   ]},
    namespace_packages = ['opennode'],
    entry_points = {'console_scripts': ['omsd = opennode.oms.daemon:run',
                                        'omspy = opennode.oms.pyshell:run',
                                        'passwd = opennode.oms.security.passwd:run',
                                        'plugin = opennode.oms.plugin:run',
                                        'obj_graph = opennode.oms.tools.obj_graph:run',
                                        ]},
    install_requires = [
        "setuptools", # Redundant but removes a warning
        "winpdb",
        "Twisted==11.1.0",
        "pyasn1==0.1.2", # required by Twisted conch
        "transaction==1.2.0",
        "zope.component==3.12",
        "zope.app.catalog==3.8.1",
        "zope.app.intid==3.7.1",
        "grokcore.component==2.4",
        "grokcore.security==1.5",
        "grokcore.annotation==1.2",
        "zope.securitypolicy==3.7.0",
        "ipython>=0.11",
        "ZODB3==3.10.5",
        "pycrypto==2.4.1",
        "pyOpenSSL==0.13",
        "netaddr==0.7.6",
        "BeautifulSoup==3.2.0",
        ],
)
