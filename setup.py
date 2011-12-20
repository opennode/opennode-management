from setuptools import setup, find_packages


setup(
    name = "opennode.oms.core",
    version = "0.0",
    description = """OpenNode OMS""",
    author = "OpenNode Developers",
    author_email = "developers@opennodecloud.com",
    packages = find_packages(),
    namespace_packages = ['opennode'],
    entry_points = {'console_scripts': ['omsd = opennode.oms.daemon:run',
                                        'omspy = opennode.oms.pyshell:run']}
)
