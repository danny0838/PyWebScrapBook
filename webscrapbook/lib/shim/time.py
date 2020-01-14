#!/usr/bin/env python3
"""shim for time
"""
import time


def time_ns():
    # time.time_ns is available since Python 3.7
    return int(time.time() * 1e9)


if not hasattr(time, 'time_ns'):
    time.time_ns = time_ns
