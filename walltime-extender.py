#!/usr/bin/env python3

import re
import sys
import os
import logging
from datetime import datetime
from configparser import ConfigParser

try:
    import pbs_ifl
except:
    sys.path.insert(1, "/opt/pbs/lib/python3-pbs_ifl")
    import pbs_ifl

try:
    import psycopg2
except:
    sys.path.insert(1, "/usr/local/lib/python3.7/dist-packages")
    import psycopg2


def config(filename="/opt/pbs/etc/walltime-extender.conf",
           section=""):

    parser = ConfigParser()
    parser.read(filename)

    c = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            c[param[0]] = param[1]
    else:
        raise Exception("Section {0} not found in the {1} file"
                        .format(section, filename))

    return c


TOOL_NAME = "walltime-extender"
FORMAT = "%(asctime)-15s %(ip)s %(user)-8s %(levelname)s %(message)s"
INFO = 0
WARNING = 1
ERROR = 2
DEBUG = 3
try:
    logfile = config(section="logging")["logfile"]
except:
    logfile = None
logging.basicConfig(filename=logfile,
                    format=FORMAT,
                    level=logging.DEBUG)
logger = logging.getLogger(TOOL_NAME)


def logMsg(lvl, msg):
    if lvl > INFO and lvl < DEBUG:
        print(msg, file=sys.stderr)
    else:
        print(msg)

    if not logfile:
        return

    # remove text colorization
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    msg = ansi_escape.sub('', msg)

    user = os.getenv("REMOTE_USER")
    if user is None or len(user) == 0:
        user = "unknown-user"

    ip = os.getenv("REMOTE_ADDR")
    if ip is None or len(ip) == 0:
        ip = "unknown-ip"

    d = {'ip': ip, 'user': user}
    if lvl == INFO:
        logger.info(msg, extra=d)
    if lvl == WARNING:
        logger.warning(msg, extra=d)
    if lvl == ERROR:
        logger.error(msg, extra=d)
    if lvl == DEBUG:
        logger.debug(msg, extra=d)


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class Database(object):
    """
    """

    def __init__(self):
        """
        Init
        """

        self.table_name = "extended"
        self.conn = None
        self.connected = False
        self.params = config(section="postgresql")

    def connect(self):

        try:
            self.conn = psycopg2.connect(**self.params)
        except:
            logMsg(ERROR, "Failed to connect to database.")
            return

        self.connected = True

        if self.check_table(self.table_name):
            self.connected = False
            return

    def disconnect(self):
        if self.conn is not None:
            self.conn.close()
        self.connected = False

    def is_connected(self):
        return self.connected

    def check_table(self, table_name):
        if not self.is_connected():
            return 1

        sql = "CREATE TABLE IF NOT EXISTS %s (\
jobid varchar(511), \
owner varchar(255), \
cputime integer, \
date timestamp);" % table_name

        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to check or create table.")
            return 1

        return 0

    def insert_job(self, jobid, owner, cputime):
        if not self.is_connected():
            return

        sql = "INSERT INTO %s (jobid, owner, cputime, date) \
VALUES ('%s', '%s', %d, NOW());" % (self.table_name, jobid, owner, cputime)

        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to insert a job into database.")

    def get_used_fund(self, owner):
        if not self.is_connected():
            return -1

        used_fund = -1

        sql = "SELECT SUM (cputime) AS total_cputime FROM %s \
WHERE owner = '%s';" % (self.table_name, owner)

        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            used_fund = cur.fetchone()[0]
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to get used fund.")
            used_fund = -1

        if used_fund is None:
            used_fund = 0

        return used_fund

    def get_used_count(self, owner):
        if not self.is_connected():
            return -1

        used_count = -1

        sql = "SELECT COUNT (cputime) AS total_count FROM %s \
WHERE owner = '%s';" % (self.table_name, owner)

        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            used_count = cur.fetchone()[0]
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to get used count.")
            used_count = -1

        if used_count is None:
            used_count = 0

        return used_count

    def clean_old(self, seconds):
        if not self.is_connected():
            return

        try:
            cur = self.conn.cursor()
            sql = "DELETE FROM %s WHERE date < NOW() - interval '%d second';\
" % (self.table_name, seconds)
            cur.execute(sql)
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to clean old records.")


