#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2016 Matthew Stone <mstone5@mgh.harvard.edu>
# Distributed under terms of the MIT license.

"""
Parse LSF log files
"""

import argparse
import re
from datetime import datetime
import pandas as pd


class LSFLog(object):
    def __init__(self, jobID, jobname, host, queue, start, end, walltime,
                 cmd, cpu, mem, swap, output_lines=[]):
        self.jobID = jobID
        self.jobname = jobname
        self.host = host
        self.queue = queue
        self.start = start
        self.end = end
        self.walltime = walltime
        self.cmd = cmd
        self.cpu = cpu
        self.mem = mem
        self.swap = swap
        self.output_lines = output_lines

    @property
    def output(self):
        return ''.join(self.output_lines)

    @property
    def series(self):
        return pd.Series(self.__dict__).drop(['output_lines', 'cmd'])


def parse_logs(logfile):
    """
    Convert logfile entries to LSFLog objects

    Parameters
    ---------
    logfile : file
        Open LSF log file handle

    Yields
    ------
    log : LSFLog
    """

    jobID_exp = re.compile(r'Job (\d+):')
    jobname_exp = re.compile(r'<(.*)>')
    host_exp = re.compile(r'host\(s\) <([a-z]+[0-9]+)>')
    queue_exp = re.compile(r'queue <([a-z]+)>')
    cpu_exp = re.compile(r'(\d+\.\d+)')
    mem_exp = re.compile(r'(\d+)')

    log = None

    for line in logfile:
        if line.startswith('Sender'):
            if log is not None:
                yield log

            subject = next(logfile)
            jobID = re.search(jobID_exp, subject).group(1)
            jobname = re.search(jobname_exp, subject).group(1)

            next(logfile)
            next(logfile)
            execline = next(logfile)
            host = re.search(host_exp, execline).group(1)
            queue = re.search(queue_exp, execline).group(1)

            next(logfile)
            next(logfile)
            startline = next(logfile)
            endline = next(logfile)
            start = startline.strip().split(' at ')[1]
            end = endline.strip().split(' at ')[1]
            start = datetime.strptime(start, '%a %b %d %X %Y')
            end = datetime.strptime(end, '%a %b %d %X %Y')
            walltime = (end - start).total_seconds()

            for i in range(5):
                next(logfile)
            cmd = next(logfile).strip()

            for i in range(6):
                next(logfile)
            cpuline = next(logfile)
            cpu = float(re.search(cpu_exp, cpuline).group(1))
            memline = next(logfile)
            mem = int(re.search(mem_exp, memline).group(1))
            swapline = next(logfile)
            swap = int(re.search(mem_exp, swapline).group(1))

            log = LSFLog(jobID, jobname, host, queue, start, end, walltime,
                         cmd, cpu, mem, swap, [])

        elif line.startswith('The output (if any) follows'):
            next(logfile)

        elif log is not None:
            log.output_lines.append(line)

    yield log


def job_stats(logfile):
    """
    Return numeric job stats as dataframe

    Parameters
    ----------
    logfile : file
        Open LSF log file handle

    Returns
    -------
    stats : pd.DataFrame
    """

    logs = [log.series for log in parse_logs(logfile)]
    stats = pd.concat(logs, axis=1).transpose()
    stats = stats.set_index('jobID')
    stats['walltime_hr'] = stats['walltime'] / 3600

    return stats


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('logfile')
    parser.add_argument('logstats')
    args = parser.parse_args()

    stats = job_stats(args.logfile)
    stats.to_csv(args.logstats, sep='\t')


if __name__ == '__main__':
    main()
