#!/bin/bash
DIR=$(dirname $0)
cd $DIR
mkdir -p db eggnest

PYTHON_VERSION=2.7.2

PYTHON=python2.7x

if [ -e bin/omsd ]; then
    PYTHON=$(head -n 1 bin/omsd | sed 's/^#!//')
fi

function install_pythonbrew() {
    echo "Installing a clean python 2.7 with pythonbrew"
    export PYTHONBREW_ROOT=~/.pythonbrew
    if [ ! -e "$PYTHONBREW_ROOT/bin/pythonbrew" ]; then
        curl -kL http://xrl.us/pythonbrewinstall | bash
    fi
    if $PYTHONBREW_ROOT/bin/pythonbrew list | grep -q $PYTHON_VERSION; then
        echo "Python2.7 python brew already installed, using it"
    else
        echo "Checking required libraries"
        if [ ! -e '/usr/include/bzlib.h' ]; then
            echo "Missing required bzip2 development libraries"
            DEB_REQ="$DEB_REQ libbz2-dev"
            RPM_REQ="$RPM_REQ bzip2-devel"
        fi
        if [ ! -e '/usr/include/gdbm.h' ]; then
            echo "Missing required gdbm development libraries"
            DEB_REQ="$DEB_REQ libgdbm-dev"
            RPM_REQ="$RPM_REQ gdbm-devel"
        fi
        if [ ! -z "$DEB_REQ" ]; then
            echo "Debian/ubuntu: apt-get install $DEB_REQ"
            echo "Redhat/centos: yum install $RPM_REQ"
            exit 1
        fi

        $PYTHONBREW_ROOT/bin/pythonbrew install --no-test $PYTHON_VERSION --configure="--enable-unicode=ucs4"
    fi

    PYTHON=$PYTHONBREW_ROOT/pythons/Python-$PYTHON_VERSION/bin/python
}

if [ "x$1" = "x--brew" ]; then
    install_pythonbrew
else
    if ! which $PYTHON; then
        echo -e "You don't have python 2.7 installed. You can automatically install python2.7 with pythonbrew and continue installation with:\n\n `pwd`/`basename $0` --brew"
        exit 1
    fi
fi

$PYTHON bootstrap.py --setup-source=$DIR/download-cache/ez_setup.py --download-base=$DIR/download-cache
bin/buildout
