from unittest import mock
import unittest
import sys
import os
import shutil
import io
import zipfile
import time
from flask import current_app, request
import webscrapbook
from webscrapbook import WSB_DIR, WSB_CONFIG
from webscrapbook import app as wsbapp

root_dir = os.path.abspath(os.path.dirname(__file__))
server_root = os.path.join(root_dir, 'test_app_helpers')

def setUpModule():
    # mock out user config
    global mockings
    mockings = [
        mock.patch('webscrapbook.WSB_USER_DIR', server_root, 'wsb'),
        mock.patch('webscrapbook.WSB_USER_CONFIG', server_root),
        ]
    for mocking in mockings:
        mocking.start()

def tearDownModule():
    # stop mock
    for mocking in mockings:
        mocking.stop()

class TestFunctions(unittest.TestCase):
    def test_is_local_access(self):
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)

        # host is localhost
        with app.test_request_context('/',
                base_url='http://127.0.0.1',
                environ_base={'REMOTE_ADDR': '192.168.0.100'}):
            self.assertTrue(wsbapp.is_local_access())

        # host (with port) is localhost
        with app.test_request_context('/',
                base_url='http://127.0.0.1:8000',
                environ_base={'REMOTE_ADDR': '192.168.0.100'}):
            self.assertTrue(wsbapp.is_local_access())

        # remote is localhost
        with app.test_request_context('/',
                base_url='http://192.168.0.1',
                environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            self.assertTrue(wsbapp.is_local_access())

        # host = remote
        with app.test_request_context('/',
                base_url='http://example.com',
                environ_base={'REMOTE_ADDR': 'example.com'}):
            self.assertTrue(wsbapp.is_local_access())

        # host (with port) = remote
        with app.test_request_context('/',
                base_url='http://example.com:8000',
                environ_base={'REMOTE_ADDR': 'example.com'}):
            self.assertTrue(wsbapp.is_local_access())

        # otherwise non-local
        with app.test_request_context('/',
                base_url='http://example.com',
                environ_base={'REMOTE_ADDR': '192.168.0.100'}):
            self.assertFalse(wsbapp.is_local_access())

    def test_get_archive_path1(self):
        """Basic logic for a sub-archive path."""
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)
        with app.app_context():
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    pass

                self.assertEqual(wsbapp.get_archive_path('/entry.zip'), ['/entry.zip'])
                self.assertEqual(wsbapp.get_archive_path('/entry.zip!'), ['/entry.zip!'])
                self.assertEqual(wsbapp.get_archive_path('/entry.zip!/'), ['/entry.zip', ''])
                self.assertEqual(wsbapp.get_archive_path('/entry.zip!/subdir'), ['/entry.zip', 'subdir'])
                self.assertEqual(wsbapp.get_archive_path('/entry.zip!/subdir/'), ['/entry.zip', 'subdir'])
                self.assertEqual(wsbapp.get_archive_path('/entry.zip!/index.html'), ['/entry.zip', 'index.html'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

    def test_get_archive_path2(self):
        """Handle conflicting file or directory."""
        # entry.zip!/entry1.zip!/ = entry.zip!/entry1.zip! >
        # entry.zip!/entry1.zip >
        # entry.zip!/ = entry.zip! >
        # entry.zip
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)
        with app.app_context():
            # entry.zip!/entry1.zip!/ > entry.zip!/entry1.zip
            try:
                os.makedirs(os.path.join(root, 'entry.zip!', 'entry1.zip!'), exist_ok=True)
                with zipfile.ZipFile(os.path.join(root, 'entry.zip!', 'entry1.zip'), 'w') as zip:
                    pass
                with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zip:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/'),
                    ['/entry.zip!/entry1.zip!'])
            finally:
                try:
                    shutil.rmtree(os.path.join(root, 'entry.zip!'))
                except NotADirectoryError:
                    os.remove(os.path.join(root, 'entry.zip!'))
                except FileNotFoundError:
                    pass
                try:
                    os.remove(os.path.join(root, 'entry.zip'))
                except FileNotFoundError:
                    pass

            # entry.zip!/entry1.zip! > entry.zip!/entry1.zip
            try:
                os.makedirs(os.path.join(root, 'entry.zip!'), exist_ok=True)
                with open(os.path.join(root, 'entry.zip!', 'entry1.zip!'), 'w') as f:
                    pass
                with zipfile.ZipFile(os.path.join(root, 'entry.zip!', 'entry1.zip'), 'w') as zip:
                    pass
                with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zip:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/'),
                    ['/entry.zip!/entry1.zip!'])
            finally:
                try:
                    shutil.rmtree(os.path.join(root, 'entry.zip!'))
                except NotADirectoryError:
                    os.remove(os.path.join(root, 'entry.zip!'))
                except FileNotFoundError:
                    pass
                try:
                    os.remove(os.path.join(root, 'entry.zip'))
                except FileNotFoundError:
                    pass

            # entry.zip!/entry1.zip > entry.zip!/
            try:
                os.makedirs(os.path.join(root, 'entry.zip!'), exist_ok=True)
                with zipfile.ZipFile(os.path.join(root, 'entry.zip!', 'entry1.zip'), 'w') as zip:
                    pass
                with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zip:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/'),
                    ['/entry.zip!/entry1.zip', ''])
            finally:
                try:
                    shutil.rmtree(os.path.join(root, 'entry.zip!'))
                except NotADirectoryError:
                    os.remove(os.path.join(root, 'entry.zip!'))
                except FileNotFoundError:
                    pass
                try:
                    os.remove(os.path.join(root, 'entry.zip'))
                except FileNotFoundError:
                    pass

            # entry.zip!/ > entry.zip
            try:
                os.makedirs(os.path.join(root, 'entry.zip!'), exist_ok=True)
                with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zip:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/'),
                    ['/entry.zip!/entry1.zip!'])
            finally:
                try:
                    shutil.rmtree(os.path.join(root, 'entry.zip!'))
                except NotADirectoryError:
                    os.remove(os.path.join(root, 'entry.zip!'))
                except FileNotFoundError:
                    pass
                try:
                    os.remove(os.path.join(root, 'entry.zip'))
                except FileNotFoundError:
                    pass

            # entry.zip! > entry.zip
            try:
                with open(os.path.join(root, 'entry.zip!'), 'w') as f:
                    pass
                with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zip:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/'),
                    ['/entry.zip!/entry1.zip!'])
            finally:
                try:
                    shutil.rmtree(os.path.join(root, 'entry.zip!'))
                except NotADirectoryError:
                    os.remove(os.path.join(root, 'entry.zip!'))
                except FileNotFoundError:
                    pass
                try:
                    os.remove(os.path.join(root, 'entry.zip'))
                except FileNotFoundError:
                    pass

            # entry.zip
            try:
                with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zip:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/'),
                    ['/entry.zip', 'entry1.zip!'])
            finally:
                try:
                    shutil.rmtree(os.path.join(root, 'entry.zip!'))
                except NotADirectoryError:
                    os.remove(os.path.join(root, 'entry.zip!'))
                except FileNotFoundError:
                    pass
                try:
                    os.remove(os.path.join(root, 'entry.zip'))
                except FileNotFoundError:
                    pass

            # other
            try:
                with open(os.path.join(root, 'entry.zip'), 'w') as f:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/'),
                    ['/entry.zip!/entry1.zip!'])
            finally:
                try:
                    shutil.rmtree(os.path.join(root, 'entry.zip!'))
                except NotADirectoryError:
                    os.remove(os.path.join(root, 'entry.zip!'))
                except FileNotFoundError:
                    pass
                try:
                    os.remove(os.path.join(root, 'entry.zip'))
                except FileNotFoundError:
                    pass

    def test_get_archive_path3(self):
        """Handle recursive sub-archive path."""
        # entry1.zip!/entry2.zip!/ >
        # entry1.zip!/entry2.zip >
        # entry1.zip!/ >
        # entry1.zip entry2.zip!/ >
        # entry1.zip entry2.zip >
        # entry1.zip >
        # other
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)
        with app.app_context():
            # entry1.zip!/entry2.zip!/ > entry1.zip!/entry2.zip
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    zip.writestr('entry1.zip!/entry2.zip!/', '')

                    buf2 = io.BytesIO()
                    with zipfile.ZipFile(buf2, 'w') as zip2:
                        pass
                    zip.writestr('entry1.zip!/entry2.zip', buf2.getvalue())

                    zip.writestr('entry1.zip!/', '')

                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip!', '')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip!/entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip!/entry2.zip!/ > entry1.zip!/entry2.zip
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    zip.writestr('entry1.zip!/entry2.zip!/.gitkeep', '')

                    buf2 = io.BytesIO()
                    with zipfile.ZipFile(buf2, 'w') as zip2:
                        pass
                    zip.writestr('entry1.zip!/entry2.zip', buf2.getvalue())

                    zip.writestr('entry1.zip!/', '')

                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip!', '')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip!/entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip!/entry2.zip > entry1.zip!/
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf2 = io.BytesIO()
                    with zipfile.ZipFile(buf2, 'w') as zip2:
                        pass
                    zip.writestr('entry1.zip!/entry2.zip', buf2.getvalue())

                    zip.writestr('entry1.zip!/', '')

                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip!', '')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip!/entry2.zip', ''])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip!/ > entry1.zip entry2.zip!/
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    zip.writestr('entry1.zip!/entry2.zip', 'non-zip')

                    zip.writestr('entry1.zip!/', '')

                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip!', '')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip!/entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip!/ > entry1.zip entry2.zip!/
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    zip.writestr('entry1.zip!/', '')

                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip!', '')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip!/entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip!/ > entry1.zip entry2.zip!/
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    zip.writestr('entry1.zip!/.gitkeep', '')

                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip!', '')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip!/entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip entry2.zip!/ > entry1.zip entry2.zip
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip!/', '')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip', 'entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip entry2.zip!/ > entry1.zip entry2.zip
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip!/.gitkeep', '')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip', 'entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip entry2.zip > entry1.zip
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w'):
                            pass
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip', 'entry2.zip', ''])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # entry1.zip
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        zip1.writestr('entry2.zip', 'non-zip')
                    zip.writestr('entry1.zip', buf1.getvalue())

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip', 'entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # other
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    zip.writestr('entry1.zip', 'non-zip')

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip!/entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # other
            tempfile = os.path.join(root, 'entry.zip')
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('/entry.zip!/entry1.zip!/entry2.zip!/'),
                    ['/entry.zip', 'entry1.zip!/entry2.zip!'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

    def test_get_archive_path4(self):
        """Tidy path."""
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)
        with app.app_context():
            tempdir = os.path.join(root, 'foo', 'bar')
            tempfile = os.path.join(tempdir, 'entry.zip')
            try:
                os.makedirs(tempdir, exist_ok=True)
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    pass

                self.assertEqual(
                    wsbapp.get_archive_path('//foo///bar////entry.zip//'),
                    ['/foo/bar/entry.zip'])
                self.assertEqual(
                    wsbapp.get_archive_path('/./foo/././bar/./././entry.zip/./'),
                    ['/foo/bar/entry.zip'])
                self.assertEqual(
                    wsbapp.get_archive_path('/foo/wtf/../bar/wtf/./wtf2/.././../entry.zip'),
                    ['/foo/bar/entry.zip'])
                self.assertEqual(
                    wsbapp.get_archive_path('/../../../'),
                    ['/'])
                self.assertEqual(
                    wsbapp.get_archive_path('/foo/bar/entry.zip!//foo//bar///baz.txt//'),
                    ['/foo/bar/entry.zip', 'foo/bar/baz.txt'])
                self.assertEqual(
                    wsbapp.get_archive_path('/foo/bar/entry.zip!/./foo/./bar/././baz.txt/./'),
                    ['/foo/bar/entry.zip', 'foo/bar/baz.txt'])
                self.assertEqual(
                    wsbapp.get_archive_path('/foo/bar/entry.zip!/foo/wtf/../bar/wtf/./wtf2/../../baz.txt'),
                    ['/foo/bar/entry.zip', 'foo/bar/baz.txt'])
                self.assertEqual(
                    wsbapp.get_archive_path('/foo/bar/entry.zip!/../../'),
                    ['/foo/bar/entry.zip', ''])
            finally:
                try:
                    shutil.rmtree(tempdir)
                except NotADirectoryError:
                    os.remove(tempdir)
                except FileNotFoundError:
                    pass

    def test_open_archive_path_read(self):
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        tempfile = os.path.join(root, 'entry.zip')
        app = wsbapp.make_app(root)
        with app.app_context():
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        buf11 = io.BytesIO()
                        with zipfile.ZipFile(buf11, 'w') as zip2:
                            zip2.writestr('subdir/index.html', 'Hello World!')
                        zip1.writestr('entry2.zip', buf11.getvalue())
                    zip.writestr('entry1.zip', buf1.getvalue())

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'entry2.zip', 'subdir/index.html']) as zip:
                    self.assertEqual(zip.read('subdir/index.html').decode('UTF-8'), 'Hello World!')

                with self.assertRaises(ValueError):
                    with wsbapp.open_archive_path([tempfile]) as zip:
                        pass
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

    def test_open_archive_path_write(self):
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        tempfile = os.path.join(root, 'entry.zip')
        app = wsbapp.make_app(root)
        with app.app_context():
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    zip.comment = 'test zip comment 測試'.encode('UTF-8')
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        zip1.comment = 'test zip comment 1 測試'.encode('UTF-8')
                        zip1.writestr('subdir/index.html', 'Hello World!')
                    zip.writestr('entry1.zip', buf1.getvalue())

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html'], 'w') as zip:
                    # existed
                    zip.writestr('subdir/index.html', 'rewritten 測試')

                    # new
                    zip.writestr('newdir/test.txt', 'new file 測試')

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html']) as zip:
                    # existed
                    self.assertEqual(zip.read('subdir/index.html').decode('UTF-8'), 'rewritten 測試')

                    # new
                    self.assertEqual(zip.read('newdir/test.txt').decode('UTF-8'), 'new file 測試')

                # check comments are kept
                with wsbapp.open_archive_path([tempfile, '']) as zip:
                    self.assertEqual(zip.comment.decode('UTF-8'), 'test zip comment 測試')

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html']) as zip:
                    self.assertEqual(zip.comment.decode('UTF-8'), 'test zip comment 1 測試')
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

    def test_open_archive_path_delete(self):
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        tempfile = os.path.join(root, 'entry.zip')
        app = wsbapp.make_app(root)
        with app.app_context():
            # file
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        zip1.writestr('subdir/', '')
                        zip1.writestr('subdir/index.html', 'Hello World!')
                        zip1.writestr('subdir2/test.txt', 'dummy')
                    zip.writestr('entry1.zip', buf1.getvalue())

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html'], 'w', ['subdir/index.html']) as zip:
                    pass

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html']) as zip:
                    self.assertEqual(zip.namelist(), ['subdir/', 'subdir2/test.txt'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # explicit directory
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        zip1.writestr('subdir/', '')
                        zip1.writestr('subdir/index.html', 'Hello World!')
                        zip1.writestr('subdir2/test.txt', 'dummy')
                    zip.writestr('entry1.zip', buf1.getvalue())

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html'], 'w', ['subdir']) as zip:
                    pass

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html']) as zip:
                    self.assertEqual(zip.namelist(), ['subdir2/test.txt'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # implicit directory
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        zip1.writestr('subdir/', '')
                        zip1.writestr('subdir/index.html', 'Hello World!')
                        zip1.writestr('subdir2/test.txt', 'dummy')
                    zip.writestr('entry1.zip', buf1.getvalue())

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html'], 'w', ['subdir2']) as zip:
                    pass

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html']) as zip:
                    self.assertEqual(zip.namelist(), ['subdir/', 'subdir/index.html'])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # root (as an implicit directory)
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        zip1.writestr('subdir/', '')
                        zip1.writestr('subdir/index.html', 'Hello World!')
                        zip1.writestr('subdir2/test.txt', 'dummy')
                    zip.writestr('entry1.zip', buf1.getvalue())

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html'], 'w', ['']) as zip:
                    pass

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html']) as zip:
                    self.assertEqual(zip.namelist(), [])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

            # multiple
            try:
                with zipfile.ZipFile(tempfile, 'w') as zip:
                    buf1 = io.BytesIO()
                    with zipfile.ZipFile(buf1, 'w') as zip1:
                        zip1.writestr('subdir/', '')
                        zip1.writestr('subdir/index.html', 'Hello World!')
                        zip1.writestr('subdir2/test.txt', 'dummy')
                    zip.writestr('entry1.zip', buf1.getvalue())

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html'], 'w', ['subdir', 'subdir2']) as zip:
                    pass

                with wsbapp.open_archive_path([tempfile, 'entry1.zip', 'subdir/index.html']) as zip:
                    self.assertEqual(zip.namelist(), [])
            finally:
                try:
                    os.remove(tempfile)
                except FileNotFoundError:
                    pass

    def test_get_breadcrumbs(self):
        # directory
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/directory/'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('directory', '/path/to/directory/', '/', True)
            ])

        # conflicting directory/file
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/fake.ext!/'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('fake.ext!', '/path/to/fake.ext!/', '/', True),
            ])

        # sub-archive path(s)
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', True),
            ])

        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', 'subdir'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/subdir/', '/', True),
            ])

        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', 'nested1.zip', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('nested1.zip', '/path/to/archive.ext!/nested1.zip!/', '!/', True),
            ])

        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', 'nested1.zip', 'subdir'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('nested1.zip', '/path/to/archive.ext!/nested1.zip!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/nested1.zip!/subdir/', '/', True),
            ])

        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', 'subdir/nested1.zip', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/subdir/', '/', False),
            ('nested1.zip', '/path/to/archive.ext!/subdir/nested1.zip!/', '!/', True),
            ])

        # base
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/directory/'], base='/wsb')), [
            ('.', '/wsb/', '/', False),
            ('path', '/wsb/path/', '/', False),
            ('to', '/wsb/path/to/', '/', False),
            ('directory', '/wsb/path/to/directory/', '/', True),
            ])

        # base (with slash)
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/directory/'], base='/wsb/')), [
            ('.', '/wsb/', '/', False),
            ('path', '/wsb/path/', '/', False),
            ('to', '/wsb/path/to/', '/', False),
            ('directory', '/wsb/path/to/directory/', '/', True),
            ])

        # topname
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/directory/'], topname='MyWsb')), [
            ('MyWsb', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('directory', '/path/to/directory/', '/', True)
            ])

    @mock.patch('webscrapbook.util.encrypt', side_effect=webscrapbook.util.encrypt)
    def test_get_permission1(self, mock_encrypt):
        """Return corresponding permission for the matched user and '' for unmatched."""
        root = os.path.join(root_dir, 'test_app_helpers', 'get_permission1')
        app = wsbapp.make_app(root)
        auth_config = app.config['WEBSCRAPBOOK_HOST'].config['auth']
        with app.app_context():
            # util.encrypt should be called with the inputting password
            # and the salt and method for the matched user
            mock_encrypt.reset_mock()

            self.assertEqual(wsbapp.get_permission({'username': 'user1', 'password': 'pass1'}, auth_config), '')
            mock_encrypt.assert_called_with('pass1', '', 'plain')

            self.assertEqual(wsbapp.get_permission({'username': 'user2', 'password': 'pass2'}, auth_config), 'view')
            mock_encrypt.assert_called_with('pass2', 'salt', 'plain')

            self.assertEqual(wsbapp.get_permission({'username': 'user3', 'password': 'pass3'}, auth_config), 'read')
            mock_encrypt.assert_called_with('pass3', '', 'sha1')

            self.assertEqual(wsbapp.get_permission({'username': 'user4', 'password': 'pass4'}, auth_config), 'all')
            mock_encrypt.assert_called_with('pass4', 'salt4', 'sha256')

            # Password check should be handled by util.encrypt properly.
            # Here are just some quick fail tests for certain cases:
            # - empty input should not work
            # - inputting password + salt should not work
            # - inputting hashed value should not work
            mock_encrypt.reset_mock()

            self.assertEqual(wsbapp.get_permission({'username': 'user4', 'password': ''}, auth_config), '')
            mock_encrypt.assert_called_with('', 'salt4', 'sha256')

            self.assertEqual(wsbapp.get_permission({'username': 'user4', 'password': 'salt4'}, auth_config), '')
            mock_encrypt.assert_called_with('salt4', 'salt4', 'sha256')

            self.assertEqual(wsbapp.get_permission({'username': 'user4', 'password': '49d1445a2989c509c5b5b1f78e092e3f30f05b1d219fd975ac77ff645ea68d53'}, auth_config), '')
            mock_encrypt.assert_called_with('49d1445a2989c509c5b5b1f78e092e3f30f05b1d219fd975ac77ff645ea68d53', 'salt4', 'sha256')

            # util.encrypt should NOT be called for an unmatched user
            mock_encrypt.reset_mock()

            self.assertEqual(wsbapp.get_permission(None, auth_config), '')
            mock_encrypt.assert_not_called()

            self.assertEqual(wsbapp.get_permission({'username': '', 'password': ''}, auth_config), '')
            mock_encrypt.assert_not_called()

            self.assertEqual(wsbapp.get_permission({'username': '', 'password': 'pass'}, auth_config), '')
            mock_encrypt.assert_not_called()

            self.assertEqual(wsbapp.get_permission({'username': 'userx', 'password': ''}, auth_config), '')
            mock_encrypt.assert_not_called()

            self.assertEqual(wsbapp.get_permission({'username': 'userx', 'password': 'pass'}, auth_config), '')
            mock_encrypt.assert_not_called()

    @mock.patch('webscrapbook.util.encrypt', side_effect=webscrapbook.util.encrypt)
    def test_get_permission2(self, mock_encrypt):
        """Use empty user and password if not provided."""
        root = os.path.join(root_dir, 'test_app_helpers', 'get_permission2')
        app = wsbapp.make_app(root)
        auth_config = app.config['WEBSCRAPBOOK_HOST'].config['auth']
        with app.app_context():
            self.assertEqual(wsbapp.get_permission(None, auth_config), 'view')
            mock_encrypt.assert_called_with('', 'salt', 'plain')

            self.assertEqual(wsbapp.get_permission({'username': '', 'password': ''}, auth_config), 'view')
            mock_encrypt.assert_called_with('', 'salt', 'plain')

    @mock.patch('webscrapbook.util.encrypt', side_effect=webscrapbook.util.encrypt)
    def test_get_permission3(self, mock_encrypt):
        """Use permission for the first matched user and password."""
        root = os.path.join(root_dir, 'test_app_helpers', 'get_permission3')
        app = wsbapp.make_app(root)
        auth_config = app.config['WEBSCRAPBOOK_HOST'].config['auth']
        with app.app_context():
            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.get_permission({'username': '', 'password': ''}, auth_config), 'view')
            mock_encrypt.assert_called_once_with('', 'salt', 'plain')

            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.get_permission({'username': 'user1', 'password': 'pass1'}, auth_config), 'read')
            self.assertEqual(mock_encrypt.call_args_list[0][0], ('pass1', 'salt', 'plain'))
            self.assertEqual(mock_encrypt.call_args_list[1][0], ('pass1', 'salt', 'plain'))

    def test_verify_authorization(self):
        for action in {'view', 'info', 'source', 'download', 'static'}:
            with self.subTest(action=action):
                self.assertFalse(wsbapp.verify_authorization('', action))
                self.assertTrue(wsbapp.verify_authorization('view', action))
                self.assertTrue(wsbapp.verify_authorization('read', action))
                self.assertTrue(wsbapp.verify_authorization('all', action))

        for action in {'list', 'edit', 'editx', 'exec', 'browse', 'config', 'unknown'}:
            with self.subTest(action=action):
                self.assertFalse(wsbapp.verify_authorization('', action))
                self.assertFalse(wsbapp.verify_authorization('view', action))
                self.assertTrue(wsbapp.verify_authorization('read', action))
                self.assertTrue(wsbapp.verify_authorization('all', action))

        for action in {'token', 'lock', 'unlock', 'mkdir', 'mkzip', 'save', 'delete', 'move', 'copy', 'backup', 'unbackup', 'cache', 'check'}:
            with self.subTest(action=action):
                self.assertFalse(wsbapp.verify_authorization('', action))
                self.assertFalse(wsbapp.verify_authorization('view', action))
                self.assertFalse(wsbapp.verify_authorization('read', action))
                self.assertTrue(wsbapp.verify_authorization('all', action))

    def test_make_app1(self):
        # pass root
        root = os.path.join(root_dir, 'test_app_helpers', 'make_app1')

        app = wsbapp.make_app(root)
        with app.app_context():
            self.assertEqual(current_app.config['WEBSCRAPBOOK_HOST'].config['app']['name'], 'mywsb1')

    def test_make_app2(self):
        # pass root, config
        root = os.path.join(root_dir, 'test_app_helpers', 'make_app1')
        config_dir = os.path.join(root_dir, 'test_app_helpers', 'make_app2')
        config = webscrapbook.Config()
        config.load(config_dir)

        app = wsbapp.make_app(root, config)
        with app.app_context():
            self.assertEqual(current_app.config['WEBSCRAPBOOK_HOST'].config['app']['name'], 'mywsb2')

