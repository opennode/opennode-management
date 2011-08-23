#!/bin/sh
cd `dirname $0`
BRANCH=`git symbolic-ref HEAD | awk -F/ '{print $3}'`

if [ ! -z "$1" ]; then
    echo "Setting a branch specific db for branch $BRANCH: $1"
    git config branch.master.dbname "$1"
else
    DB_NAME=`git config branch.master.dbname`
    if [ -d "$DB_NAME" ]; then
        echo $DB_NAME
    else
        echo db
    fi
fi