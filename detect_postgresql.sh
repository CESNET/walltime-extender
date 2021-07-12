#/bin/bash

export PATH=/usr/lib/postgresql/11/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/bin:/usr/sbin
dirname $(which pg_ctl) | sed 's/\//\\\//g'
