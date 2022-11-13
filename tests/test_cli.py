import io
import os
import re
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
from urllib.request import pathname2url

from webscrapbook import WSB_DIR, cli

from . import ROOT_DIR, TEMP_DIR

RESOURCE_DIR = os.path.join(ROOT_DIR, '..', 'webscrapbook', 'resources')


def setUpModule():
    """Set up a temp directory for testing."""
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='cli-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)


def tearDownModule():
    """Cleanup the temp directory."""
    _tmpdir.cleanup()


class Test(unittest.TestCase):
    def setUp(self):
        """Set up a temp directory for testing."""
        self.root = tempfile.mkdtemp(dir=tmpdir)


class TestServe(Test):
    @mock.patch('sys.stdout', io.StringIO)
    @mock.patch('webscrapbook.cli.server.serve', autospec=True)
    def test_call(self, mock_serve):
        cli.cmd_serve({
            'root': self.root,
            'browse': False,
        })

        mock_serve.assert_called_once_with(root=self.root, browse=False)


class TestConfig(Test):
    def setUp(self):
        super().setUp()
        self.user_config_file = os.path.join(self.root, WSB_DIR, 'userconfig.ini')
        self.mock_user_config = mock.patch('webscrapbook.cli.WSB_USER_CONFIG', self.user_config_file)
        self.mock_user_config.start()

    def tearDown(self):
        self.mock_user_config.stop()

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_book_create(self, mock_stdout):
        cli.cmd_config({
            'root': self.root,
            'book': True,
            'user': False,
            'all': False,
            'edit': False,
            'name': None,
        })

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_book_create2(self, mock_stdout):
        """No overwrite."""
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(os.path.join(self.root, WSB_DIR, 'config.ini'), 'w') as fh:
            fh.write('dummy')

        cli.cmd_config({
            'root': self.root,
            'book': True,
            'user': False,
            'all': False,
            'edit': False,
            'name': None,
        })

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'dummy')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.launch', autospec=True)
    def test_book_edit(self, mock_launch, mock_stdout):
        cli.cmd_config({
            'root': self.root,
            'book': True,
            'user': False,
            'all': False,
            'edit': True,
            'name': None,
        })

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        mock_launch.assert_called_once_with(os.path.join(self.root, WSB_DIR, 'config.ini'))

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.launch', autospec=True)
    def test_book_edit2(self, mock_launch, mock_stdout):
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(os.path.join(self.root, WSB_DIR, 'config.ini'), 'w') as fh:
            fh.write('foo')

        cli.cmd_config({
            'root': self.root,
            'book': True,
            'user': False,
            'all': False,
            'edit': True,
            'name': None,
        })

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'foo')

        mock_launch.assert_called_once_with(os.path.join(self.root, WSB_DIR, 'config.ini'))

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_book_all(self, mock_stdout):
        cli.cmd_config({
            'root': self.root,
            'book': True,
            'user': False,
            'all': True,
            'edit': False,
            'name': None,
        })

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        with open(os.path.join(self.root, WSB_DIR, 'serve.py')) as f1,\
             open(os.path.join(RESOURCE_DIR, 'serve.py')) as f2:
            self.assertTrue(f1.read(), f2.read())

        with open(os.path.join(self.root, WSB_DIR, 'app.py')) as f1,\
             open(os.path.join(RESOURCE_DIR, 'app.py')) as f2:
            self.assertTrue(f1.read(), f2.read())

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_book_all2(self, mock_stdout):
        """No overwrite."""
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(os.path.join(self.root, WSB_DIR, 'config.ini'), 'w') as fh:
            fh.write('dummy1')
        with open(os.path.join(self.root, WSB_DIR, 'serve.py'), 'w') as fh:
            fh.write('dummy2')
        with open(os.path.join(self.root, WSB_DIR, 'app.py'), 'w') as fh:
            fh.write('dummy3')

        cli.cmd_config({
            'root': self.root,
            'book': True,
            'user': False,
            'all': True,
            'edit': False,
            'name': None,
        })

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'dummy1')

        with open(os.path.join(self.root, WSB_DIR, 'serve.py')) as f1:
            self.assertTrue(f1.read(), 'dummy2')

        with open(os.path.join(self.root, WSB_DIR, 'app.py')) as f1:
            self.assertTrue(f1.read(), 'dummy3')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_user_create(self, mock_stdout):
        cli.cmd_config({
            'root': self.root,
            'book': False,
            'user': True,
            'all': False,
            'edit': False,
            'name': None,
        })

        with open(self.user_config_file) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_user_create2(self, mock_stdout):
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(self.user_config_file, 'w') as fh:
            fh.write('dummy')

        cli.cmd_config({
            'root': self.root,
            'book': False,
            'user': True,
            'all': False,
            'edit': False,
            'name': None,
        })

        with open(self.user_config_file) as f1:
            self.assertTrue(f1.read(), 'dummy')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.launch', autospec=True)
    def test_user_edit(self, mock_launch, mock_stdout):
        cli.cmd_config({
            'root': self.root,
            'book': False,
            'user': True,
            'all': False,
            'edit': True,
            'name': None,
        })

        with open(self.user_config_file) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        mock_launch.assert_called_once_with(self.user_config_file)

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.launch', autospec=True)
    def test_user_edit2(self, mock_launch, mock_stdout):
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(self.user_config_file, 'w') as fh:
            fh.write('dummy')

        cli.cmd_config({
            'root': self.root,
            'book': False,
            'user': True,
            'all': False,
            'edit': True,
            'name': None,
        })

        mock_launch.assert_called_once_with(self.user_config_file)

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('webscrapbook.cli.die', side_effect=SystemExit)
    def test_edit(self, mock_die):
        with self.assertRaises(SystemExit):
            cli.cmd_config({
                'root': self.root,
                'book': False,
                'user': False,
                'all': False,
                'edit': True,
                'name': None,
            })

        mock_die.assert_called_once_with('Use --edit in combine with --book or --user.')

    @mock.patch('webscrapbook.cli.die', side_effect=SystemExit)
    def test_all(self, mock_die):
        with self.assertRaises(SystemExit):
            cli.cmd_config({
                'root': self.root,
                'book': False,
                'user': False,
                'all': True,
                'edit': False,
                'name': None,
            })

        mock_die.assert_called_once_with('Use --all in combine with --book.')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.config.getname', return_value='dummy', autospec=True)
    def test_name_call(self, mock_getname, mock_stdout):
        cli.cmd_config({
            'root': self.root,
            'book': False,
            'user': False,
            'all': False,
            'edit': False,
            'name': 'app.name',
        })

        mock_getname.assert_called_once_with('app.name')
        self.assertEqual(mock_stdout.getvalue(), 'dummy\n')

    @mock.patch('webscrapbook.cli.die', side_effect=SystemExit)
    @mock.patch('webscrapbook.config.getname', return_value=None, autospec=True)
    def test_name_call2(self, mock_getname, mock_die):
        with self.assertRaises(SystemExit):
            cli.cmd_config({
                'root': self.root,
                'book': False,
                'user': False,
                'all': False,
                'edit': False,
                'name': 'unknown.config',
            })

        mock_getname.assert_called_once_with('unknown.config')
        mock_die.assert_called_once_with('Config entry "unknown.config" does not exist')

    @mock.patch('webscrapbook.config.dump', autospec=True)
    def test_dump(self, mock_dump):
        cli.cmd_config({
            'root': self.root,
            'book': False,
            'user': False,
            'all': False,
            'edit': False,
            'name': None,
        })

        mock_dump.assert_called_once_with(sys.stdout)


