#!/usr/bin/env python3
import os
from webscrapbook.app import make_app
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
application = make_app(root)
