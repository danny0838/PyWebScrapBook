#!/usr/bin/env python3
import os
from webscrapbook import server
server.serve(os.path.dirname(os.path.dirname(__file__)))
