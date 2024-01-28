import glob
import os
import unittest
import uuid
from unittest import mock

from webscrapbook import util

from . import PROG_DIR


def setUpModule():
    # mock out user config
    global mockings
    mockings = (
        mock.patch('webscrapbook.Config.user_config_dir', return_value=os.devnull),
    )
    for mocking in mockings:
        mocking.start()


def tearDownModule():
    # stop mock
    for mocking in mockings:
        mocking.stop()


class TestThemesDefault(unittest.TestCase):
    def test_locales(self):
        locales_dir = os.path.join(PROG_DIR, 'themes', 'default', 'locales')
        for file in glob.iglob(os.path.join(glob.escape(locales_dir), '**', '*.py'), recursive=True):
            util.import_module_file(f'webscrapbook._test_themes_default_locale_{uuid.uuid4()}', file)