class TestRequest(unittest.TestCase):
    def test_action(self):
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)
        with app.test_client() as c:
            r = c.get('/index.html')
            self.assertEqual(request.action, 'view')

            r = c.get('/index.html', query_string={'action': 'source'})
            self.assertEqual(request.action, 'source')

            r = c.get('/index.html', query_string={'a': 'source'})
            self.assertEqual(request.action, 'source')

            r = c.get('/index.html', query_string={'a': 'source', 'action': 'static'})
            self.assertEqual(request.action, 'static')

    def test_format(self):
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)
        with app.test_client() as c:
            r = c.get('/index.html')
            self.assertEqual(request.format, None)

            r = c.get('/index.html', query_string={'format': 'json'})
            self.assertEqual(request.format, 'json')

            r = c.get('/index.html', query_string={'f': 'json'})
            self.assertEqual(request.format, 'json')

            r = c.get('/index.html', query_string={'f': 'json', 'format': 'sse'})
            self.assertEqual(request.format, 'sse')

class TestHandlers(unittest.TestCase):
    def test_handle_error(self):
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)

        # json
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'list', 'f': 'json'})
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {
                'error': {
                    'status': 404,
                    'message': 'Directory does not exist.'
                    }
                })

        # other
        with app.test_client() as c:
            r = c.get('/nonexist')
            self.assertEqual(r.status_code, 404)
            html = r.data.decode('UTF-8')
            self.assertIn('<h1>Not Found</h1>', html)



