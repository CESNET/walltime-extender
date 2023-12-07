sudo -u postgres /usr/lib/postgresql/15/bin/initdb -D /tmp/pgsql_openpbs-walltime-extender/
sudo -u postgres /usr/lib/postgresql/15/bin/pg_ctl -D /tmp/pgsql_openpbs-walltime-extender/ -o "-p 5455" start -w 
sudo -u postgres /usr/lib/postgresql/15/bin/pg_ctl -D /tmp/pgsql_openpbs-walltime-extender/ stop -w

sudo -u postgres psql -h localhost -p 5455 -c 'CREATE DATABASE walltime_extender;'

