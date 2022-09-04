import os

from webscrapbook import server

root = os.path.abspath(os.path.join(__file__, '..', '..'))
server.serve(root)
