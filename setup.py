from setuptools import setup, find_packages


setup(
    name = "opennode.oms.core",
    version = "0.0",
    description = """OpenNode OMS""",
    author = "OpenNode Developers",
    author_email = "developers@opennodecloud.com",
    packages = find_packages(),
    namespace_packages = ['opennode', 'opennode.oms'],
    entry_points = {'console_scripts': ['omsd = opennode.oms.daemon:run',
                                        'omspy = opennode.oms.pyshell:run']},
    install_requires = [
        "Twisted",
        "storm",
        "transaction",
        "zope.component",
        "zope.app.catalog",
        "zope.app.intid",
        "grokcore.component",
        "grokcore.security",
        "zope.securitypolicy",
        "columnize",
        "ipython>=0.11",
        "ZODB3",
        "pycrypto",
        "pyOpenSSL",
        "pyasn1",
        "netaddr",
        ],

    setup_requires = [
        "nose",
        "mock",
        "coverage",
        "sphinx",
        ],

)
