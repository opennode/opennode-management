#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name = "opennode.wsproxy",
    version = "1.0",
    description = """Slightly customized version of wsproxy for better integration with opennode buildout environment""",
    author = "Joel Martin",
    author_email = "code.osuosl.org@martintribe.org",
    packages = find_packages(),
    entry_points = {'console_scripts': ['wsproxy = wsproxy:run']},
    install_requires = [
        "setuptools", # Redundant but removes a warning
        ],
)
