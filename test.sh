#!/bin/bash

if [ ! -z "$1" ] ; then
    tests="--tests opennode.oms.tests.test_$1"
fi

if [ ! -z "$2" ] ; then
    tests="$tests,opennode.oms.tests.test_$2"
fi

if [ ! -z "$3" ] ; then
    tests="$tests,opennode.oms.tests.test_$3"
fi

PATH=scripts:$PATH python setup.py nosetests --nologcapture --detailed-errors --nocapture $tests
