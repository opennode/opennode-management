#!/bin/sh

python setup.py develop
scripts/sphinx-apidoc -o doc/gen opennode
python setup.py build_sphinx