#!/usr/bin/env python3
import sys, os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)
sys.path.insert(0, root)

from webscrapbook.app import init_app
application = init_app()
