#!/usr/bin/env python3
import os
from webscrapbook import server
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
server.serve(root)