class TestWebHost(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(root_dir, 'test_app_helpers', 'general')
        self.token_dir = os.path.join(root_dir, 'test_app_helpers', 'general', WSB_DIR, 'server', 'tokens')
        os.makedirs(self.token_dir, exist_ok=True)

    def tearDown(self):
        try:
            shutil.rmtree(self.token_dir)
        except NotADirectoryError:
            os.remove(self.token_dir)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.WebHost.token_check_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_DEFAULT_EXPIRY', 10)
    def test_token_acquire1(self, mock_check):
        now = time.time()
        expected_expire_time = int(now) + 10

        handler = wsbapp.WebHost(self.test_dir)
        token = handler.token_acquire()
        token_file = os.path.join(self.token_dir, token)

        self.assertTrue(os.path.isfile(token_file))
        with open(token_file, 'r', encoding='UTF-8') as f:
            self.assertAlmostEqual(int(f.read()), expected_expire_time, delta=1)
        self.assertAlmostEqual(mock_check.call_args[0][0], now, delta=1)

    @mock.patch('webscrapbook.app.WebHost.token_check_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_DEFAULT_EXPIRY', 30)
    def test_token_acquire2(self, mock_check):
        now = 30000
        expected_expire_time = int(now) + 30

        handler = wsbapp.WebHost(self.test_dir)
        token = handler.token_acquire(now)
        token_file = os.path.join(self.token_dir, token)

        self.assertTrue(os.path.isfile(token_file))
        with open(token_file, 'r', encoding='UTF-8') as f:
            self.assertEqual(int(f.read()), expected_expire_time)
        self.assertEqual(mock_check.call_args[0][0], now)

    def test_token_validate1(self):
        token = 'sampleToken'
        token_time = int(time.time()) + 3

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(token_time))

        handler = wsbapp.WebHost(self.test_dir)
        self.assertTrue(handler.token_validate(token))

    def test_token_validate2(self):
        token = 'sampleToken'
        token_time = int(time.time()) - 3

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(token_time))

        handler = wsbapp.WebHost(self.test_dir)
        self.assertFalse(handler.token_validate(token))

    def test_token_validate3(self):
        token = 'sampleToken'
        now = 30000
        token_time = 30001

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(token_time))

        handler = wsbapp.WebHost(self.test_dir)
        self.assertTrue(handler.token_validate(token, now))

    def test_token_validate4(self):
        token = 'sampleToken'
        now = 30000
        token_time = 29999

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(token_time))

        handler = wsbapp.WebHost(self.test_dir)
        self.assertFalse(handler.token_validate(token, now))

    def test_token_delete(self):
        token = 'sampleToken'

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(32768))

        handler = wsbapp.WebHost(self.test_dir)
        handler.token_delete(token)
        self.assertFalse(os.path.exists(token_file))

    def test_token_delete_expire1(self):
        now = int(time.time())

        with open(os.path.join(self.token_dir, 'sampleToken1'), 'w', encoding='UTF-8') as f:
            f.write(str(now - 100))
        with open(os.path.join(self.token_dir, 'sampleToken2'), 'w', encoding='UTF-8') as f:
            f.write(str(now - 10))
        with open(os.path.join(self.token_dir, 'sampleToken3'), 'w', encoding='UTF-8') as f:
            f.write(str(now + 10))
        with open(os.path.join(self.token_dir, 'sampleToken4'), 'w', encoding='UTF-8') as f:
            f.write(str(now + 100))

        handler = wsbapp.WebHost(self.test_dir)
        handler.token_delete_expire()

        self.assertFalse(os.path.exists(os.path.join(self.token_dir, 'sampleToken1')))
        self.assertFalse(os.path.exists(os.path.join(self.token_dir, 'sampleToken2')))
        self.assertTrue(os.path.exists(os.path.join(self.token_dir, 'sampleToken3')))
        self.assertTrue(os.path.exists(os.path.join(self.token_dir, 'sampleToken4')))

    def test_token_delete_expire2(self):
        now = 30000

        with open(os.path.join(self.token_dir, 'sampleToken1'), 'w', encoding='UTF-8') as f:
            f.write(str(29000))
        with open(os.path.join(self.token_dir, 'sampleToken2'), 'w', encoding='UTF-8') as f:
            f.write(str(29100))
        with open(os.path.join(self.token_dir, 'sampleToken3'), 'w', encoding='UTF-8') as f:
            f.write(str(30100))
        with open(os.path.join(self.token_dir, 'sampleToken4'), 'w', encoding='UTF-8') as f:
            f.write(str(30500))

        handler = wsbapp.WebHost(self.test_dir)
        handler.token_delete_expire(now)

        self.assertFalse(os.path.exists(os.path.join(self.token_dir, 'sampleToken1')))
        self.assertFalse(os.path.exists(os.path.join(self.token_dir, 'sampleToken2')))
        self.assertTrue(os.path.exists(os.path.join(self.token_dir, 'sampleToken3')))
        self.assertTrue(os.path.exists(os.path.join(self.token_dir, 'sampleToken4')))

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    def test_token_check_delete_expire1(self, mock_delete):
        now = int(time.time())

        handler = wsbapp.WebHost(self.test_dir)
        self.assertEqual(handler.token_last_purge, 0)

        handler.token_check_delete_expire()
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.token_last_purge, now, delta=1)

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_PURGE_INTERVAL', 1000)
    def test_token_check_delete_expire2(self, mock_delete):
        now = int(time.time())

        handler = wsbapp.WebHost(self.test_dir)
        handler.token_last_purge = now - 1100

        handler.token_check_delete_expire()
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.token_last_purge, now, delta=1)

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_PURGE_INTERVAL', 1000)
    def test_token_check_delete_expire3(self, mock_delete):
        now = int(time.time())

        handler = wsbapp.WebHost(self.test_dir)
        handler.token_last_purge = now - 900

        handler.token_check_delete_expire()
        mock_delete.assert_not_called()
        self.assertEqual(handler.token_last_purge, now - 900)

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_PURGE_INTERVAL', 1000)
    def test_token_check_delete_expire4(self, mock_delete):
        now = 40000

        handler = wsbapp.WebHost(self.test_dir)
        handler.token_last_purge = now - 1100

        handler.token_check_delete_expire(now)
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.token_last_purge, now, delta=1)

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_PURGE_INTERVAL', 1000)
    def test_token_check_delete_expire5(self, mock_delete):
        now = 40000

        handler = wsbapp.WebHost(self.test_dir)
        handler.token_last_purge = now - 900

        handler.token_check_delete_expire(now)
        mock_delete.assert_not_called()
        self.assertEqual(handler.token_last_purge, now - 900)

if __name__ == '__main__':
    unittest.main()
