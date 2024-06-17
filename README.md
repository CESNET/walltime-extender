# walltime-extender

walltime-extender alias `qextend` is a PBSPro/OpenPBS tool for allowing self-extend job's walltime by users.

The `qextend` command can be used by both the users and the admins.

 * The users are limited by the number of job extensions and quota, which is cputime fund in seconds. Whatever limit they meet first, they can not extend the jobs by themself anymore. The consumed fund is progressively released based on the elapsed time. Users can also show their current consumption.

 * The admins can extend the jobs without any limit and they can reset the user's limits.

The tool also checks for jobs running on a node, that is not suitable for job extensions. This can happen if there is a conflicting reservation planned on the node or the node is in a special queue (like `maintenance`/`reserved`). Admins can force the job extension.

The tool uses a small PostgreSQL database to keep track of the limit consumption.

`qextend` tool is composed of two parts:

 * A script available for users. This script uses `remctl` to contact the server and invoke the server part of the tool. `remctl` allows to easily authenticate the users. This way the authenticated username and parameters for extending a job to the server part are provided.

 * The server part with the database is in Python and uses PBSPro/OpenPBS API to query affected nodes and alter the requested jobs.

## Parameters

qextend (client part):
 * `info` - shows user info of current consumptions
 * `<jobid> <additional_walltime>` - extend the job walltime by `<additional_walltime>`, walltime is requested but cputime is subtracted from the user's fund
 * `-f` - force the walltime prolongation over planned maintenance (admins only)

openpbs-walltime-extender (server part):
The username/principal is read from the environmental variable `REMOTE_USER`.
 * `info` - shows user's consumptions
 * `<jobid> <additional_walltime>` - extend the job walltime by `<additional_walltime>`
 * `list` - list all user's consumption
 * `reset <principal>` - reset all limits and consumption of user `<principal>`

## Configuration

One or more pbs servers should be set at the beginning of qextend script.
 * servers=("pbs_server_name")

The server configuration file is located in `/opt/pbs/etc/openpbs-walltime-extender.conf`:

`general` section:
 * `clean_secs` - after this time, the job extension is forgotten, and the used cputime fund is released
 * `fund` - comma-separated list of regex representing username and allowed cputime fund limit for the user, e.g.: `.*@REALM1$:10368000,.*@REALM2$:20736000,`
 * `count` - comma-separated list of regex representing username and number of allowed job extensions, e.g.: `.*@REALM1$:10,.*@REALM2$:20,`
 * `admin_re` - regexp representing users with admin permissions, e.g.: .`*@ADMIN.REALM$`
 * `list_re` - regexp representing users allowed to list users' consumption, e.g.: .`*@ADMIN.REALM$`
 * `owner_re` - regexp representing the allowed format of the username

`postgresql` section:
 * here you can specify how to connect to the database

`logging` section:
 * `logfile` - path to logfile

## Installation

Server part:
 * create debian package: run `./release-deb.sh`
 * create rpm package: run `./release-rpm.sh`

Client part:
 * provide the `qextend` script to users