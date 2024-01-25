import importlib
import os
import tempfile
import unittest
from unittest import mock

from webscrapbook import WSB_USER_DIR
from webscrapbook._polyfill import mimetypes

from . import TEMP_DIR


def setUpModule():
    # mock out user config
    global mockings
    mockings = (
        mock.patch('webscrapbook.Config.user_config_dir', return_value=os.devnull),
    )
    for mocking in mockings:
        mocking.start()

    # reload to re-init mimetypes database
    # This is required in Python < 3.9, whose http.server.SimpleHTTPRequestHandler
    # calls mimetypes.init() at class init when that module is imported, before
    # the above mockings start.
    importlib.reload(mimetypes._mimetypes)
    importlib.reload(mimetypes)


def tearDownModule():
    # stop mock
    for mocking in mockings:
        mocking.stop()

    # reload to re-init mimetypes database
    importlib.reload(mimetypes._mimetypes)
    importlib.reload(mimetypes)


class TestMimetypes(unittest.TestCase):
    def test_patch_ext2type(self):
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

    def test_patch_type2ext(self):
        self.assertEqual(
            mimetypes.guess_extension('text/javascript'),
            '.js',
        )

    def test_user_config(self):
        """Test if user config works."""
        with tempfile.TemporaryDirectory(prefix='mimetypes-', dir=TEMP_DIR) as tmpdir:
            user_config_dir = os.path.normpath(os.path.join(tmpdir, WSB_USER_DIR))
            os.makedirs(user_config_dir)
            with open(os.path.join(user_config_dir, mimetypes.WSB_USER_MIMETYPES), 'w', encoding='UTF-8') as fh:
                fh.write("""\
user/type        js
text/javascript  userext
""")

            try:
                with mock.patch('webscrapbook.Config.user_config_dir', return_value=user_config_dir):
                    # reload to re-init mimetypes database
                    importlib.reload(mimetypes._mimetypes)
                    importlib.reload(mimetypes)

                    # last-win (overwrite built-in)
                    self.assertEqual(
                        mimetypes.guess_type('abc.js'),
                        ('user/type', None),
                    )

                    # first-win (add to last extension)
                    self.assertEqual(
                        mimetypes.guess_all_extensions('text/javascript').pop(),
                        '.userext',
                    )
            finally:
                # reload to re-init mimetypes database
                importlib.reload(mimetypes._mimetypes)
                importlib.reload(mimetypes)


if __name__ == '__main__':
    unittest.main()