class TestEncrypt(Test):
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.encrypt', return_value='dummy_hash', autospec=True)
    def test_call(self, mock_encrypt, mock_stdout):
        cli.cmd_encrypt({
            'password': '1234',
            'salt': 'mysalt',
            'method': 'sha256',
        })

        mock_encrypt.assert_called_once_with('1234', salt='mysalt', method='sha256')
        self.assertEqual(mock_stdout.getvalue(), 'dummy_hash\n')


class TestCache(Test):
    @mock.patch('webscrapbook.scrapbook.cache.generate', autospec=True)
    def test_call(self, mock_func):
        cli.cmd_cache({
            'root': self.root,
            'book_ids': ['book1', 'book2'],
            'item_ids': ['item1', 'item2'],
            'fulltext': False,
            'inclusive_frames': False,
            'static_site': True,
            'static_index': True,
            'rss_root': 'http://example.com:8000/wsb/',
            'locale': 'zh_TW',
            'no_backup': True,
            'debug': True,
        })

        mock_func.assert_called_once_with(
            root=self.root,
            book_ids=['book1', 'book2'],
            item_ids=['item1', 'item2'],
            fulltext=False,
            inclusive_frames=False,
            static_site=True,
            static_index=True,
            rss_root='http://example.com:8000/wsb/',
            locale='zh_TW',
            no_backup=True,
        )


