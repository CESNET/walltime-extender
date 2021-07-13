#!/bin/bash

VERSION="1.0"

rm walltime-extender-$VERSION -rf
mkdir -p walltime-extender-$VERSION

make

cp walltime-extender.spec walltime-extender-$VERSION/
cp walltime-extender.py walltime-extender-$VERSION/
cp walltime-extender walltime-extender-$VERSION/
cp walltime-extender.conf walltime-extender-$VERSION/
cp walltime-extender.remctl walltime-extender-$VERSION/
cp debian/walltime-extender.service walltime-extender-$VERSION/
cp _pbs_ifl.so walltime-extender-$VERSION/
cp pbs_ifl.py walltime-extender-$VERSION/

POSTGRESQL_PATH=$(./detect_postgresql.sh)
cp walltime-extender.spec walltime-extender.spec.backup
sed -i "s/POSTGRESQL_PATH_HERE/$POSTGRESQL_PATH/g" walltime-extender.spec
sed -i "s/POSTGRESQL_PATH_HERE/$POSTGRESQL_PATH/g" walltime-extender-$VERSION/walltime-extender.spec
sed -i "s/POSTGRESQL_PATH_HERE/$POSTGRESQL_PATH/g" walltime-extender-$VERSION/walltime-extender.service

tar -cvzf walltime-extender-${VERSION}.tar.gz walltime-extender-$VERSION
rm walltime-extender-$VERSION -rf

mkdir -p ~/rpmbuild/SOURCES/
mv walltime-extender-${VERSION}.tar.gz ~/rpmbuild/SOURCES/

rpmbuild -ba walltime-extender.spec

mv walltime-extender.spec.backup walltime-extender.spec