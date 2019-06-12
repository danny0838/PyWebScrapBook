#!/usr/bin/env python3
"""shim for Python < 3.6

https://github.com/python/cpython/blob/3.6/Lib/secrets.py
"""
import base64
import os

DEFAULT_ENTROPY = 32  # number of bytes to return by default

def token_bytes(nbytes=None):
    if nbytes is None:
        nbytes = DEFAULT_ENTROPY
    return os.urandom(nbytes)

def token_urlsafe(nbytes=None):
    tok = token_bytes(nbytes)
    return base64.urlsafe_b64encode(tok).rstrip(b'=').decode('ascii')
