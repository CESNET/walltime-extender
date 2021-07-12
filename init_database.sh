sudo -u postgres /usr/lib/postgresql/11/bin/initdb -D /tmp/pgsql_walltime-extender/
sudo -u postgres /usr/lib/postgresql/11/bin/pg_ctl -D /tmp/pgsql_walltime-extender/ -o "-p 5455" start -w 
sudo -u postgres /usr/lib/postgresql/11/bin/pg_ctl -D /tmp/pgsql_walltime-extender/ stop -w

sudo -u postgres psql -h localhost -p 5455 -c 'CREATE DATABASE walltime_extender;'

