import io
import os
import re
import sys
import tempfile
import unittest
from unittest import mock
from urllib.request import pathname2url

from webscrapbook import WSB_DIR, cli
from webscrapbook._polyfill import zipfile

from . import PROG_DIR, TEMP_DIR

RESOURCE_DIR = os.path.join(PROG_DIR, 'resources')


def setUpModule():
    # set up a temp directory for testing
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
    @mock.patch('webscrapbook.server.serve', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_serve', wraps=cli.cmd_serve)
    def test_default(self, mock_handler, mock_func):
        cli.main([
            '--root', self.root,
            'serve',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            browse=None,
        ))

        mock_func.assert_called_once_with(
            root=self.root,
            browse=None,
        )

    @mock.patch('webscrapbook.server.serve', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_serve', wraps=cli.cmd_serve)
    def test_basic(self, mock_handler, mock_func):
        cli.main([
            '--root', self.root,
            'serve',
            '--no-browse',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            browse=False,
        ))

        mock_func.assert_called_once_with(
            root=self.root,
            browse=False,
        )


class TestConfig(Test):
    def setUp(self):
        super().setUp()
        self.user_config_file = os.path.join(self.root, WSB_DIR, 'userconfig.ini')
        self.mock_user_config = mock.patch('webscrapbook.cli.WSB_USER_CONFIG', self.user_config_file)
        self.mock_user_config.start()

    def tearDown(self):
        self.mock_user_config.stop()

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_book_create(self, mock_handler, mock_stdout):
        cli.main([
            '--root', self.root,
            'config',
            '--book',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=True,
            user=False,
            all=False,
            edit=False,
            name=None,
        ))

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_book_create2(self, mock_handler, mock_stdout):
        """No overwrite."""
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(os.path.join(self.root, WSB_DIR, 'config.ini'), 'w') as fh:
            fh.write('dummy')

        cli.main([
            '--root', self.root,
            'config',
            '--book',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=True,
            user=False,
            all=False,
            edit=False,
            name=None,
        ))

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'dummy')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.fs.launch', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_book_edit(self, mock_handler, mock_launch, mock_stdout):
        cli.main([
            '--root', self.root,
            'config',
            '--book',
            '--edit',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=True,
            user=False,
            all=False,
            edit=True,
            name=None,
        ))

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        mock_launch.assert_called_once_with(os.path.join(self.root, WSB_DIR, 'config.ini'))

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.fs.launch', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_book_edit2(self, mock_handler, mock_launch, mock_stdout):
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(os.path.join(self.root, WSB_DIR, 'config.ini'), 'w') as fh:
            fh.write('foo')

        cli.main([
            '--root', self.root,
            'config',
            '--book',
            '--edit',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=True,
            user=False,
            all=False,
            edit=True,
            name=None,
        ))

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'foo')

        mock_launch.assert_called_once_with(os.path.join(self.root, WSB_DIR, 'config.ini'))

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_book_all(self, mock_handler, mock_stdout):
        cli.main([
            '--root', self.root,
            'config',
            '--book',
            '--all',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=True,
            user=False,
            all=True,
            edit=False,
            name=None,
        ))

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
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_book_all2(self, mock_handler, mock_stdout):
        """No overwrite."""
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(os.path.join(self.root, WSB_DIR, 'config.ini'), 'w') as fh:
            fh.write('dummy1')
        with open(os.path.join(self.root, WSB_DIR, 'serve.py'), 'w') as fh:
            fh.write('dummy2')
        with open(os.path.join(self.root, WSB_DIR, 'app.py'), 'w') as fh:
            fh.write('dummy3')

        cli.main([
            '--root', self.root,
            'config',
            '--book',
            '--all',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=True,
            user=False,
            all=True,
            edit=False,
            name=None,
        ))

        with open(os.path.join(self.root, WSB_DIR, 'config.ini')) as f1:
            self.assertTrue(f1.read(), 'dummy1')

        with open(os.path.join(self.root, WSB_DIR, 'serve.py')) as f1:
            self.assertTrue(f1.read(), 'dummy2')

        with open(os.path.join(self.root, WSB_DIR, 'app.py')) as f1:
            self.assertTrue(f1.read(), 'dummy3')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_user_create(self, mock_handler, mock_stdout):
        cli.main([
            '--root', self.root,
            'config',
            '--user',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=True,
            all=False,
            edit=False,
            name=None,
        ))

        with open(self.user_config_file) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_user_create2(self, mock_handler, mock_stdout):
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(self.user_config_file, 'w') as fh:
            fh.write('dummy')

        cli.main([
            '--root', self.root,
            'config',
            '--user',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=True,
            all=False,
            edit=False,
            name=None,
        ))

        with open(self.user_config_file) as f1:
            self.assertTrue(f1.read(), 'dummy')

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.fs.launch', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_user_edit(self, mock_handler, mock_launch, mock_stdout):
        cli.main([
            '--root', self.root,
            'config',
            '--user',
            '--edit',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=True,
            all=False,
            edit=True,
            name=None,
        ))

        with open(self.user_config_file) as f1,\
             open(os.path.join(RESOURCE_DIR, 'config.ini')) as f2:
            self.assertTrue(f1.read(), f2.read())

        mock_launch.assert_called_once_with(self.user_config_file)

        self.assertNotEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.fs.launch', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_user_edit2(self, mock_handler, mock_launch, mock_stdout):
        os.makedirs(os.path.join(self.root, WSB_DIR), exist_ok=True)
        with open(self.user_config_file, 'w') as fh:
            fh.write('dummy')

        cli.main([
            '--root', self.root,
            'config',
            '--user',
            '--edit',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=True,
            all=False,
            edit=True,
            name=None,
        ))

        mock_launch.assert_called_once_with(self.user_config_file)

        self.assertEqual(mock_stdout.getvalue(), '')

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_edit(self, mock_handler, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            cli.main([
                '--root', self.root,
                'config',
                '--edit',
            ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=False,
            all=False,
            edit=True,
            name=None,
        ))

        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(mock_stderr.getvalue(), 'Error: Use --edit in combine with --book or --user.\n')

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_all(self, mock_handler, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            cli.main([
                '--root', self.root,
                'config',
                '--all',
            ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=False,
            all=True,
            edit=False,
            name=None,
        ))

        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(mock_stderr.getvalue(), 'Error: Use --all in combine with --book.\n')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.config.getname', return_value='dummy', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_name_call(self, mock_handler, mock_getname, mock_stdout):
        cli.main([
            '--root', self.root,
            'config',
            'app.name',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=False,
            all=False,
            edit=False,
            name='app.name',
        ))

        mock_getname.assert_called_once_with('app.name')
        self.assertEqual(mock_stdout.getvalue(), 'dummy\n')

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('webscrapbook.config.getname', return_value=None, autospec=True)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_name_call2(self, mock_handler, mock_getname, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            cli.main([
                '--root', self.root,
                'config',
                'unknown.config',
            ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=False,
            all=False,
            edit=False,
            name='unknown.config',
        ))

        mock_getname.assert_called_once_with('unknown.config')
        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(mock_stderr.getvalue(), 'Error: Config entry "unknown.config" does not exist\n')

    @mock.patch('webscrapbook.config.dump', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_config', wraps=cli.cmd_config)
    def test_dump(self, mock_handler, mock_dump):
        cli.main([
            '--root', self.root,
            'config',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book=False,
            user=False,
            all=False,
            edit=False,
            name=None,
        ))

        mock_dump.assert_called_once_with(sys.stdout)


class TestEncrypt(Test):
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.encrypt', return_value='dummy_hash', autospec=True)
    @mock.patch('webscrapbook.cli.getpass', return_value='1234', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_encrypt', wraps=cli.cmd_encrypt)
    def test_default(self, mock_handler, mock_getpass, mock_encrypt, mock_stdout):
        cli.main([
            '--root', self.root,
            'encrypt',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            password=None,
            salt='',
            method='sha1',
        ))

        mock_encrypt.assert_called_once_with('1234', salt='', method='sha1')
        self.assertEqual(mock_stdout.getvalue(), 'dummy_hash\n')

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    @mock.patch('webscrapbook.util.encrypt', return_value='dummy_hash', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_encrypt', wraps=cli.cmd_encrypt)
    def test_basic(self, mock_handler, mock_encrypt, mock_stdout):
        cli.main([
            '--root', self.root,
            'encrypt',
            '--password', '1234',
            '--salt', 'mysalt',
            '--method', 'sha256',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            password='1234',
            salt='mysalt',
            method='sha256',
        ))

        mock_encrypt.assert_called_once_with('1234', salt='mysalt', method='sha256')
        self.assertEqual(mock_stdout.getvalue(), 'dummy_hash\n')


class TestCache(Test):
    @mock.patch('webscrapbook.scrapbook.cache.generate', autospec=True, return_value=iter(()))
    @mock.patch('webscrapbook.cli.cmd_cache', wraps=cli.cmd_cache)
    def test_default(self, mock_handler, mock_func):
        cli.main([
            '--root', self.root,
            'cache',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book_ids=[],
            item_ids=None,
            fulltext=True,
            inclusive_frames=True,
            recreate=False,
            static_site=False,
            static_index=False,
            rss_root=None,
            rss_item_count=50,
            locale=None,
            backup=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            self.root,
            book_ids=[],
            item_ids=None,
            fulltext=True,
            inclusive_frames=True,
            recreate=False,
            static_site=False,
            static_index=False,
            rss_root=None,
            rss_item_count=50,
            locale=None,
            backup=False,
        )

    @mock.patch('webscrapbook.scrapbook.cache.generate', autospec=True, return_value=iter(()))
    @mock.patch('webscrapbook.cli.cmd_cache', wraps=cli.cmd_cache)
    def test_basic(self, mock_handler, mock_func):
        cli.main([
            '--root', self.root,
            'cache',
            'book1', 'book2',
            '--item', 'item1', 'item2',
            '--no-fulltext',
            '--no-inclusive-frames',
            '--recreate',
            '--static-site',
            '--static-index',
            '--rss-root', 'http://example.com:8000/wsb/',
            '--rss-item-count', '20',
            '--locale', 'zh_TW',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book_ids=['book1', 'book2'],
            item_ids=['item1', 'item2'],
            fulltext=False,
            inclusive_frames=False,
            recreate=True,
            static_site=True,
            static_index=True,
            rss_root='http://example.com:8000/wsb/',
            rss_item_count=20,
            locale='zh_TW',
            backup=False,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            self.root,
            book_ids=['book1', 'book2'],
            item_ids=['item1', 'item2'],
            fulltext=False,
            inclusive_frames=False,
            recreate=True,
            static_site=True,
            static_index=True,
            rss_root='http://example.com:8000/wsb/',
            rss_item_count=20,
            locale='zh_TW',
            backup=False,
        )


class TestCheck(Test):
    @mock.patch('webscrapbook.scrapbook.check.run', autospec=True, return_value=iter(()))
    @mock.patch('webscrapbook.cli.cmd_check', wraps=cli.cmd_check)
    def test_default(self, mock_handler, mock_func):
        cli.main([
            '--root', self.root,
            'check',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book_ids=[],
            resolve_all=False,
            resolve_invalid_id=False,
            resolve_missing_index=False,
            resolve_missing_index_file=False,
            resolve_missing_date=False,
            resolve_older_mtime=False,
            resolve_toc_unreachable=False,
            resolve_toc_invalid=False,
            resolve_toc_empty_subtree=False,
            resolve_unindexed_files=False,
            resolve_absolute_icon=False,
            resolve_unused_icon=False,
            backup=True,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            self.root,
            book_ids=[],
            resolve_all=False,
            resolve_invalid_id=False,
            resolve_missing_index=False,
            resolve_missing_index_file=False,
            resolve_missing_date=False,
            resolve_older_mtime=False,
            resolve_toc_unreachable=False,
            resolve_toc_invalid=False,
            resolve_toc_empty_subtree=False,
            resolve_unindexed_files=False,
            resolve_absolute_icon=False,
            resolve_unused_icon=False,
            backup=True,
        )

    @mock.patch('webscrapbook.scrapbook.check.run', autospec=True, return_value=iter(()))
    @mock.patch('webscrapbook.cli.cmd_check', wraps=cli.cmd_check)
    def test_basic(self, mock_handler, mock_func):
        cli.main([
            '--root', self.root,
            'check',
            'book1', 'book2',
            '--resolve-invalid-id',
            '--resolve-missing-index',
            '--resolve-missing-index-file',
            '--resolve-missing-date',
            '--resolve-older-mtime',
            '--resolve-toc-unreachable',
            '--resolve-toc-invalid',
            '--resolve-toc-empty-subtree',
            '--resolve-unindexed-files',
            '--resolve-absolute-icon',
            '--resolve-unused-icon',
            '--no-backup',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
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
            backup=False,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            self.root,
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
            backup=False,
        )

    @mock.patch('webscrapbook.scrapbook.check.run', autospec=True, return_value=iter(()))
    @mock.patch('webscrapbook.cli.cmd_check', wraps=cli.cmd_check)
    def test_basic_resolve_all(self, mock_handler, mock_func):
        cli.main([
            '--root', self.root,
            'check',
            'book1', 'book2',
            '--resolve',
            '--no-backup',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            book_ids=['book1', 'book2'],
            resolve_all=True,
            resolve_invalid_id=False,
            resolve_missing_index=False,
            resolve_missing_index_file=False,
            resolve_missing_date=False,
            resolve_older_mtime=False,
            resolve_toc_unreachable=False,
            resolve_toc_invalid=False,
            resolve_toc_empty_subtree=False,
            resolve_unindexed_files=False,
            resolve_absolute_icon=False,
            resolve_unused_icon=False,
            backup=False,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            self.root,
            book_ids=['book1', 'book2'],
            resolve_all=True,
            resolve_invalid_id=False,
            resolve_missing_index=False,
            resolve_missing_index_file=False,
            resolve_missing_date=False,
            resolve_older_mtime=False,
            resolve_toc_unreachable=False,
            resolve_toc_invalid=False,
            resolve_toc_empty_subtree=False,
            resolve_unindexed_files=False,
            resolve_absolute_icon=False,
            resolve_unused_icon=False,
            backup=False,
        )


class TestExport(Test):
    @mock.patch('webscrapbook.scrapbook.exporter.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_export', wraps=cli.cmd_export)
    def test_default(self, mock_handler, mock_func):
        output_dir = os.path.join(self.root, 'export')
        cli.main([
            '--root', self.root,
            'export',
            output_dir,
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            output=output_dir,
            book_id='',
            item_ids=None,
            recursive=False,
            singleton=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            self.root,
            output=output_dir,
            book_id='',
            item_ids=None,
            recursive=False,
            singleton=False,
        )

    @mock.patch('webscrapbook.scrapbook.exporter.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_export', wraps=cli.cmd_export)
    def test_basic(self, mock_handler, mock_func):
        output_dir = os.path.join(self.root, 'export')
        cli.main([
            '--root', self.root,
            'export',
            output_dir,
            '--book', 'book1',
            '--item', 'item1', 'item2',
            '--recursive',
            '--singleton',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            output=output_dir,
            book_id='book1',
            item_ids=['item1', 'item2'],
            recursive=True,
            singleton=True,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            self.root,
            output=output_dir,
            book_id='book1',
            item_ids=['item1', 'item2'],
            recursive=True,
            singleton=True,
        )


class TestImport(Test):
    @mock.patch('webscrapbook.scrapbook.importer.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_import', wraps=cli.cmd_import)
    def test_default(self, mock_handler, mock_func):
        file1 = os.path.join(self.root, 'import', 'file1.warc')
        cli.main([
            '--root', self.root,
            'import',
            file1,
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            files=[file1],
            book_id='',
            target_id='root',
            target_index=None,
            target_filename='%ID%',
            rebuild_folders=False,
            resolve_id_used='skip',
            prune=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            self.root,
            files=[file1],
            book_id='',
            target_id='root',
            target_index=None,
            target_filename='%ID%',
            rebuild_folders=False,
            resolve_id_used='skip',
            prune=False,
        )

    @mock.patch('webscrapbook.scrapbook.importer.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_import', wraps=cli.cmd_import)
    def test_basic(self, mock_handler, mock_func):
        file1 = os.path.join(self.root, 'import', 'file1.warc')
        file2 = os.path.join(self.root, 'import', 'file2.warc')
        cli.main([
            '--root', self.root,
            'import',
            file1, file2,
            '--book', 'book1',
            '--target', '20200101000000000',
            '--target-index', '1',
            '--filename', '%UUID%',
            '--rebuild-folders',
            '--resolve-id-used', 'new',
            '--prune',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            files=[file1, file2],
            book_id='book1',
            target_id='20200101000000000',
            target_index=1,
            target_filename='%UUID%',
            rebuild_folders=True,
            resolve_id_used='new',
            prune=True,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            self.root,
            files=[file1, file2],
            book_id='book1',
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
        super().setUp()
        self.input = os.path.join(self.root, 'input')
        self.output = os.path.join(self.root, 'output')
        os.makedirs(self.input)

    @mock.patch('webscrapbook.scrapbook.convert.migrate.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_migrate_default(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'migrate',
            self.input,
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='migrate',
            input=self.input,
            output=None,
            book_ids=None,
            convert_legacy=True,
            convert_v1=True,
            use_native_tags=False,
            force=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=None,
            book_ids=None,
            convert_legacy=True,
            convert_v1=True,
            use_native_tags=False,
        )

    @mock.patch('webscrapbook.scrapbook.convert.migrate.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_migrate_basic(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'migrate',
            self.input,
            self.output,
            '--book', 'book1', 'book2',
            '--no-convert-legacy',
            '--no-convert-v1',
            '--use-native-tags',
            '--force',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='migrate',
            input=self.input,
            output=self.output,
            book_ids=['book1', 'book2'],
            convert_legacy=False,
            convert_v1=False,
            use_native_tags=True,
            force=True,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            book_ids=['book1', 'book2'],
            convert_legacy=False,
            convert_v1=False,
            use_native_tags=True,
        )

    @mock.patch('webscrapbook.scrapbook.convert.items.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_items_default(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'items',
            self.input,
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='items',
            input=self.input,
            output=None,
            book_ids=None,
            item_ids=None,
            format=None,
            types=[''],
            force=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=None,
            book_ids=None,
            item_ids=None,
            format=None,
            types=[''],
        )

    @mock.patch('webscrapbook.scrapbook.convert.items.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_items_basic(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'items',
            self.input,
            self.output,
            '--book', 'book1', 'book2',
            '--item', 'item1', 'item2',
            '--format', 'htz',
            '--type', '', 'site', 'image', 'file', 'combine',
            'note', 'postit', 'bookmark', 'folder', 'separator',
            '--force',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='items',
            input=self.input,
            output=self.output,
            book_ids=['book1', 'book2'],
            item_ids=['item1', 'item2'],
            format='htz',
            types=['', 'site', 'image', 'file', 'combine',
                   'note', 'postit', 'bookmark', 'folder', 'separator'],
            force=True,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            book_ids=['book1', 'book2'],
            item_ids=['item1', 'item2'],
            format='htz',
            types=['', 'site', 'image', 'file', 'combine',
                   'note', 'postit', 'bookmark', 'folder', 'separator'],
        )

    @mock.patch('webscrapbook.scrapbook.convert.sb2wsb.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_sb2wsb_default(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'sb2wsb',
            self.input,
            self.output,
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='sb2wsb',
            input=self.input,
            output=self.output,
            data_files=True,
            backup=True,
            force=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            data_files=True,
            backup=True,
        )

    @mock.patch('webscrapbook.scrapbook.convert.sb2wsb.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_sb2wsb_basic(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'sb2wsb',
            self.input,
            self.output,
            '--no-data-files',
            '--no-backup',
            '--force',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='sb2wsb',
            input=self.input,
            output=self.output,
            data_files=False,
            backup=False,
            force=True,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            data_files=False,
            backup=False,
        )

    @mock.patch('webscrapbook.scrapbook.convert.wsb2sb.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_wsb2sb_default(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'wsb2sb',
            self.input,
            self.output,
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='wsb2sb',
            input=self.input,
            output=self.output,
            book_id='',
            data_files=True,
            force=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            book_id='',
            data_files=True,
        )

    @mock.patch('webscrapbook.scrapbook.convert.wsb2sb.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_wsb2sb_basic(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'wsb2sb',
            self.input,
            self.output,
            '--book', 'book1',
            '--no-data-files',
            '--force',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='wsb2sb',
            input=self.input,
            output=self.output,
            book_id='book1',
            data_files=False,
            force=True,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            book_id='book1',
            data_files=False,
        )

    @mock.patch('webscrapbook.scrapbook.convert.file2wsb.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_file2wsb_default(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'file2wsb',
            self.input,
            self.output,
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='file2wsb',
            input=self.input,
            output=self.output,
            data_folder_suffixes=None,
            preserve_filename=True,
            handle_ie_meta=True,
            handle_singlefile_meta=True,
            handle_savepagewe_meta=True,
            handle_maoxian_meta=True,
            force=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            data_folder_suffixes=None,
            preserve_filename=True,
            handle_ie_meta=True,
            handle_singlefile_meta=True,
            handle_savepagewe_meta=True,
            handle_maoxian_meta=True,
        )

    @mock.patch('webscrapbook.scrapbook.convert.file2wsb.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_file2wsb_basic(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'file2wsb',
            self.input,
            self.output,
            '--data-folder-suffix', '.files', '_files', '.data',
            '--no-preserve-filename',
            '--no-handle-ie-meta',
            '--no-handle-singlefile-meta',
            '--no-handle-savepagewe-meta',
            '--no-handle-maoxian-meta',
            '--force',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='file2wsb',
            input=self.input,
            output=self.output,
            data_folder_suffixes=['.files', '_files', '.data'],
            preserve_filename=False,
            handle_ie_meta=False,
            handle_singlefile_meta=False,
            handle_savepagewe_meta=False,
            handle_maoxian_meta=False,
            force=True,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            data_folder_suffixes=['.files', '_files', '.data'],
            preserve_filename=False,
            handle_ie_meta=False,
            handle_singlefile_meta=False,
            handle_savepagewe_meta=False,
            handle_maoxian_meta=False,
        )

    @mock.patch('webscrapbook.scrapbook.convert.wsb2file.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_wsb2file_default(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'wsb2file',
            self.input,
            self.output,
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='wsb2file',
            input=self.input,
            output=self.output,
            book_id='',
            prefix=True,
            force=False,
            debug=False,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            book_id='',
            prefix=True,
        )

    @mock.patch('webscrapbook.scrapbook.convert.wsb2file.run', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_convert', wraps=cli.cmd_convert)
    def test_wsb2file_basic(self, mock_handler, mock_func):
        cli.main([
            'convert',
            'wsb2file',
            self.input,
            self.output,
            '--book', 'book1',
            '--no-prefix',
            '--force',
            '--debug',
        ])

        mock_handler.assert_called_once_with(dict(
            root='.',
            mode='wsb2file',
            input=self.input,
            output=self.output,
            book_id='book1',
            prefix=False,
            force=True,
            debug=True,
        ))

        mock_func.assert_called_once_with(
            input=self.input,
            output=self.output,
            book_id='book1',
            prefix=False,
        )


class TestHelp(Test):
    def test_basic(self):
        topics = {
            'config': os.path.join(RESOURCE_DIR, 'config.md'),
            'themes': os.path.join(RESOURCE_DIR, 'themes.md'),
            'mimetypes': os.path.join(RESOURCE_DIR, 'mimetypes.md'),
        }

        for topic, file in topics.items():
            with self.subTest(topic=topic),\
                 mock.patch('webscrapbook.cli.cmd_help', wraps=cli.cmd_help) as mock_handler,\
                 mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                cli.main([
                    '--root', self.root,
                    'help',
                    topic,
                ])

                mock_handler.assert_called_once_with(dict(
                    root=self.root,
                    topic=topic,
                ))

                with open(file) as fh:
                    self.assertEqual(mock_stdout.getvalue(), fh.read() + '\n')


class TestView(Test):
    @mock.patch('webscrapbook.cli.view_archive_files', autospec=True)
    @mock.patch('webscrapbook.cli.cmd_view', wraps=cli.cmd_view)
    def test_basic(self, mock_handler, mock_view):
        file1 = os.path.join(self.root, 'archive.htz')
        file2 = os.path.join(self.root, 'archive.maff')
        cli.main([
            '--root', self.root,
            'view',
            file1, file2,
        ])

        mock_handler.assert_called_once_with(dict(
            root=self.root,
            files=[file1, file2],
        ))

        mock_view.assert_called_once_with([file1, file2])


class TestHelpers(Test):
    @mock.patch('webbrowser.get')
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
