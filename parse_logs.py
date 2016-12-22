#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2016 Matthew Stone <mstone5@mgh.harvard.edu>
# Distributed under terms of the MIT license.

"""
Parse LSF log files
"""

import sys
import argparse
import re
from datetime import datetime
import pandas as pd


class LSFLog(object):
    def __init__(self, jobID, jobname, host, queue, start, end, walltime,
                 cmd, status, cpu, mem, swap, output_lines=[]):
        self.jobID = jobID
        self.jobname = jobname
        self.host = host
        self.queue = queue
        self.start = start
        self.end = end
        self.walltime = walltime
        self.cmd = cmd
        self.status = status
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
                if len(log.output_lines) == 0:
                    log.output_lines = ['']
                yield log

            subject = next(logfile)
            jobID = re.search(jobID_exp, subject).group(1)
            jobname = re.search(jobname_exp, subject).group(1)

            next(logfile)
            next(logfile)
            execline = next(logfile)
            try:
                host = re.search(host_exp, execline).group(1)
            except:
                sys.stderr.write('Malformed job log: {0}\n'.format(jobID))
                continue
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
            cmd = ''
            for line in logfile:
                if line.startswith('--------'):
                    cmd = cmd.strip()
                    break
                cmd = cmd + ' ' + line.strip()

            next(logfile)
            statusline = next(logfile)
            if statusline.startswith('Successfully completed'):
                status = 'DONE'
            else:
                status = 'EXIT'

            cpuline = next(logfile)
            while re.search(cpu_exp, cpuline) is None:
                cpuline = next(logfile)
            cpu = float(re.search(cpu_exp, cpuline).group(1))

            memline = next(logfile)
            try:
                mem = int(re.search(mem_exp, memline).group(1))
            except AttributeError:
                mem = 0
            swapline = next(logfile)
            try:
                swap = int(re.search(mem_exp, swapline).group(1))
            except AttributeError:
                swap = 0

            log = LSFLog(jobID, jobname, host, queue, start, end, walltime,
                         cmd, status, cpu, mem, swap, [])

            for i in range(6):
                next(logfile)

        elif log is not None:
            log.output_lines.append(line.strip())

    if len(log.output_lines) == 0:
        log.output_lines = ['']
    yield log


def job_stats(logs):
    """
    Return numeric job stats as dataframe

    Parameters
    ----------
    logs : list of LSFLog
        LSF logs

    Returns
    -------
    stats : pd.DataFrame
    """

    logs = [log.series for log in logs]
    stats = pd.concat(logs, axis=1).transpose()
    stats = stats.set_index('jobID')
    stats['walltime_hr'] = stats['walltime'] / 3600

    return stats


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('logfile', type=argparse.FileType('r'),
                        help='LSF log file to parse')
    parser.add_argument('logstats',
                        help='Tidied LSF log statistics')
    parser.add_argument('--output', type=argparse.FileType('w'),
                        help='stdout/stderr of each job')
    args = parser.parse_args()

    logs = list(parse_logs(args.logfile))

    stats = job_stats(logs)
    stats.to_csv(args.logstats, sep='\t')

    for log in logs:
        args.output.write('{0}\t{1}\t{2}\t{3}\n'.format(log.jobID, 'A', log.output_lines[0], 'B'))


if __name__ == '__main__':
    main()
