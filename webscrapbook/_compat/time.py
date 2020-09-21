# time.time_ns is available since Python 3.7
try:
    from time import time_ns
except ImportError:
    from time import time
    def time_ns():
        return int(time() * 1e9)
