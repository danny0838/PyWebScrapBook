import os

from webscrapbook.app import make_app

root = os.path.abspath(os.path.join(__file__, '..', '..'))
application = make_app(root)
