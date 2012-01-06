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
        "Twisted",
        "transaction",
        "zope.component",
        "zope.app.catalog",
        "zope.app.intid",
        "grokcore.component",
        "grokcore.security",
        "zope.securitypolicy",
        "ipython>=0.11",
        "ZODB3",
        "pycrypto",
        "pyOpenSSL",
        "pyasn1",
        "netaddr",
        "certmaster",
        "func",
        ],
)
