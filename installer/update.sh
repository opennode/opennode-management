##!/bin/sh
cd $(dirname $0)
mkdir -p db eggnest
python bootstrap.py
bin/buildout
