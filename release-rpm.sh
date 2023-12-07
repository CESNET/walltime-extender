#!/bin/bash

VERSION="1.0"

rm openpbs-walltime-extender-$VERSION -rf
mkdir -p openpbs-walltime-extender-$VERSION

make

cp openpbs-walltime-extender.spec openpbs-walltime-extender-$VERSION/
cp openpbs-walltime-extender.py openpbs-walltime-extender-$VERSION/
cp openpbs-walltime-extender openpbs-walltime-extender-$VERSION/
cp openpbs-walltime-extender.conf openpbs-walltime-extender-$VERSION/
cp openpbs-walltime-extender.remctl openpbs-walltime-extender-$VERSION/
cp debian/openpbs-walltime-extender.service openpbs-walltime-extender-$VERSION/
cp _pbs_ifl.so openpbs-walltime-extender-$VERSION/
cp pbs_ifl.py openpbs-walltime-extender-$VERSION/

POSTGRESQL_PATH=$(./detect_postgresql.sh)
cp openpbs-walltime-extender.spec openpbs-walltime-extender.spec.backup
sed -i "s/POSTGRESQL_PATH_HERE/$POSTGRESQL_PATH/g" openpbs-walltime-extender.spec
sed -i "s/POSTGRESQL_PATH_HERE/$POSTGRESQL_PATH/g" openpbs-walltime-extender-$VERSION/openpbs-walltime-extender.spec
sed -i "s/POSTGRESQL_PATH_HERE/$POSTGRESQL_PATH/g" openpbs-walltime-extender-$VERSION/openpbs-walltime-extender.service

tar -cvzf openpbs-walltime-extender-${VERSION}.tar.gz openpbs-walltime-extender-$VERSION
rm openpbs-walltime-extender-$VERSION -rf

mkdir -p ~/rpmbuild/SOURCES/
mv openpbs-walltime-extender-${VERSION}.tar.gz ~/rpmbuild/SOURCES/

rpmbuild -ba openpbs-walltime-extender.spec

mv openpbs-walltime-extender.spec.backup openpbs-walltime-extender.spec