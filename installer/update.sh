#!/bin/sh
DIR=$(dirname $0)
cd $DIR
mkdir -p db eggnest
python bootstrap.py --setup-source=$DIR/download-cache/ez_setup.py --download-base=$DIR/download-cache
bin/buildout
