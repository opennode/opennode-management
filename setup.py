#!/usr/bin/env python
from setuptools import setup, find_packages
from version import get_git_version


setup(
    name = "opennode.oms.core",
    version = get_git_version(),
    description = """OpenNode OMS""",
    author = "OpenNode Developers",
    author_email = "developers@opennodecloud.com",
    packages = find_packages(),
    namespace_packages = ['opennode'],
    entry_points = {'console_scripts': ['omsd = opennode.oms.daemon:run',
                                        'omspy = opennode.oms.pyshell:run']},
    install_requires = [
        "setuptools", # Redundant but removes a warning
        "Twisted==11.1.0",
        "transaction==1.2.0",
        "zope.component==3.12",
        "zope.app.catalog==3.8.1",
        "zope.app.intid==3.7.1",
        "grokcore.component==2.4",
        "grokcore.security==1.5",
        "zope.securitypolicy==3.7.0",
        "ipython>=0.11",
        "ZODB3==3.10.5",
        "pycrypto==2.4.1",
        "pyOpenSSL==0.13",
        "pyasn1==0.1.2",
        "netaddr==0.7.6",
        "certmaster==0.28",
        "func==0.28",
        ],
)
