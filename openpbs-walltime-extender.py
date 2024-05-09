#!/usr/bin/env python3

import re
import sys
import os
import logging
import json
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


def config(filename="/opt/pbs/etc/openpbs-walltime-extender.conf",
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


TOOL_NAME = "openpbs-walltime-extender"
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

    msg = msg.replace('\n', ' ')
    msg = msg.replace('\t', ' ')
    msg = re.sub(' +', ' ', msg)

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

        jobid = self.sanitize(jobid)
        owner = self.sanitize(owner)
        cputime = self.sanitize(cputime)

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

        owner = self.sanitize(owner)

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

        owner = self.sanitize(owner)

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

    def get_full_list(self):
        if not self.is_connected():
            return []

        full_list = []

        sql = "SELECT owner, COUNT(cputime) AS count, \
SUM (cputime) AS total_cputime FROM %s GROUP BY owner;" % self.table_name

        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            full_list = cur.fetchall()
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to get the list.")
            full_list = []

        return full_list

    def get_earliest_record_timeout(self, owner, seconds):
        if not self.is_connected():
            return None

        owner = self.sanitize(owner)
        seconds = self.sanitize(seconds)

        earliest_timeout = None

        try:
            cur = self.conn.cursor()
            sql = "SELECT MIN(date) + interval '%d second' as earliest \
FROM %s WHERE owner = '%s';" % (seconds, self.table_name, owner)
            cur.execute(sql)
            earliest_timeout = cur.fetchone()[0]
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to get earliest record timeout for %s."
                   % owner)
            earliest_timeout = None

        return earliest_timeout

    def clean_owner(self, owner):
        if not self.is_connected():
            return

        owner = self.sanitize(owner)

        try:
            cur = self.conn.cursor()
            sql = "DELETE FROM %s WHERE owner = '%s';" \
                  % (self.table_name, owner)
            cur.execute(sql)
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to delete %s's records." % owner)

    def clean_old(self, seconds):
        if not self.is_connected():
            return

        seconds = self.sanitize(seconds)

        try:
            cur = self.conn.cursor()
            sql = "DELETE FROM %s WHERE date < NOW() - interval '%d second';\
" % (self.table_name, seconds)
            cur.execute(sql)
            cur.close()
            self.conn.commit()
        except:
            logMsg(ERROR, "Failed to clean old records.")

    def sanitize(self, to_check):
        forbidden_chars = [";", "'", '"']
        safe_str = "__u_n_k_n_o_w_n__"

        if (type(to_check) == int):
            return to_check

        if (type(to_check) == str):
            if len(to_check) == 0:
                to_check = safe_str

            for i in forbidden_chars:
                if to_check.find(i) != -1:
                    to_check = safe_str

        else:
            to_check = safe_str

        return to_check


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
        self.force = False
        self.affect_fund = True
        self.db = None

        self.do_extension = False
        self.show_info = False
        self.show_full_list = False
        self.reset_owner = None
        self.info_owner = None

        self.clean_secs = 2592000
        self.fund = 10368000
        self.count = 20
        self.owner_re = r'^[a-z][a-z0-9_-]{1,14}@[A-Z0-9\._-]+$'
        self.admin_re = r'NOTHING'
        self.list_re = r'.*'

        self.preparsed_fund = ""
        self.preparsed_count = ""

        cfg = config(section="general")

        if "clean_secs" in cfg.keys():
            self.clean_secs = self.human2sec(cfg["clean_secs"])

        if "fund" in cfg.keys():
            self.preparsed_fund = cfg["fund"]

        if "count" in cfg.keys():
            self.preparsed_count = cfg["count"]

        if "owner_re" in cfg.keys():
            self.owner_re = r'%r' % cfg["owner_re"]
            self.owner_re = self.owner_re[1:-1]

        if "admin_re" in cfg.keys():
            self.admin_re = r'%r' % cfg["admin_re"]
            self.admin_re = self.admin_re[1:-1]

        if "list_re" in cfg.keys():
            self.list_re = r'%r' % cfg["list_re"]
            self.list_re = self.list_re[1:-1]

        self.cmd_owner = os.getenv("REMOTE_USER")
        if self.cmd_owner is None or len(self.cmd_owner) == 0:
            logMsg(ERROR, "Missing REMOTE_USER environmental variable.")
            self.print_help()
            return

        if not re.match(self.owner_re, self.cmd_owner):
            logMsg(ERROR, "Illegal format of REMOTE_USER.")
            self.print_help()
            return

        for r in self.preparsed_fund.split(","):
            rule = r.split(":")
            if len(rule) != 2:
                continue
            [rule_re, rule_value] = rule
            rule_re = rule_re.strip()
            rule_value = rule_value.strip()
            rule_re = r'%r' % rule_re
            rule_re = rule_re[1:-1]

            if re.match(rule_re, self.cmd_owner):
                self.fund = int(rule_value)
                break

        for r in self.preparsed_count.split(","):
            rule = r.split(":")
            if len(rule) != 2:
                continue
            [rule_re, rule_value] = rule
            rule_re = rule_re.strip()
            rule_value = rule_value.strip()
            rule_re = r'%r' % rule_re
            rule_re = rule_re[1:-1]

            if re.match(rule_re, self.cmd_owner):
                self.count = self.human2sec(rule_value)
                break

        if len(self.admin_re) > 0 and re.match(self.admin_re, self.cmd_owner):
            print("You are the admin. Your cputime fund will not be affected.")
            self.admin = True
            self.affect_fund = False

        if "-f" in sys.argv:
            sys.argv.remove("-f")
            if self.admin:
                self.force = True
            else:
                print("You need to be the admin to use '-f' parameter.")

        if len(argv) == 2 and sys.argv[1] == 'info':
            self.show_info = True
        elif len(argv) == 3 and sys.argv[1] == 'info':
            if len(sys.argv[2]) > 0:
                if self.cmd_owner == sys.argv[2]:
                    self.show_info = True
                else:
                    if not self.admin:
                        logMsg(ERROR, "You are not allowed to show others info.")
                        self.print_help()
                        return
                    self.info_owner = sys.argv[2]
                self.show_info = True
            else:
                self.print_help()
                return
        elif len(argv) == 2 and sys.argv[1] == 'list':
            if not self.admin:
                logMsg(ERROR, "You are not allowed to show full list.")
                self.print_help()
                return
            if self.admin:
                self.show_full_list = True
        elif len(argv) == 3 and sys.argv[1] == 'reset':
            if not self.admin:
                logMsg(ERROR, "You are not allowed to reset fund.")
            if (self.admin and len(sys.argv[2]) > 0):
                self.reset_owner = sys.argv[2]
                self.affect_fund = True
            else:
                self.print_help()
                return
        elif len(argv) > 2:
            self.jobid = sys.argv[1]
            self.additional_walltime = sys.argv[2]
            self.do_extension = True
        else:
            self.print_help()
            return

        if self.do_extension:
            if not self.check_walltime_format():
                logMsg(ERROR, "Incorrect walltime format.")
                self.print_help()
                return

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
[<jobid> <additional_walltime>]|info|list|[reset <principal>]")
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

    def check_max_walltime(self, job_info):
        """
        Checks the queue max walltime limit
        """

        if self.c is None:
            logMsg(ERROR, "No connection to server.")
            return False

        queue = job_info["queue"]

        if not queue:
            logMsg(ERROR, "Missing queue on job.")
            return False

        try:
            queue_info = pbs_ifl.pbs_statque(self.c, queue, None, None)
        except:
            logMsg(ERROR, "Failed to get queue info.")
            return False

        if len(queue_info) != 1:
            logMsg(ERROR, "Queue %s not found." % queue)
            return False

        queue_info = queue_info[0]

        if ("resources_max.walltime" in queue_info.keys()):
            limit = self.human2sec(queue_info["resources_max.walltime"])

            walltime = self.current_walltime + self.additional_walltime

            if walltime > limit:
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

    def check_node_reservation(self, job_info, node_info):
        """
        Check node reservation violation.
        """

        if "queue" in node_info.keys():
            if node_info["queue"] == "maintenance":
                return False

            if node_info["queue"] == "reserved":
                return False

        if "resv" in node_info.keys():
            resvs = node_info["resv"].split(", ")
            for resv in resvs:
                try:
                    resv_info = pbs_ifl.pbs_statresv(self.c, resv, None, None)
                except:
                    logMsg(ERROR, "Failed to get reservation info.")
                    return False

                if len(resv_info) != 1:
                    logMsg(ERROR, "Reservation %s not found." % resv)
                    return False

                resv_info = resv_info[0]

                if not "stime" in job_info.keys():
                    logMsg(ERROR, "Job %s misses start time. \
Please, contact support." % self.jobid)

                    return False

                if "reserve_start" in resv_info.keys():
                    end_time = int(job_info["stime"])
                    end_time += self.current_walltime
                    end_time += self.additional_walltime

                    if end_time > int(resv_info["reserve_start"]):
                        logMsg(INFO, "Reservation %s in conflict." % resv)
                        return False
        return True

    def check_reservations(self, job_info):
        """
        Check nodes reservations violation.
        """

        if job_info["job_state"] != "R":
            return True

        nodes = set()

        exec_host = job_info['exec_host']
        for host in exec_host.split("+"):
            host = host.split("/")[0]
            nodes.add(host)

        for node in nodes:
            try:
                node_info = pbs_ifl.pbs_statvnode(self.c, node, None, None)
            except:
                logMsg(ERROR, "Failed to get node info.")
                return False

            if len(node_info) != 1:
                logMsg(ERROR, "Node %s not found." % node)
                return False

            node_info = node_info[0]

            if not self.check_node_reservation(job_info, node_info):
                return False

        return True

    def check_job(self):
        """
        Check job is suitable for walltime extension
        """

        if not self.do_extension:
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
            logMsg(INFO, "The job %s did not start yet. \
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
            # doesn't matter
            self.ncpus = 1

        if self.ncpus == 0:
            logMsg(ERROR, "Failed to get ncpus from 'exec_vnode'.")
            return False

        if self.affect_fund and not self.check_count():
            logMsg(INFO, f"Number of extensions {bcolors.FAIL}exceeds \
%d{bcolors.ENDC}." % self.count)

            self.show_info = True

            return False

        if self.affect_fund and not self.check_fund():
            used_fund = self.db.get_used_fund(self.cmd_owner)
            avail_walltime = (self.fund - used_fund) / self.ncpus

            logMsg(INFO, f"Requested walltime {bcolors.FAIL}exceeds %s's \
cputime fund{bcolors.ENDC}." % self.cmd_owner)

            print("Possible walltime extension for the job %s is %s." %
                  (self.jobid, self.sec2human(avail_walltime)))

            self.show_info = True

            return False

        if not self.affect_fund and \
           not self.admin and \
           not self.check_max_walltime(job_info):

            logMsg(INFO, f"Requested walltime {bcolors.FAIL}violates \
queue limit{bcolors.ENDC}.")

            return False

        if not self.force and \
            not self.check_reservations(job_info):
            logMsg(INFO, f"Requested walltime {bcolors.FAIL}violates \
node reservation{bcolors.ENDC}. Please, contact support.")

            logMsg(INFO, "Admins can bypass this check by '-f' parameter.")

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

        reduction = 0
        if self.affect_fund:
            reduction = self.additional_walltime * self.ncpus
            self.show_info = True

        logMsg(INFO, f"The walltime of the job %s {bcolors.OKGREEN}\
has been extended{bcolors.ENDC}.\n\
Additional walltime:\t%s\n\
New walltime:\t\t%s\n\
Fund affected:\t\t%s\n\
Fund reduction:\t\t%s" %
               (self.jobid,
                self.sec2human(self.additional_walltime),
                self.sec2human(self.new_walltime),
                self.affect_fund,
                self.sec2human(reduction)))

        self.disconnect_server()

        return ret

    def reset_other_owner(self):

        if not self.reset_owner:
            return

        if not re.match(self.owner_re, self.reset_owner):
            logMsg(ERROR, "Illegal format of principal.")
            self.print_help()
            return

        self.db.clean_owner(self.reset_owner)

        self.info_owner = self.reset_owner
        self.show_info = True

        return

    def full_list(self):
        """
        Shows list of all users with fund consumption.
        """

        if not self.cmd_owner:
            return

        if self.show_full_list and self.db.is_connected():

            if len(self.list_re) == 0:
                logMsg(ERROR, "Listing users is disabled.")
                return

            if not re.match(self.list_re, self.cmd_owner):
                logMsg(ERROR, "No permission to list users.")
                return

            full_list = {}
            full_list["clean_secs"] = self.clean_secs
            if self.preparsed_fund:
                full_list["cputime_fund_rules"] = self.preparsed_fund
            if self.preparsed_count:
                full_list["count_limit_rules"] = self.preparsed_count
            full_list["list"] = {}
            for item in self.db.get_full_list():
                earliest_timeout = self.db.get_earliest_record_timeout(
                    item[0], self.clean_secs)
                full_list["list"][item[0]] = {}
                full_list["list"][item[0]]["count"] = item[1]
                full_list["list"][item[0]]["cputime"] = item[2]
                full_list["list"][item[0]]["earliest_timeout"] \
                    = "%s" % earliest_timeout

            print(json.dumps(full_list, indent=4))

    def info(self):
        """
        Show user info
        """

        if not self.show_info:
            return

        if not self.cmd_owner:
            return

        owner = self.cmd_owner

        if self.info_owner:
            owner = self.info_owner

        if not re.match(self.owner_re, owner):
            logMsg(ERROR, "Illegal format of principal.")
            self.print_help()
            return

        if self.db.is_connected():
            days = int(self.clean_secs / 86400)
            used_count = self.db.get_used_count(owner)
            used_fund = self.db.get_used_fund(owner)
            earliest_timeout = self.db.get_earliest_record_timeout(
                owner, self.clean_secs)
            print()
            print("%s's info:" % owner)
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
            print()
            print("Earliest rec. timeout:\t%s" %
                  earliest_timeout)

    def finish(self):
        """
        Disconnect from db and pbs
        """

        self.disconnect_server()
        if self.db:
            self.db.disconnect()

if __name__ == "__main__":
    extender = Walltime_extender(sys.argv)
    ret = 0
    if extender.check_job():
        ret = extender.extend()
        if ret == 0:
            extender.adjust_fund()

    extender.reset_other_owner()
    extender.full_list()
    extender.info()

    extender.finish()
    exit(ret)
