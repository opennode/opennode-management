#!/bin/bash

DB=`./current_db_dir.sh`
mkdir -p $DB # just in case
runzeo -f $DB/data.fs -a $DB/socket > $DB/zeo.log 2>&1 &
twistd -ny opennode/oms.tac

trap "kill 0" SIGINT SIGTERM EXIT
