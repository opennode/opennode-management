#!/bin/bash

mkdir -p db # just in case
runzeo -f db/data.fs -a db/socket > db/zeo.log 2>&1 &
./twistd-autoreload.py -ny opennode/oms.tac

trap "kill 0" SIGINT SIGTERM EXIT
