#!/bin/sh
INSTALLER=parts/oms-core-installer.sh

TMP=$(mktemp /tmp/oms-installer-XXXXXX)

makeself --nox11 --notemp installer $TMP oms-core ./update.sh
sed -i 's/targetdir="installer"/targetdir="oms"/' $TMP

cat >$INSTALLER <<EOF
#!/bin/sh
if [ "x\$0" = "xsh" ]; then
  # run as curl | sh
  # on some systems, you can just do cat>oms-installer.sh
  # which is a bit cuter.  But on others, &1 is already closed,
  # so catting to another script file won't do anything.
  curl -s http://opennodecloud.com/download/oms-core-installer.sh > oms-installer-\$\$.sh
  sh oms-installer-\$\$.sh
  ret=\$?
  #rm oms-installer-\$\$.sh
  exit \$ret
fi
EOF

cat >>$INSTALLER $TMP

# take care of the extra headers for pipelined installation
sed -i 's/head -n 403/head -n 415/' $INSTALLER

rm $TMP