class TestCheck(Test):
    @mock.patch('webscrapbook.scrapbook.check.run', autospec=True)
    def test_call(self, mock_func):
        cli.cmd_check({
            'root': self.root,
            'book_ids': ['book1', 'book2'],
            'resolve_all': False,
            'resolve_invalid_id': True,
            'resolve_missing_index': True,
            'resolve_missing_index_file': True,
            'resolve_missing_date': True,
            'resolve_older_mtime': True,
            'resolve_toc_unreachable': True,
            'resolve_toc_invalid': True,
            'resolve_toc_empty_subtree': True,
            'resolve_unindexed_files': True,
            'resolve_absolute_icon': True,
            'resolve_unused_icon': True,
            'no_backup': True,
            'debug': True,
        })

        mock_func.assert_called_once_with(
            root=self.root,
            book_ids=['book1', 'book2'],
            resolve_all=False,
            resolve_invalid_id=True,
            resolve_missing_index=True,
            resolve_missing_index_file=True,
            resolve_missing_date=True,
            resolve_older_mtime=True,
            resolve_toc_unreachable=True,
            resolve_toc_invalid=True,
            resolve_toc_empty_subtree=True,
            resolve_unindexed_files=True,
            resolve_absolute_icon=True,
            resolve_unused_icon=True,
            no_backup=True,
        )


class TestExport(Test):
    @mock.patch('webscrapbook.scrapbook.exporter.run', autospec=True)
    def test_call(self, mock_func):
        cli.cmd_export({
            'root': self.root,
            'output': os.path.join(self.root, 'export'),
            'book_id': 'id1',
            'item_ids': ['item1', 'item2'],
            'recursive': True,
            'singleton': True,
            'debug': True,
        })

        mock_func.assert_called_once_with(
            root=self.root,
            output=os.path.join(self.root, 'export'),
            book_id='id1',
            item_ids=['item1', 'item2'],
            recursive=True,
            singleton=True,
        )


class TestImport(Test):
    @mock.patch('webscrapbook.scrapbook.importer.run', autospec=True)
    def test_call(self, mock_func):
        cli.cmd_import({
            'root': self.root,
            'files': [os.path.join(self.root, 'import')],
            'book': 'id1',
            'target_id': '20200101000000000',
            'target_index': 1,
            'target_filename': '%UUID%',
            'rebuild_folders': True,
            'resolve_id_used': 'new',
            'prune': True,
            'debug': True,
        })

        mock_func.assert_called_once_with(
            root=self.root,
            files=[os.path.join(self.root, 'import')],
            book='id1',
            target_id='20200101000000000',
            target_index=1,
            target_filename='%UUID%',
            rebuild_folders=True,
            resolve_id_used='new',
            prune=True,
        )


class TestConvert(Test):
    def setUp(self):
        """Set up temp directories for testing."""
        self.input = tempfile.mkdtemp(dir=tmpdir)
        self.output = tempfile.mkdtemp(dir=tmpdir)

    @mock.patch('webscrapbook.scrapbook.convert.sb2wsb.run', autospec=True)
    def test_sb2wsb(self, mock_func):
        cli.cmd_convert({
            'root': self.input,
            'mode': 'sb2wsb',
            'input': self.input,
            'output': self.output,
            'no_backup': True,
            'force': True,
            'debug': True,
        })

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            no_backup=True,
        )

    @mock.patch('webscrapbook.scrapbook.convert.wsb2sb.run', autospec=True)
    def test_wsb2sb(self, mock_func):
        cli.cmd_convert({
            'root': self.input,
            'mode': 'wsb2sb',
            'input': self.input,
            'output': self.output,
            'book_id': 'id1',
            'force': True,
            'debug': True,
        })

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            book_id='id1',
        )


class TestHelp(Test):
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_call(self, mock_stdout):
        cli.cmd_help({
            'topic': 'config',
        })

        with open(os.path.join(RESOURCE_DIR, 'config.md')) as fh:
            self.assertEqual(mock_stdout.getvalue(), fh.read() + '\n')


class TestView(Test):
    @mock.patch('webscrapbook.cli.view_archive_files', autospec=True)
    def test_call(self, mock_view):
        cli.cmd_view({
            'root': 'config',
            'files': [self.root],
        })

        mock_view.assert_called_once_with([self.root])


class TestHelpers(Test):
    @mock.patch('webbrowser.get', new_callable=mock.MagicMock())
    def test_view_archive_files(self, mock_browser):
        testfile1 = os.path.join(self.root, 'test1.htz')
        testfile2 = os.path.join(self.root, 'test2.maff')
        testfile3 = os.path.join(self.root, 'test3.maff')
        testfile4 = os.path.join(self.root, 'test4.zip')
        testtemp = os.path.join(self.root, 'tempdir')
        testtempprefix = os.path.join(self.root, 'tempdir', 'webscrapbook.')

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

        with mock.patch('tempfile.gettempdir', lambda: testtemp):
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
