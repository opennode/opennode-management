#!/bin/sh

# Build a self-extracable installer for OMS. Relies on usage of https://github.com/megastep/makeself

# 1. Building:  sh scripts/build-installer.sh 
# 2. Verifying: parts/oms-core-installer.sh --list 

INSTALLER=parts/oms-core-installer.sh

rm -rf installer/oms_permissions installer/oms_roles
cp scripts/omsdrc installer/omsdrc

TMP=$(mktemp /tmp/oms-installer-XXXXXX)

makeself.sh --nox11 --notemp installer $TMP oms-core ./update.sh
sed -i 's/targetdir="installer"/targetdir="oms"/' $TMP

mv -vf $TMP $INSTALLER
