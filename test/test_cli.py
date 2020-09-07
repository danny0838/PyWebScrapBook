from unittest import mock
import unittest
import sys
import os
import shutil
import io
import zipfile
import re
from urllib.request import pathname2url
from tempfile import gettempdir
from webscrapbook import WSB_DIR, WSB_LOCAL_CONFIG
from webscrapbook import Config
from webscrapbook import cli

root_dir = os.path.abspath(os.path.dirname(__file__))
test_dir = os.path.join(root_dir, 'test_cli')
resource_dir = os.path.join(root_dir, '..', 'webscrapbook', 'resources')

class TestServe(unittest.TestCase):
    @mock.patch('sys.stdout', io.StringIO)
    @mock.patch('webscrapbook.cli.server')
    def test_call(self, mock_server):
        cli.cmd_serve({
            'root': test_dir,
            })

        self.assertEqual(mock_server.mock_calls[0], ('serve', (test_dir,), {}))

class TestConfig(unittest.TestCase):
    def tearDown(self):
        try:
            shutil.rmtree(os.path.join(test_dir, WSB_DIR))
        except NotADirectoryError:
            os.remove(os.path.join(test_dir, WSB_DIR))
        except FileNotFoundError:
            pass

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_book_create(self, mock_stdout):
        cli.cmd_config({
            'root': test_dir,
            'book': True,
            'user': False,
            'all': False,
            'edit': False,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'config.ini')) as f1:
            with open(os.path.join(resource_dir, 'config.ini')) as f2:
                self.assertTrue(f1.read(), f2.read())

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_book_create2(self, mock_stdout):
        """No overwrite."""
        os.makedirs(os.path.join(test_dir, WSB_DIR), exist_ok=True)
        with open(os.path.join(test_dir, WSB_DIR, 'config.ini'), 'w') as f:
            f.write('dummy')

        cli.cmd_config({
            'root': test_dir,
            'book': True,
            'user': False,
            'all': False,
            'edit': False,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'dummy')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.launch')
    def test_book_edit(self, mock_launch, mock_stdout):
        cli.cmd_config({
            'root': test_dir,
            'book': True,
            'user': False,
            'all': False,
            'edit': True,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'config.ini')) as f1:
            with open(os.path.join(resource_dir, 'config.ini')) as f2:
                self.assertTrue(f1.read(), f2.read())

        mock_launch.assert_called_once_with(os.path.join(test_dir, WSB_DIR, 'config.ini'))

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.launch')
    def test_book_edit2(self, mock_launch, mock_stdout):
        os.makedirs(os.path.join(test_dir, WSB_DIR), exist_ok=True)
        with open(os.path.join(test_dir, WSB_DIR, 'config.ini'), 'w') as f:
            f.write('foo')

        cli.cmd_config({
            'root': test_dir,
            'book': True,
            'user': False,
            'all': False,
            'edit': True,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'foo')

        mock_launch.assert_called_once_with(os.path.join(test_dir, WSB_DIR, 'config.ini'))

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_book_all(self, mock_stdout):
        cli.cmd_config({
            'root': test_dir,
            'book': True,
            'user': False,
            'all': True,
            'edit': False,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'config.ini')) as f1:
            with open(os.path.join(resource_dir, 'config.ini')) as f2:
                self.assertTrue(f1.read(), f2.read())

        with open(os.path.join(test_dir, WSB_DIR, 'serve.py')) as f1:
            with open(os.path.join(resource_dir, 'serve.py')) as f2:
                self.assertTrue(f1.read(), f2.read())

        with open(os.path.join(test_dir, WSB_DIR, 'app.py')) as f1:
            with open(os.path.join(resource_dir, 'app.py')) as f2:
                self.assertTrue(f1.read(), f2.read())

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_book_all2(self, mock_stdout):
        """No overwrite."""
        os.makedirs(os.path.join(test_dir, WSB_DIR), exist_ok=True)
        with open(os.path.join(test_dir, WSB_DIR, 'config.ini'), 'w') as f:
            f.write('dummy1')
        with open(os.path.join(test_dir, WSB_DIR, 'serve.py'), 'w') as f:
            f.write('dummy2')
        with open(os.path.join(test_dir, WSB_DIR, 'app.py'), 'w') as f:
            f.write('dummy3')

        cli.cmd_config({
            'root': test_dir,
            'book': True,
            'user': False,
            'all': True,
            'edit': False,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'dummy1')

        with open(os.path.join(test_dir, WSB_DIR, 'serve.py')) as f1:
            self.assertTrue(f1.read(), 'dummy2')

        with open(os.path.join(test_dir, WSB_DIR, 'app.py')) as f1:
            self.assertTrue(f1.read(), 'dummy3')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.WSB_USER_CONFIG', os.path.join(test_dir, WSB_DIR, 'userconfig.ini'))
    def test_user_create(self, mock_stdout):
        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': True,
            'all': False,
            'edit': False,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'userconfig.ini')) as f1:
            with open(os.path.join(resource_dir, 'config.ini')) as f2:
                self.assertTrue(f1.read(), f2.read())

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.WSB_USER_CONFIG', os.path.join(test_dir, WSB_DIR, 'userconfig.ini'))
    def test_user_create2(self, mock_stdout):
        os.makedirs(os.path.join(test_dir, WSB_DIR), exist_ok=True)
        with open(os.path.join(test_dir, WSB_DIR, 'userconfig.ini'), 'w') as f:
            f.write('dummy')

        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': True,
            'all': False,
            'edit': False,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'userconfig.ini')) as f1:
            self.assertTrue(f1.read(), 'dummy')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('webscrapbook.cli.WSB_USER_CONFIG', os.path.join(test_dir, WSB_DIR, 'userconfig.ini'))
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.launch')
    def test_user_edit(self, mock_launch, mock_stdout):
        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': True,
            'all': False,
            'edit': True,
            'name': None,
            })

        with open(os.path.join(test_dir, WSB_DIR, 'userconfig.ini')) as f1:
            with open(os.path.join(resource_dir, 'config.ini')) as f2:
                self.assertTrue(f1.read(), f2.read())

        mock_launch.assert_called_once_with(os.path.join(test_dir, WSB_DIR, 'userconfig.ini'))

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('webscrapbook.cli.WSB_USER_CONFIG', os.path.join(test_dir, WSB_DIR, 'userconfig.ini'))
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.launch')
    def test_user_edit2(self, mock_launch, mock_stdout):
        os.makedirs(os.path.join(test_dir, WSB_DIR), exist_ok=True)
        with open(os.path.join(test_dir, WSB_DIR, 'userconfig.ini'), 'w') as f:
            f.write('dummy')

        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': True,
            'all': False,
            'edit': True,
            'name': None,
            })

        mock_launch.assert_called_once_with(os.path.join(test_dir, WSB_DIR, 'userconfig.ini'))

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('sys.exit')
    def test_edit(self, mock_exit, mock_stderr):
        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': False,
            'all': False,
            'edit': True,
            'name': None,
            })

        mock_exit.assert_called_once_with(1)
        self.assertNotEqual(mock_stderr.getvalue(), '')

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('sys.exit')
    def test_all(self, mock_exit, mock_stderr):
        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': False,
            'all': True,
            'edit': False,
            'name': None,
            })

        mock_exit.assert_called_once_with(1)
        self.assertNotEqual(mock_stderr.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.config.getname', return_value='dummy')
    def test_name_call(self, mock_getname, mock_stdout):
        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': False,
            'all': False,
            'edit': False,
            'name': 'app.name',
            })

        mock_getname.assert_called_once_with('app.name')
        self.assertEqual(mock_stdout.getvalue(), 'dummy\n')

    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('webscrapbook.config.getname', return_value=None)
    def test_name_call2(self, mock_getname, mock_stderr, mock_exit):
        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': False,
            'all': False,
            'edit': False,
            'name': 'unknown.config',
            })

        mock_getname.assert_called_once_with('unknown.config')
        self.assertNotEqual(mock_stderr.getvalue(), '')
        mock_exit.assert_called_once_with(1)

    @mock.patch('webscrapbook.config.dump')
    def test_dump(self, mock_dump):
        cli.cmd_config({
            'root': test_dir,
            'book': False,
            'user': False,
            'all': False,
            'edit': False,
            'name': None,
            })

        mock_dump.assert_called_once_with(sys.stdout)

