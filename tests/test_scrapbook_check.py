import os
import tempfile
import unittest
from base64 import b64decode
from datetime import datetime, timezone
from unittest import mock

from webscrapbook import WSB_DIR, util
from webscrapbook._polyfill import zipfile
from webscrapbook.scrapbook import check as wsb_check

from . import TEMP_DIR, TestBookMixin


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='check-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)

    # mock out user config
    global mockings
    mockings = (
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.devnull),
        mock.patch('webscrapbook.WSB_USER_DIR', os.devnull),
        mock.patch('webscrapbook.WSB_USER_CONFIG', os.devnull),
    )
    for mocking in mockings:
        mocking.start()


def tearDownModule():
    # cleanup the temp directory
    _tmpdir.cleanup()

    # stop mock
    for mocking in mockings:
        mocking.stop()


class TestCheck(TestBookMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_tree = os.path.join(self.test_root, WSB_DIR, 'tree')
        os.makedirs(self.test_tree)


class TestFuncRun(TestCheck):
    @mock.patch('webscrapbook.scrapbook.check.Host')
    def test_param_root(self, mock_host):
        for _info in wsb_check.run(self.test_root):
            pass

        mock_host.assert_called_once_with(self.test_root, None)

    @mock.patch('webscrapbook.scrapbook.check.Host')
    def test_param_config(self, mock_host):
        for _info in wsb_check.run(self.test_root, config={}):
            pass

        mock_host.assert_called_once_with(self.test_root, {})

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_param_lock01(self, mock_func):
        for _info in wsb_check.run(self.test_root, lock=True):
            pass

        mock_func.assert_called_once_with()

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_param_lock02(self, mock_func):
        for _info in wsb_check.run(self.test_root, lock=False):
            pass

        mock_func.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.host.Book')
    def test_param_book_ids01(self, mock_book):
        """Include effective provided IDs"""
        self.init_host(self.test_root, config="""\
[book "id1"]

[book "id2"]

[book "id4"]

[book "id5"]
""")

        for _info in wsb_check.run(self.test_root, book_ids=['', 'id1', 'id2', 'id3', 'id4']):
            pass

        self.assertListEqual(mock_book.call_args_list, [
            mock.call(mock.ANY, ''),
            mock.call(mock.ANY, 'id1'),
            mock.call(mock.ANY, 'id2'),
            mock.call(mock.ANY, 'id4'),
        ])

    @mock.patch('webscrapbook.scrapbook.host.Book')
    def test_param_book_ids02(self, mock_book):
        """Include all available IDs if None provided"""
        self.init_host(self.test_root, config="""\
[book "id1"]

[book "id2"]

[book "id4"]

[book "id5"]
""")

        for _info in wsb_check.run(self.test_root):
            pass

        self.assertListEqual(mock_book.call_args_list, [
            mock.call(mock.ANY, ''),
            mock.call(mock.ANY, 'id1'),
            mock.call(mock.ANY, 'id2'),
            mock.call(mock.ANY, 'id4'),
            mock.call(mock.ANY, 'id5'),
        ])

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_no_tree(self, mock_lock):
        """Books with no_tree=True should be skipped."""
        self.init_host(self.test_root, config="""\
[book ""]
no_tree = true
""")

        for _info in wsb_check.run(self.test_root):
            pass

        mock_lock.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.host.Host.get_subpath', lambda *_: '')
    @mock.patch('webscrapbook.scrapbook.host.Host.init_auto_backup')
    def test_param_backup01(self, mock_func):
        for _info in wsb_check.run(self.test_root, backup=True):
            pass

        self.assertEqual(mock_func.call_args_list, [
            mock.call(note='check'),
            mock.call(False),
        ])

    @mock.patch('webscrapbook.scrapbook.host.Host.init_auto_backup')
    def test_param_backup02(self, mock_func):
        for _info in wsb_check.run(self.test_root, backup=False):
            pass

        mock_func.assert_not_called()


class TestBookChecker(TestCheck):
    def test_normal(self):
        """A simple normal check case. No error should raise."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        generator = wsb_check.BookChecker(book)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': 'favicon.ico'
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

    def test_resolve_invalid_id(self):
        """Resolve item with invalid ID"""
        book = self.init_book(
            self.test_root,
            meta={
                'root': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        generator = wsb_check.BookChecker(book, resolve_invalid_id=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {})
        self.assertDictEqual(book.toc, {'root': ['20200101000000000']})

    def test_resolve_missing_index(self):
        """Resolve item with missing index"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        generator = wsb_check.BookChecker(book, resolve_missing_index=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {})
        self.assertDictEqual(book.toc, {'root': ['20200101000000000']})

    def test_resolve_missing_index_file(self):
        """Resolve item with missing index file"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_missing_index_file=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {})
        self.assertDictEqual(book.toc, {'root': ['20200101000000000']})

    def test_resolve_missing_create01(self):
        """Resolve item with empty create (infer from ID)"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '',
                    'modify': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': 'favicon.ico'
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

    def test_resolve_missing_create02(self):
        """Resolve item with missing create (infer from ID)"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'modify': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': 'favicon.ico'
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

    def test_resolve_missing_create03(self):
        """Resolve item with empty create (infer from ctime)"""
        book = self.init_book(
            self.test_root,
            meta={
                'foobar': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '',
                    'modify': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    'foobar',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        ts = util.id_to_datetime(util.datetime_to_id()).timestamp()
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertAlmostEqual(util.id_to_datetime(book.meta['foobar']['create']).timestamp(), ts, delta=3)
        self.assertDictEqual({k: (v, v.pop('create'))[0] for k, v in book.meta.items()}, {
            'foobar': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle中文',
                'type': '',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': 'favicon.ico'
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                'foobar',
            ],
        })

    def test_resolve_missing_create04(self):
        """Resolve item with empty create (infer from modify)"""
        book = self.init_book(
            self.test_root,
            meta={
                'foobar': {
                    'title': 'MyTitle中文',
                    'type': 'folder',
                    'create': '',
                    'modify': '20200101000000000',
                },
            },
            toc={
                'root': [
                    'foobar',
                ],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'foobar': {
                'title': 'MyTitle中文',
                'type': 'folder',
                'create': '20200101000000000',
                'modify': '20200101000000000',
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                'foobar',
            ],
        })

    def test_resolve_missing_create05(self):
        """Resolve item with empty create (no change)"""
        book = self.init_book(
            self.test_root,
            meta={
                'foobar': {
                    'title': 'MyTitle中文',
                    'type': 'folder',
                    'create': '',
                },
            },
            toc={
                'root': [
                    'foobar',
                ],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'foobar': {
                'title': 'MyTitle中文',
                'type': 'folder',
                'create': '',
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                'foobar',
            ],
        })

    def test_resolve_missing_modify01(self):
        """Resolve item with empty modify (infer from mtime)"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'source': 'http://example.com',
                'icon': 'favicon.ico'
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

    def test_resolve_missing_modify02(self):
        """Resolve item with missing modify (infer from mtime)"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'source': 'http://example.com',
                'icon': 'favicon.ico'
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

    def test_resolve_missing_modify03(self):
        """Resolve item with empty modify (infer from create)"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'title': 'MyTitle中文',
                    'type': 'folder',
                    'create': '20200101000000000',
                    'modify': '',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'title': 'MyTitle中文',
                'type': 'folder',
                'create': '20200101000000000',
                'modify': '20200101000000000',
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

    def test_resolve_missing_modify04(self):
        """Resolve item with empty modify (infer from none)"""
        book = self.init_book(
            self.test_root,
            meta={
                'foobar': {
                    'title': 'MyTitle中文',
                    'type': 'folder',
                    'create': '',
                    'modify': '',
                },
            },
            toc={
                'root': [
                    'foobar',
                ],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'foobar': {
                'title': 'MyTitle中文',
                'type': 'folder',
                'create': '',
                'modify': '',
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                'foobar',
            ],
        })

    def test_resolve_older_mtime(self):
        """Resolve item with modify older than mtime of index file"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'MyTitle中文',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        generator = wsb_check.BookChecker(book, resolve_older_mtime=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'source': 'http://example.com',
                'icon': 'favicon.ico'
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

    def test_resolve_toc_invalid01(self):
        """Remove invalid items from TOC."""
        book = self.init_book(
            self.test_root,
            meta={
                'item1': {
                    'title': 'MyTitle中文',
                    'type': 'folder',
                },
                'item2': {
                    'title': 'MyTitle2',
                    'type': 'separator',
                }
            },
            toc={
                'root': [
                    'item1',
                    'unknown1',
                    'unknown2',
                    'hidden',
                    'recycle',
                ],
                'item1': [
                    'item2',
                    'unknown3',
                    'root',
                ],
                'item3': [
                    'item1',
                ],
                'recycle': [
                    'item4',
                ],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_toc_invalid=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'item1': {
                'title': 'MyTitle中文',
                'type': 'folder',
            },
            'item2': {
                'title': 'MyTitle2',
                'type': 'separator',
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'recycle': [],
        })

    def test_resolve_toc_invalid02(self):
        """Don't error if toc[id] has been removed when checking its ref IDs."""
        book = self.init_book(
            self.test_root,
            meta={},
            toc={
                'root': [
                    'unknown',
                ],
                'unknown': [
                    'item1',
                ],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_toc_invalid=True, resolve_missing_index=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {})

        self.assertDictEqual(book.toc, {
            'root': [],
        })

    def test_resolve_toc_unreachable(self):
        """Resolve unreachable items."""
        book = self.init_book(
            self.test_root,
            meta={
                'item1': {
                    'title': 'MyTitle中文',
                    'type': 'folder',
                },
                'item2': {
                    'title': 'MyTitle2',
                    'type': 'separator',
                },
            },
            toc={
                'root': [],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_toc_unreachable=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'item1': {
                'title': 'MyTitle中文',
                'type': 'folder',
            },
            'item2': {
                'title': 'MyTitle2',
                'type': 'separator',
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                'item1',
                'item2',
            ],
        })

    def test_resolve_toc_empty_subtree(self):
        """Resolve empty TOC item lists."""
        book = self.init_book(
            self.test_root,
            meta={
                'item1': {
                    'title': 'MyTitle中文',
                    'type': 'folder',
                },
                'item2': {
                    'title': 'MyTitle2',
                    'type': 'separator',
                },
            },
            toc={
                'root': [
                    'item1',
                    'item2',
                ],
                'item1': [],
                'item2': [],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_toc_empty_subtree=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'item1': {
                'title': 'MyTitle中文',
                'type': 'folder',
            },
            'item2': {
                'title': 'MyTitle2',
                'type': 'separator',
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                'item1',
                'item2',
            ],
        })

    def test_resolve_unindexed_files(self):
        book = self.init_book(
            self.test_root,
            meta={
                'item1': {},
            },
            toc={
                'root': [
                    'item1',
                ],
            },
        )

        test_file = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html data-scrapbook-create="20200101030405067"
      data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文 1</title>
</head>
<body>
page content 1
</body>
</html>""")
        ts = datetime(2021, 1, 1, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_file, (ts, ts))

        test_file = os.path.join(self.test_root, '20200102000000000.html')
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html data-scrapbook-create="20200102030405067"
      data-scrapbook-source="https://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文 2</title>
</head>
<body>
page content 2
</body>
</html>""")
        ts = datetime(2021, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_file, (ts, ts))

        generator = wsb_check.BookChecker(book, resolve_unindexed_files=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'item1': {},
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle 中文 1',
                'type': '',
                'create': '20200101030405067',
                'modify': '20210101030405067',
                'icon': '',
                'source': 'http://example.com',
                'comment': '',
            },
            '20200102000000000': {
                'index': '20200102000000000.html',
                'title': 'MyTitle 中文 2',
                'type': '',
                'create': '20200102030405067',
                'modify': '20210102030405067',
                'icon': '',
                'source': 'https://example.com',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                'item1',
                '20200101000000000',
                '20200102000000000',
            ],
        })

    def test_resolve_unindexed_files_icon(self):
        """Favicons should be cached regardless of other resolve options."""
        test_index = os.path.join(self.test_root, '20200101000000000.htz')
        with zipfile.ZipFile(test_index, 'w') as zh:
            zh.writestr('index.html', '<link rel="shortcut icon" href="favicon.bmp">')
            zh.writestr(
                'favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

        book = self.init_book(self.test_root)
        generator = wsb_check.BookChecker(book, resolve_unindexed_files=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.htz',
                'title': '',
                'type': '',
                'create': mock.ANY,
                'modify': mock.ANY,
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                'source': '',
                'comment': '',
            },
        })
        self.assertEqual(
            os.listdir(os.path.join(self.test_tree, 'favicon')),
            ['dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'],
        )

    def test_resolve_unindexed_files_exclude_support_folders(self):
        book = self.init_book(
            self.test_root,
            meta={
                'item1': {
                    'index': 'item1.html',
                },
            },
            toc={
                'root': [
                    'item1',
                ],
            },
        )
        test_file = os.path.join(self.test_root, 'item1.html')
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('item page content')
        sup_dir = os.path.join(self.test_root, 'item1.files')
        os.makedirs(sup_dir)
        with open(os.path.join(sup_dir, 'frame.html'), 'w', encoding='UTF-8') as fh:
            fh.write('frame content')
        sup_dir = os.path.join(self.test_root, 'item1_files')
        os.makedirs(sup_dir)
        with open(os.path.join(sup_dir, 'frame.html'), 'w', encoding='UTF-8') as fh:
            fh.write('frame content')

        test_file = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')
        sup_dir = os.path.join(self.test_root, '20200101000000000.files')
        os.makedirs(sup_dir)
        with open(os.path.join(sup_dir, 'frame.html'), 'w', encoding='UTF-8') as fh:
            fh.write('frame content')
        sup_dir = os.path.join(self.test_root, '20200101000000000_files')
        os.makedirs(sup_dir)
        with open(os.path.join(sup_dir, 'frame.html'), 'w', encoding='UTF-8') as fh:
            fh.write('frame content')

        generator = wsb_check.BookChecker(book, resolve_unindexed_files=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'item1': {
                'index': 'item1.html',
            },
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': '',
                'type': '',
                'create': mock.ANY,
                'modify': mock.ANY,
                'icon': '',
                'source': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                'item1',
                '20200101000000000',
            ],
        })

    def test_resolve_unindexed_files_exclude_wsb(self):
        """<book>/.wsb should be skipped."""
        book = self.init_book(self.test_root, config="""\
[book ""]
top_dir = top
data_dir =
tree_dir = .wsb/tree
""")

        wsb_file = os.path.join(self.test_root, 'top', WSB_DIR, 'index.html')
        os.makedirs(os.path.dirname(wsb_file), exist_ok=True)
        with open(wsb_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>index content""")

        generator = wsb_check.BookChecker(book, resolve_unindexed_files=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {})
        self.assertDictEqual(book.toc, {})

    def test_resolve_absolute_icon01(self):
        """Check favicon with absolute URL."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000.html',
                    'icon': 'data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA',
                },
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        generator = wsb_check.BookChecker(book, resolve_absolute_icon=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'type': '',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            },
        })
        self.assertEqual(
            os.listdir(os.path.join(self.test_tree, 'favicon')),
            ['dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'],
        )

    def test_resolve_absolute_icon02(self):
        """Keep original value for bad data URL."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000.html',
                    'icon': 'data:',
                },
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        generator = wsb_check.BookChecker(book, resolve_absolute_icon=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'type': '',
                'icon': 'data:',
            },
        })
        self.assertFalse(os.path.exists(os.path.join(self.test_tree, 'favicon')))

    def test_resolve_absolute_icon03(self):
        """Keep original value for bad data URL."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000.html',
                    'icon': 'data:image/bmp;base64,Qk08AAA-------',
                },
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        generator = wsb_check.BookChecker(book, resolve_absolute_icon=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'type': '',
                'icon': 'data:image/bmp;base64,Qk08AAA-------',
            },
        })
        self.assertFalse(os.path.exists(os.path.join(self.test_tree, 'favicon')))

    def test_resolve_absolute_icon04(self):
        """Keep original value for bad protocol."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000.html',
                    'icon': 'blob:http%3A//example.com/c94d498c-7818-49b3-8e79-d3959938ba0a',
                },
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        generator = wsb_check.BookChecker(book, resolve_absolute_icon=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'type': '',
                'icon': 'blob:http%3A//example.com/c94d498c-7818-49b3-8e79-d3959938ba0a',
            },
        })
        self.assertFalse(os.path.exists(os.path.join(self.test_tree, 'favicon')))

    def test_resolve_unused_icon(self):
        """Check for unused favicons."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000.htz',
                    'type': '',
                    'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                },
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000.htz')
        with zipfile.ZipFile(test_index, 'w') as zh:
            zh.writestr('index.html', 'dummy')
        os.makedirs(os.path.join(self.test_tree, 'favicon'))
        with open(os.path.join(self.test_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'), 'w') as fh:
            fh.write('dummy')
        with open(os.path.join(self.test_tree, 'favicon', 'foo.ico'), 'w') as fh:
            fh.write('dummy')
        with open(os.path.join(self.test_tree, 'favicon', 'bar.png'), 'w') as fh:
            fh.write('dummy')
        with open(os.path.join(self.test_tree, 'favicon', 'baz.jpg'), 'w') as fh:
            fh.write('dummy')

        generator = wsb_check.BookChecker(book, resolve_unused_icon=True)
        for _info in generator.run():
            pass

        self.assertEqual(
            os.listdir(os.path.join(self.test_tree, 'favicon')),
            ['dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'],
        )
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.htz',
                'type': '',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            },
        })

    def test_resolve_all(self):
        """A test case for resolve_all.

        - Resolve empty TOC item lists after other resolves.
        """
        book = self.init_book(
            self.test_root,
            meta={
                'item1': {
                    'title': 'MyTitle中文',
                    'type': 'folder',
                },
                'item2': {
                    'title': 'MyTitle2',
                    'type': 'separator',
                },
                'item3': {
                    'title': 'MyTitle2',
                    'type': '',
                    'index': 'item3.html',
                },
            },
            toc={
                'root': [
                    'item1',
                    'item2',
                ],
                'item1': [
                    'item3',
                    'nonexistent',
                ],
                'item2': [
                    'recycle',
                ],
            },
        )

        generator = wsb_check.BookChecker(book, resolve_all=True)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            'item1': {
                'title': 'MyTitle中文',
                'type': 'folder',
            },
            'item2': {
                'title': 'MyTitle2',
                'type': 'separator',
            },
        })

        self.assertDictEqual(book.toc, {
            'root': [
                'item1',
                'item2',
            ],
        })


if __name__ == '__main__':
    unittest.main()
