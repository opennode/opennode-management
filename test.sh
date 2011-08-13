#!/bin/bash

if [ ! -z "$1" ] ; then
    arg1="opennode.oms.tests.test_$1"
fi

if [ ! -z "$2" ] ; then
    arg2="opennode.oms.tests.test_$2"
fi

if [ ! -z "$3" ] ; then
    arg3="opennode.oms.tests.test_$3"
fi

nosetests --nologcapture --detailed-errors --nocapture $arg1 $arg2 $arg3
