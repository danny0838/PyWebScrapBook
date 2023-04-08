import unittest

from webscrapbook._polyfill import mimetypes


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
            ('application/javascript', None),
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