class Walltime_extender(object):
    """
    PBS walltime extender class
    """

    def __init__(self, argv):
        """
        Init
        """

        self.server_host = None
        self.c = None
        self.ncpus = 0
        self.cputime = 0
        self.current_walltime = 0
        self.new_walltime = 0
        self.admin = False
        self.affect_fund = True
        self.db = None
        self.only_info = False

        self.clean_secs = 2592000
        self.fund = 10368000
        self.count = 20
        self.admin_re = r'NOTHING'

        cfg = config(section="general")

        if "clean_secs" in cfg.keys():
            self.clean_secs = self.human2sec(cfg["clean_secs"])

        if "fund" in cfg.keys():
            self.fund = self.human2sec(cfg["fund"])

        if "count" in cfg.keys():
            self.count = int(cfg["count"])

        if "admin_re" in cfg.keys():
            self.admin_re = r'%r' % cfg["admin_re"]
            self.admin_re = self.admin_re[1:-1]

        self.cmd_owner = os.getenv("REMOTE_USER")
        if self.cmd_owner is None or len(self.cmd_owner) == 0:
            logMsg(ERROR, "Missing REMOTE_USER environmental variable.")
            self.print_help()
            return

        if len(self.admin_re) > 0 and re.match(self.admin_re, self.cmd_owner):
            print("You are the admin. Your cputime fund is not affected.")
            self.admin = True
            self.affect_fund = False

        if len(argv) == 2 and sys.argv[1] == 'info':
            self.only_info = True
        elif len(argv) > 2:
            self.jobid = sys.argv[1]
            self.additional_walltime = sys.argv[2]
        else:
            self.print_help()
            return

        if not self.only_info and not self.check_walltime_format():
            logMsg(ERROR, "Incorrect walltime format.")
            self.print_help()
            return

        if not self.only_info:
            self.connect_server()

            self.additional_walltime = self.human2sec(self.additional_walltime)
            if self.adjust_jobid():
                self.disconnect_server()
                self.connect_server(self.server_host)

        self.db = Database()
        if self.db.connect():
            return

        self.db.clean_old(self.clean_secs)

    def print_help(self):
        """
        Prints help
        """
        self.cmd_owner = None
        self.jobid = None
        self.additional_walltime = None
        print("Usage:")
        print("remctl <pbs_server> pbs-extend \
[<jobid> <additional_walltime>]|info")
        print("")
        print(" - A valid kerberos ticket needs to be issued before running.")
        print(" - Allowed jobid formats: \
123|123.servername|123.original_servername@target_servername")
        print(" - Allowed additional_walltime formats: \
<seconds>|<h+:mm:ss>")

    def human2sec(self, h):
        """
        Converts hh:mm:ss to seconds
        """

        a = h.split(":")

        s = 0

        if len(a) > 0:
            s += int(a[len(a) - 1])
        if len(a) > 1:
            s += int(a[len(a) - 2]) * 60
        if len(a) > 2:
            s += int(a[len(a) - 3]) * 60 * 60

        return s

    def sec2human(self, s):
        """
        Converts seconds to hh:mm:ss
        """

        h = ""

        hours = int(s / 60 / 60)
        s = s % (60 * 60)

        mins = int(s / 60)
        s = s % 60

        secs = int(s)

        h = "%02d:%02d:%02d" % (hours, mins, secs)
        return h

    def get_ncpus(self, exec_vnode):
        """
        Gets total number of ncpus from exec_vnode
        """
        ncpus = 0

        for i in exec_vnode.split("+"):
            node_ncpus = 1
            match = re.match(r'.*ncpus=([0-9]+).*', i)
            if match:
                node_ncpus *= int(match.group(1))
            ncpus += node_ncpus

        return ncpus

    def connect_server(self, server_name=None):
        """
        Connect to PBS server
        """

        try:
            self.c = pbs_ifl.pbs_connect(server_name)
        except:
            self.c = None

        if not self.c or self.c < 0:
            logMsg(ERROR, "Failed to connect to %s server." % server_name)
            self.c = None
            return

        server_info = []
        try:
            server_info = pbs_ifl.pbs_statserver(self.c, None, None)
        except:
            logMsg(ERROR, "Failed to get server info. Try again later.")
            self.c = None
            server_info = []

        if len(server_info) > 0:
            server_info = server_info[0]
            self.server_host = server_info["server_host"]

    def disconnect_server(self):
        """
        Disconnect from PBS server
        """

        if self.c is None:
            return

        try:
            ret = pbs_ifl.pbs_disconnect(self.c)
        finally:
            self.c = None

    def adjust_jobid(self):
        """
        Adds server name to number (if needed).
        Checks jobid@fqdn and returns frue if needs reconnect
        to different server.
        Returns false for no reconnect
        """

        if re.match(r'^[0-9]+$', self.jobid):
            self.jobid += ".%s" % self.server_host
            return False

        a = self.jobid.split("@")
        if len(a) == 1:
            return False

        if (len(a) != 2):
            return False

        if len(a[1]) == 0:
            return False

        if (self.server_host == a[1]):
            return False

        self.server_host = a[1]

        # Needs reconnect
        return True

    def check_count(self):
        """
        Checks allowed number of jobs
        """

        if self.count == 0:
            return False

        used_count = self.db.get_used_count(self.cmd_owner)

        if used_count < 0:
            return False

        if self.count <= used_count:
            return False

        return True

    def check_fund(self):
        """
        Checks cputime fund
        """

        self.cputime = self.ncpus * self.additional_walltime

        if self.cputime == 0:
            return False

        used_fund = self.db.get_used_fund(self.cmd_owner)

        if used_fund < 0:
            return False

        if self.cputime > self.fund - used_fund:
            return False

        return True

    def adjust_fund(self):
        """
        Once the walltime has been extended,
        alter cputime fund
        """

        if not self.affect_fund:
            return

        self.db.insert_job(self.jobid, self.cmd_owner, self.cputime)

    def check_walltime_format(self):
        """
        Checks walltime format.
        Must be in seconds or
        h+:mm:ss
        """

        rexp = r'^(([0-9]+:[0-9]{2}:[0-9]{2})|([0-9]+))$'
        if not re.match(rexp, self.additional_walltime):
            return False

        rexp = r'^[0-9]+:[0-9]{2}:[0-9]{2}$'
        if re.match(rexp, self.additional_walltime):
            a = self.additional_walltime.split(":")

            if int(a[1]) >= 60:
                return False

            if int(a[2]) >= 60:
                return False

        return True

    def check_moved_job(self, job_info):
        """
        Check moved job is suitable for walltime extension.
        The extender is reconnect to suitableserver and
        checks the job.
        """
        if job_info["job_state"] != "M":
            return False

        if "queue" not in job_info.keys():
            return False

        a = job_info["queue"].split("@")

        if len(a) != 2:
            return False

        if len(a[1]) == 0:
            return False

        self.disconnect_server()
        self.connect_server(a[1])

        return self.check_job()

    def check_job(self):
        """
        Check job is suitable for walltime extension
        """

        if self.only_info:
            return False

        if self.jobid is None or self.additional_walltime is None:
            return False

        if self.additional_walltime == 0:
            logMsg(ERROR, "Zero walltime is not allowed.")
            return False

        if self.c is None:
            logMsg(ERROR, "No connection to server.")
            return False

        if not self.db.is_connected():
            return False

        try:
            job_info = pbs_ifl.pbs_statjob(self.c, self.jobid, None, "x")
        except:
            logMsg(ERROR, "Failed to get job info.")
            return False

        if len(job_info) != 1:
            logMsg(ERROR, "Jobid %s not found." % self.jobid)
            return False

        job_info = job_info[0]

        if job_info["job_state"] == "M":
            return self.check_moved_job(job_info)

        elif job_info["job_state"] == "F":
            logMsg(INFO, "The job %s already finished." % self.jobid)
            return False

        elif job_info["job_state"] == "Q":
            logMsg(INFO, "The job %s did not start yet.\
Your cputime fund will not be affected." % self.jobid)

            self.affect_fund = False
            # no return here

        elif job_info["job_state"] != "R":
            logMsg(INFO, "The job %s is not running." % self.jobid)
            return False

        if not self.admin and self.cmd_owner != job_info["Job_Owner"]:
            logMsg(ERROR, "You are not the owner of the job.")
            return False

        if "Resource_List.walltime" not in job_info.keys():
            logMsg(ERROR, "Requested job %s misses the walltime resource."
                   % self.jobid)
            return False

        self.current_walltime = self.human2sec(
            job_info["Resource_List.walltime"])

        if self.affect_fund:
            if "exec_vnode" not in job_info.keys():
                logMsg(ERROR, "Requested job %s misses the exec_vnode."
                       % self.jobid)
                return False
            self.ncpus = self.get_ncpus(job_info["exec_vnode"])
        else:
            self.ncpus = 1 # doesn't matter

        if self.ncpus == 0:
            logMsg(ERROR, "Failed to get ncpus from 'exec_vnode'.")
            return False

        if self.affect_fund and not self.check_count():
            logMsg(INFO, f"Number of extensions {bcolors.FAIL}exceeds \
%d{bcolors.ENDC}." % self.count)

            return False

        if self.affect_fund and not self.check_fund():
            used_fund = self.db.get_used_fund(self.cmd_owner)
            avail_walltime = (self.fund - used_fund) / self.ncpus

            logMsg(INFO, f"Requested walltime {bcolors.FAIL}exceeds %s's \
cputime fund{bcolors.ENDC}." % self.cmd_owner)

            print("Possible walltime extension for the job %s is %s." %
                  (self.jobid, self.sec2human(avail_walltime)))

            return False

        return True

    def create_walltime_attr(self, walltime):
        """
        Creates walltime attribute from walltime
        """

        a = pbs_ifl.attrl()
        a.name = "Resource_List"
        a.resource = "walltime"
        a.value = walltime
        a.next = None

        return a

    def extend(self):
        """
        Extends the job
        """

        ret = 1

        if self.c is None:
            logMsg(ERROR, "No connection to server.")
            return ret

        self.new_walltime = self.current_walltime + self.additional_walltime

        attr_walltime = self.create_walltime_attr(
                        self.sec2human(self.new_walltime))

        try:
            ret = pbs_ifl.pbs_alterjob(self.c, self.jobid, attr_walltime, None)
        except:
            ret = 1

        if ret != 0:
            logMsg(ERROR, "Failed to alter job. Error code: %d" % ret)
            return ret

        logMsg(INFO, f"The walltime of the job %s {bcolors.OKGREEN}\
has been extended{bcolors.ENDC}. New walltime: %s." %
               (self.jobid, self.sec2human(self.new_walltime)))

        self.disconnect_server()

        return ret

    def finish(self):
        if self.affect_fund and self.cmd_owner and self.db.is_connected():
            days = int(self.clean_secs / 86400)
            used_count = self.db.get_used_count(self.cmd_owner)
            used_fund = self.db.get_used_fund(self.cmd_owner)
            print()
            print("%s's info:" % self.cmd_owner)
            print()
            print("%d-days counter limit:\t%d" %
                  (days, self.count))

            print("Used counter limit:\t%d" % used_count)

            print("Avail. counter limit:\t%d" %
                  (self.count - used_count))
            print()

            print("%d-days cputime fund:\t%s" %
                  (days, self.sec2human(self.fund)))

            print("Used cputime fund:\t%s" %
                  self.sec2human(used_fund))

            print("Avail. cputime fund:\t%s" %
                  self.sec2human((self.fund - used_fund)))

        self.disconnect_server()
        if self.db:
            self.db.disconnect()

if __name__ == "__main__":
    extender = Walltime_extender(sys.argv)
    ret = 1
    if extender.check_job():
        ret = extender.extend()
        if ret == 0:
            extender.adjust_fund()

    extender.finish()
    exit(ret)
