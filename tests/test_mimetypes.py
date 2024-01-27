import os
import unittest
from unittest import mock

from webscrapbook._polyfill import mimetypes


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


class TestMimetypes(unittest.TestCase):
    def test_overridden_mimetypes(self):
        self.assertEqual(
            mimetypes.guess_type('myfile.htz'),
            ('application/html+zip', None),
        )
        self.assertEqual(
            mimetypes.guess_type('myfile.maff'),
            ('application/x-maff', None),
        )
        self.assertEqual(
            mimetypes.guess_type('myfile.wsba'),
            ('application/wsba+zip', None),
        )
        self.assertEqual(
            mimetypes.guess_type('myfile.zip'),
            ('application/zip', None),
        )
        self.assertEqual(
            mimetypes.guess_type('myfile.md'),
            ('text/markdown', None),
        )
        self.assertEqual(
            mimetypes.guess_type('myfile.js'),
            ('text/javascript', None),
        )
        self.assertEqual(
            mimetypes.guess_type('myfile.bmp'),
            ('image/bmp', None),
        )
        self.assertEqual(
            mimetypes.guess_type('myfile.ico'),
            ('image/x-icon', None),
        )


if __name__ == '__main__':
    unittest.main()