class TestEncrypt(unittest.TestCase):
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.encrypt', return_value='dummy_hash')
    def test_call(self, mock_encrypt, mock_stdout):
        cli.cmd_encrypt({
            'password': '1234',
            'salt': 'mysalt',
            'method': 'sha256',
            })

        mock_encrypt.assert_called_once_with('1234', salt='mysalt', method='sha256')
        self.assertEqual(mock_stdout.getvalue(), 'dummy_hash\n')

class TestHelp(unittest.TestCase):
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_call(self, mock_stdout):
        cli.cmd_help({
            'topic': 'config',
            })

        with open(os.path.join(resource_dir, 'config.md')) as f:
            self.assertEqual(mock_stdout.getvalue(), f.read() + '\n')

class TestView(unittest.TestCase):
    @mock.patch('webscrapbook.cli.view_archive_files')
    def test_call(self, mock_view):
        cli.cmd_view({
            'root': 'config',
            'files': [test_dir],
            })

        mock_view.assert_called_once_with([test_dir])

class TestHelpers(unittest.TestCase):
    def tearDown(self):
        try:
            shutil.rmtree(os.path.join(test_dir, 'temp'))
        except NotADirectoryError:
            os.remove(os.path.join(test_dir, 'temp'))
        except FileNotFoundError:
            pass

    @mock.patch('tempfile.gettempdir', lambda: os.path.join(test_dir, 'temp', 'tempdir'))
    @mock.patch('webbrowser.get', new_callable=mock.MagicMock())
    def test_view_archive_files(self, mock_browser):
        testfile1 = os.path.join(test_dir, 'temp', 'test1.htz')
        testfile2 = os.path.join(test_dir, 'temp', 'test2.maff')
        testfile3 = os.path.join(test_dir, 'temp', 'test3.maff')
        testfile4 = os.path.join(test_dir, 'temp', 'test4.zip')
        testtemp = os.path.join(test_dir, 'temp', 'tempdir')
        testtempprefix = os.path.join(test_dir, 'temp', 'tempdir', 'webscrapbook.')

        os.makedirs(testtemp, exist_ok=True)
        with zipfile.ZipFile(testfile1, 'w') as zh:
            zh.writestr('index.html', 'abc 測試')
        with zipfile.ZipFile(testfile2, 'w') as zh:
            zh.writestr('123456/index.html', 'abc 測試')
        with zipfile.ZipFile(testfile3, 'w') as zh:
            zh.writestr('abc/index.html', 'abc 測試')
            zh.writestr('def/index.html', 'abc 測試')
        with zipfile.ZipFile(testfile4, 'w') as zh:
            zh.writestr('index.html', 'abc 測試')

        # test jar, no temp dir should be generated
        with mock.patch('webscrapbook.cli.config', {
                'browser': {
                    'command': '',
                    'cache_prefix': 'webscrapbook.',
                    'cache_expire': 1000,
                    'use_jar': True,
                    }
                }):
            cli.view_archive_files([testfile1, testfile2, testfile3, testfile4])

        self.assertEqual(len(mock_browser.mock_calls), 5)
        self.assertEqual(mock_browser.mock_calls[1][1][0],
            fr'jar:file:{pathname2url(os.path.normcase(testfile1))}!/index.html')
        self.assertEqual(mock_browser.mock_calls[2][1][0],
            fr'jar:file:{pathname2url(os.path.normcase(testfile2))}!/123456/index.html')
        self.assertEqual(mock_browser.mock_calls[3][1][0],
            fr'jar:file:{pathname2url(os.path.normcase(testfile3))}!/abc/index.html')
        self.assertEqual(mock_browser.mock_calls[4][1][0],
            fr'jar:file:{pathname2url(os.path.normcase(testfile3))}!/def/index.html')
        self.assertEqual(len(os.listdir(testtemp)), 0)

        # test simple view
        mock_browser.reset_mock()
        with mock.patch('webscrapbook.cli.config', {
                'browser': {
                    'command': '',
                    'cache_prefix': 'webscrapbook.',
                    'cache_expire': 1000,
                    'use_jar': False,
                    }
                }):
            cli.view_archive_files([testfile1, testfile2, testfile3, testfile4])

        mock_browser.assert_called_once_with(None)
        self.assertEqual(len(mock_browser.mock_calls), 5)
        self.assertRegex(mock_browser.mock_calls[1][1][0],
            fr'^file:{re.escape(pathname2url(testtemp))}/webscrapbook\.[0-9a-z]*_[0-9a-z_]*/index\.html$')
        self.assertRegex(mock_browser.mock_calls[2][1][0],
            fr'^file:{re.escape(pathname2url(testtemp))}/webscrapbook\.[0-9a-z]*_[0-9a-z_]*/123456/index\.html$')
        self.assertRegex(mock_browser.mock_calls[3][1][0],
            fr'^file:{re.escape(pathname2url(testtemp))}/webscrapbook\.[0-9a-z]*_[0-9a-z_]*/abc/index\.html$')
        self.assertRegex(mock_browser.mock_calls[4][1][0],
            fr'^file:{re.escape(pathname2url(testtemp))}/webscrapbook\.[0-9a-z]*_[0-9a-z_]*/def/index\.html$')
        self.assertEqual(len(os.listdir(testtemp)), 3)

        # test browser command
        # test if cache is used for same archive
        mock_browser.reset_mock()
        with mock.patch('webscrapbook.cli.config', {
                'browser': {
                    'command': '/path/to/firefox',
                    'cache_prefix': 'webscrapbook.',
                    'cache_expire': 1000,
                    'use_jar': False,
                    }
                }):
            cli.view_archive_files([testfile1, testfile2, testfile3, testfile4])

        mock_browser.assert_called_once_with('/path/to/firefox')
        self.assertEqual(len(mock_browser.mock_calls), 5)
        self.assertRegex(mock_browser.mock_calls[1][1][0],
            fr'^file:{re.escape(pathname2url(testtemp))}/webscrapbook\.[0-9a-z]*_[0-9a-z_]*/index\.html$')
        self.assertRegex(mock_browser.mock_calls[2][1][0],
            fr'^file:{re.escape(pathname2url(testtemp))}/webscrapbook\.[0-9a-z]*_[0-9a-z_]*/123456/index\.html$')
        self.assertRegex(mock_browser.mock_calls[3][1][0],
            fr'^file:{re.escape(pathname2url(testtemp))}/webscrapbook\.[0-9a-z]*_[0-9a-z_]*/abc/index\.html$')
        self.assertRegex(mock_browser.mock_calls[4][1][0],
            fr'^file:{re.escape(pathname2url(testtemp))}/webscrapbook\.[0-9a-z]*_[0-9a-z_]*/def/index\.html$')
        self.assertEqual(len(os.listdir(testtemp)), 3)

        # test auto clearance of stale caches
        mock_browser.reset_mock()
        with mock.patch('webscrapbook.cli.config', {
                'browser': {
                    'command': '',
                    'cache_prefix': 'webscrapbook.',
                    'cache_expire': -1,
                    'use_jar': False,
                    }
                }):
            with mock.patch('shutil.rmtree') as mock_rmtree:
                cli.view_archive_files([])
                self.assertEqual(len(mock_rmtree.call_args_list), 3)
                self.assertRegex(mock_rmtree.call_args_list[0][0][0].path,
                    fr'^{re.escape(testtempprefix)}[0-9a-z]*_[0-9a-z_]*$')
                self.assertRegex(mock_rmtree.call_args_list[1][0][0].path,
                    fr'^{re.escape(testtempprefix)}[0-9a-z]*_[0-9a-z_]*$')
                self.assertRegex(mock_rmtree.call_args_list[2][0][0].path,
                    fr'^{re.escape(testtempprefix)}[0-9a-z]*_[0-9a-z_]*$')

if __name__ == '__main__':
    unittest.main()
