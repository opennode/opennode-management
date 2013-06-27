#!/bin/bash
while :
do
    date >> /var/log/runDevOms.log
    cd /opt/opennode-management && ./bin/omsd >> /var/log/runDevOms.log 2>&1
    test $? -gt 128 && break
    sleep 2
done
exit 0