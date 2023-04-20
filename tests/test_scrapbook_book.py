import copy
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from webscrapbook import WSB_DIR, util
from webscrapbook._polyfill import zipfile
from webscrapbook.scrapbook import book as wsb_book
from webscrapbook.scrapbook.book import Book
from webscrapbook.scrapbook.host import Host

from . import DUMMY_BYTES, TEMP_DIR, glob_files


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='book-', dir=TEMP_DIR)
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
    """Cleanup the temp directory."""
    _tmpdir.cleanup()

    # stop mock
    for mocking in mockings:
        mocking.stop()


class TestBook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_wsbdir = os.path.join(self.test_root, WSB_DIR)
        self.test_config = os.path.join(self.test_root, WSB_DIR, 'config.ini')

        os.makedirs(self.test_wsbdir)

    def create_general_config(self):
        with open(self.test_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[book ""]
name = scrapbook
top_dir =
data_dir = data
tree_dir = tree
index = tree/map.html
no_tree = false
""")


class TestBasicMethods(TestBook):
    def test_init01(self):
        """Check basic"""
        with open(self.test_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[book ""]
name = scrapbook
top_dir =
data_dir = data
tree_dir = tree
index = tree/map.html
no_tree = false
""")

        host = Host(self.test_root)
        book = Book(host)

        self.assertEqual(book.host, host)
        self.assertEqual(book.id, '')
        self.assertEqual(book.name, 'scrapbook')
        self.assertEqual(book.root, self.test_root)
        self.assertEqual(book.top_dir, self.test_root)
        self.assertEqual(book.data_dir, os.path.join(self.test_root, 'data'))
        self.assertEqual(book.tree_dir, os.path.join(self.test_root, 'tree'))
        self.assertFalse(book.no_tree)

    def test_init02(self):
        """Check book_id param"""
        with open(self.test_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[book "book1"]
name = scrapbook1
top_dir =
data_dir =
tree_dir = .wsb/tree
index = .wsb/tree/map.html
no_tree = false
""")

        host = Host(self.test_root)
        book = Book(host, 'book1')

        self.assertEqual(book.host, host)
        self.assertEqual(book.id, 'book1')
        self.assertEqual(book.name, 'scrapbook1')
        self.assertEqual(book.root, self.test_root)
        self.assertEqual(book.top_dir, self.test_root)
        self.assertEqual(book.data_dir, self.test_root)
        self.assertEqual(book.tree_dir, os.path.join(self.test_root, '.wsb', 'tree'))
        self.assertFalse(book.no_tree)

    def test_init03(self):
        """Check modified path"""
        with open(self.test_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[app]
root = public

[book ""]
name = scrapbook
top_dir = sb
data_dir = data
tree_dir = tree
index = tree/map.html
no_tree = false
""")

        host = Host(self.test_root)
        book = Book(host)

        self.assertEqual(book.host, host)
        self.assertEqual(book.id, '')
        self.assertEqual(book.name, 'scrapbook')
        self.assertEqual(book.root, self.test_root)
        self.assertEqual(book.top_dir, os.path.join(self.test_root, 'public', 'sb'))
        self.assertEqual(book.data_dir, os.path.join(self.test_root, 'public', 'sb', 'data'))
        self.assertEqual(book.tree_dir, os.path.join(self.test_root, 'public', 'sb', 'tree'))
        self.assertFalse(book.no_tree)

    def test_get_subpath(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        self.assertEqual(book.get_subpath(os.path.join(self.test_root, 'tree', 'meta.js')), 'tree/meta.js')

    def test_get_tree_file(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        self.assertEqual(book.get_tree_file('meta'), os.path.join(self.test_root, 'tree', 'meta.js'))
        self.assertEqual(book.get_tree_file('toc', 1), os.path.join(self.test_root, 'tree', 'toc1.js'))

    def test_iter_tree_files01(self):
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'tree'))
        with open(os.path.join(self.test_root, 'tree', 'meta.js'), 'w', encoding='UTF-8'):
            pass
        with open(os.path.join(self.test_root, 'tree', 'meta1.js'), 'w', encoding='UTF-8'):
            pass
        with open(os.path.join(self.test_root, 'tree', 'meta2.js'), 'w', encoding='UTF-8'):
            pass

        book = Book(Host(self.test_root))
        self.assertEqual(list(book.iter_tree_files('meta')), [
            os.path.join(self.test_root, 'tree', 'meta.js'),
            os.path.join(self.test_root, 'tree', 'meta1.js'),
            os.path.join(self.test_root, 'tree', 'meta2.js'),
        ])

    def test_iter_tree_files02(self):
        """Break since nonexisting index"""
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'tree'))
        with open(os.path.join(self.test_root, 'tree', 'meta.js'), 'w', encoding='UTF-8'):
            pass
        with open(os.path.join(self.test_root, 'tree', 'meta1.js'), 'w', encoding='UTF-8'):
            pass
        with open(os.path.join(self.test_root, 'tree', 'meta3.js'), 'w', encoding='UTF-8'):
            pass

        book = Book(Host(self.test_root))
        self.assertEqual(list(book.iter_tree_files('meta')), [
            os.path.join(self.test_root, 'tree', 'meta.js'),
            os.path.join(self.test_root, 'tree', 'meta1.js'),
        ])

    def test_iter_tree_files03(self):
        """Works when directory not exist"""
        book = Book(Host(self.test_root))
        self.assertEqual(list(book.iter_tree_files('meta')), [])

    @mock.patch('webscrapbook.scrapbook.book.Book.iter_tree_files')
    def test_iter_meta_files(self, mock_func):
        book = Book(Host(self.test_root))
        for _ in book.iter_meta_files():
            pass
        mock_func.assert_called_once_with('meta')

    @mock.patch('webscrapbook.scrapbook.book.Book.iter_tree_files')
    def test_iter_toc_files(self, mock_func):
        book = Book(Host(self.test_root))
        for _ in book.iter_toc_files():
            pass
        mock_func.assert_called_once_with('toc')

    @mock.patch('webscrapbook.scrapbook.book.Book.iter_tree_files')
    def test_iter_fulltext_files(self, mock_func):
        book = Book(Host(self.test_root))
        for _ in book.iter_fulltext_files():
            pass
        mock_func.assert_called_once_with('fulltext')

    def test_load_tree_file01(self):
        """Test normal loading"""
        self.create_general_config()
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")

        book = Book(Host(self.test_root))
        self.assertEqual(
            book.load_tree_file(os.path.join(self.test_root, 'meta.js')), {
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'Dummy',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                },
            })

    def test_load_tree_file02(self):
        """Test malformed wrapping"""
        self.create_general_config()
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
}""")

        book = Book(Host(self.test_root))
        with self.assertRaises(wsb_book.TreeFileMalformedWrappingError):
            book.load_tree_file(os.path.join(self.test_root, 'meta.js'))

    def test_load_tree_file03(self):
        """Test malformed wrapping"""
        self.create_general_config()
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""
scrapbook.meta{
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")

        book = Book(Host(self.test_root))
        with self.assertRaises(wsb_book.TreeFileMalformedWrappingError):
            book.load_tree_file(os.path.join(self.test_root, 'meta.js'))

    def test_load_tree_file04(self):
        """Test malformed wrapping"""
        self.create_general_config()
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")

        book = Book(Host(self.test_root))
        with self.assertRaises(wsb_book.TreeFileMalformedWrappingError):
            book.load_tree_file(os.path.join(self.test_root, 'meta.js'))

    def test_load_tree_file05(self):
        """Test malformed JSON"""
        self.create_general_config()
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""
scrapbook.meta({
  '20200101000000000': {
    index: '20200101000000000/index.html',
    title: 'Dummy',
    type: '',
    create: '20200101000000000',
    modify: '20200101000000000'
  }
})""")

        book = Book(Host(self.test_root))
        with self.assertRaises(wsb_book.TreeFileMalformedJsonError):
            book.load_tree_file(os.path.join(self.test_root, 'meta.js'))

    def test_load_tree_file06(self):
        """Test empty file should not error out."""
        self.create_general_config()
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write('')

        book = Book(Host(self.test_root))
        self.assertEqual(book.load_tree_file(os.path.join(self.test_root, 'meta.js')), {})

    def test_load_tree_files01(self):
        """Test normal loading

        - Item of same ID from the latter overwrites the formatter.
        - Item with None value should be removed.
        """
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'tree'))
        with open(os.path.join(self.test_root, 'tree', 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "comment": "comment"
  },
  "20200101000000001": {
    "index": "20200101000000001/index.html",
    "title": "Dummy1",
    "type": "",
    "create": "20200101000000001",
    "modify": "20200101000000001",
    "comment": "comment1"
  },
  "20200101000000002": {
    "index": "20200101000000002/index.html",
    "title": "Dummy2",
    "type": "",
    "create": "20200101000000002",
    "modify": "20200101000000002",
    "comment": "comment2"
  }
})""")
        with open(os.path.join(self.test_root, 'tree', 'meta1.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.meta({
  "20200101000000001": {
    "index": "20200101000000001/index.html",
    "title": "Dummy1rev",
    "type": "",
    "create": "20200101000000001",
    "modify": "20200101000000011"
  },
  "20200101000000002": null,
  "20200101000000003": {
    "index": "20200101000000003/index.html",
    "title": "Dummy3",
    "type": "",
    "create": "20200101000000003",
    "modify": "20200101000000003",
    "comment": "comment3"
  }
})""")

        book = Book(Host(self.test_root))
        self.assertEqual(book.load_tree_files('meta'), {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'Dummy',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'comment': 'comment',
            },
            '20200101000000001': {
                'index': '20200101000000001/index.html',
                'title': 'Dummy1rev',
                'type': '',
                'create': '20200101000000001',
                'modify': '20200101000000011',
            },
            '20200101000000003': {
                'index': '20200101000000003/index.html',
                'title': 'Dummy3',
                'type': '',
                'create': '20200101000000003',
                'modify': '20200101000000003',
                'comment': 'comment3',
            },
        })

    def test_load_tree_files02(self):
        """Works when directory not exist"""
        book = Book(Host(self.test_root))
        self.assertEqual(book.load_tree_files('meta'), {})

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_meta_files01(self, mock_func):
        book = Book(Host(self.test_root))
        book.load_meta_files()
        mock_func.assert_called_once_with('meta')

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_meta_files02(self, mock_func):
        book = Book(Host(self.test_root))
        book.meta = {}
        book.load_meta_files()
        mock_func.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_meta_files03(self, mock_func):
        book = Book(Host(self.test_root))
        book.meta = {}
        book.load_meta_files(refresh=True)
        mock_func.assert_called_once_with('meta')

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_toc_files01(self, mock_func):
        book = Book(Host(self.test_root))
        book.load_toc_files()
        mock_func.assert_called_once_with('toc')

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_toc_files02(self, mock_func):
        book = Book(Host(self.test_root))
        book.toc = {}
        book.load_toc_files()
        mock_func.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_toc_files03(self, mock_func):
        book = Book(Host(self.test_root))
        book.toc = {}
        book.load_toc_files(refresh=True)
        mock_func.assert_called_once_with('toc')

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_fulltext_files01(self, mock_func):
        book = Book(Host(self.test_root))
        book.load_fulltext_files()
        mock_func.assert_called_once_with('fulltext')

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_fulltext_files02(self, mock_func):
        book = Book(Host(self.test_root))
        book.fulltext = {}
        book.load_fulltext_files()
        mock_func.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.book.Book.load_tree_files')
    def test_load_fulltext_files03(self, mock_func):
        book = Book(Host(self.test_root))
        book.fulltext = {}
        book.load_fulltext_files(refresh=True)
        mock_func.assert_called_once_with('fulltext')

    def test_save_meta_files01(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.meta = {
            '20200101000000000': {'title': 'Dummy 1 中文'},
            '20200101000000001': {'title': 'Dummy 2 中文'},
        }

        book.save_meta_files()

        with open(os.path.join(self.test_root, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.meta({
  "20200101000000000": {
    "title": "Dummy 1 中文"
  },
  "20200101000000001": {
    "title": "Dummy 2 中文"
  }
})""")

    @mock.patch('webscrapbook.scrapbook.book.Book.SAVE_META_THRESHOLD', 3)
    def test_save_meta_files02(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.meta = {
            '20200101000000000': {'title': 'Dummy 1 中文'},
            '20200101000000001': {'title': 'Dummy 2 中文'},
            '20200101000000002': {'title': 'Dummy 3 中文'},
            '20200101000000003': {'title': 'Dummy 4 中文'},
        }

        book.save_meta_files()

        with open(os.path.join(self.test_root, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.meta({
  "20200101000000000": {
    "title": "Dummy 1 中文"
  },
  "20200101000000001": {
    "title": "Dummy 2 中文"
  }
})""")
        with open(os.path.join(self.test_root, 'tree', 'meta1.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.meta({
  "20200101000000002": {
    "title": "Dummy 3 中文"
  },
  "20200101000000003": {
    "title": "Dummy 4 中文"
  }
})""")

    def test_save_meta_files03(self):
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'tree'))
        with open(os.path.join(self.test_root, 'tree', 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')
        with open(os.path.join(self.test_root, 'tree', 'meta1.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy1')
        with open(os.path.join(self.test_root, 'tree', 'meta2.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy2')
        with open(os.path.join(self.test_root, 'tree', 'meta3.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy3')

        book = Book(Host(self.test_root))
        book.meta = {
            '20200101000000000': {'title': 'Dummy 1 中文'},
            '20200101000000001': {'title': 'Dummy 2 中文'},
        }

        book.save_meta_files()

        with open(os.path.join(self.test_root, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.meta({
  "20200101000000000": {
    "title": "Dummy 1 中文"
  },
  "20200101000000001": {
    "title": "Dummy 2 中文"
  }
})""")
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'meta1.js')))
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'meta2.js')))
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'meta3.js')))
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'meta4.js')))

    def test_save_meta_files04(self):
        """Check if U+2028 and U+2029 are escaped in the embedded JSON."""
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.meta = {
            '20200101\u2028000000000': {'title\u20281': 'Dummy 1\u2028中文'},
            '20200101\u2029000000001': {'title\u20292': 'Dummy 2\u2029中文'},
        }

        book.save_meta_files()

        with open(os.path.join(self.test_root, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), r"""/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.meta({
  "20200101\u2028000000000": {
    "title\u20281": "Dummy 1\u2028中文"
  },
  "20200101\u2029000000001": {
    "title\u20292": "Dummy 2\u2029中文"
  }
})""")

    def test_save_toc_files01(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.toc = {
            'root': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
            ],
            '20200101000000000': [
                '20200101000000003'
            ]
        }

        book.save_toc_files()

        with open(os.path.join(self.test_root, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000000001",
    "20200101000000002"
  ],
  "20200101000000000": [
    "20200101000000003"
  ]
})""")

    @mock.patch('webscrapbook.scrapbook.book.Book.SAVE_TOC_THRESHOLD', 3)
    def test_save_toc_files02(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.toc = {
            'root': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
                '20200101000000003',
                '20200101000000004',
            ],
            '20200101000000001': [
                '20200101000000011'
            ],
            '20200101000000002': [
                '20200101000000021'
            ],
            '20200101000000003': [
                '20200101000000031',
                '20200101000000032'
            ],
        }

        book.save_toc_files()

        with open(os.path.join(self.test_root, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000000001",
    "20200101000000002",
    "20200101000000003",
    "20200101000000004"
  ]
})""")
        with open(os.path.join(self.test_root, 'tree', 'toc1.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.toc({
  "20200101000000001": [
    "20200101000000011"
  ],
  "20200101000000002": [
    "20200101000000021"
  ]
})""")
        with open(os.path.join(self.test_root, 'tree', 'toc2.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.toc({
  "20200101000000003": [
    "20200101000000031",
    "20200101000000032"
  ]
})""")

    def test_save_toc_files03(self):
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'tree'))
        with open(os.path.join(self.test_root, 'tree', 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')
        with open(os.path.join(self.test_root, 'tree', 'toc1.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy1')
        with open(os.path.join(self.test_root, 'tree', 'toc2.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy2')
        with open(os.path.join(self.test_root, 'tree', 'toc4.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy4')

        book = Book(Host(self.test_root))
        book.toc = {
            'root': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
            ],
            '20200101000000000': [
                '20200101000000003'
            ]
        }

        book.save_toc_files()

        with open(os.path.join(self.test_root, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000000001",
    "20200101000000002"
  ],
  "20200101000000000": [
    "20200101000000003"
  ]
})""")
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'toc1.js')))
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'toc2.js')))
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'toc3.js')))
        self.assertTrue(os.path.exists(os.path.join(self.test_root, 'tree', 'toc4.js')))

    def test_save_toc_files04(self):
        """Check if U+2028 and U+2029 are escaped in the embedded JSON."""
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.toc = {
            'root': [
                '20200101\u2028000000000',
                '20200101\u2029000000001',
            ],
            '20200101\u2028000000000': [
                '20200101\u2029000000003'
            ]
        }

        book.save_toc_files()

        with open(os.path.join(self.test_root, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), r"""/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.toc({
  "root": [
    "20200101\u2028000000000",
    "20200101\u2029000000001"
  ],
  "20200101\u2028000000000": [
    "20200101\u2029000000003"
  ]
})""")

    def test_save_fulltext_files01(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.fulltext = {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy text 1 中文',
                }
            },
            '20200101000000001': {
                'index.html': {
                    'content': 'dummy text 2 中文',
                }
            },
        }

        book.save_fulltext_files()

        with open(os.path.join(self.test_root, 'tree', 'fulltext.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy text 1 中文"
  }
 },
 "20200101000000001": {
  "index.html": {
   "content": "dummy text 2 中文"
  }
 }
})""")

    @mock.patch('webscrapbook.scrapbook.book.Book.SAVE_FULLTEXT_THRESHOLD', 10)
    def test_save_fulltext_files02(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.fulltext = {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy text 1 中文',
                },
                'frame.html': {
                    'content': 'frame page content',
                },
            },
            '20200101000000001': {
                'index.html': {
                    'content': 'dummy text 2 中文',
                },
            },
            '20200101000000002': {
                'index.html': {
                    'content': 'dummy text 3 中文',
                },
            },
        }

        book.save_fulltext_files()

        with open(os.path.join(self.test_root, 'tree', 'fulltext.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy text 1 中文"
  },
  "frame.html": {
   "content": "frame page content"
  }
 }
})""")
        with open(os.path.join(self.test_root, 'tree', 'fulltext1.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({
 "20200101000000001": {
  "index.html": {
   "content": "dummy text 2 中文"
  }
 }
})""")
        with open(os.path.join(self.test_root, 'tree', 'fulltext2.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({
 "20200101000000002": {
  "index.html": {
   "content": "dummy text 3 中文"
  }
 }
})""")

    @mock.patch('webscrapbook.scrapbook.book.Book.SAVE_FULLTEXT_THRESHOLD', 10)
    def test_save_fulltext_files03(self):
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'tree'))
        with open(os.path.join(self.test_root, 'tree', 'fulltext.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')
        with open(os.path.join(self.test_root, 'tree', 'fulltext1.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy1')
        with open(os.path.join(self.test_root, 'tree', 'fulltext2.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy2')
        with open(os.path.join(self.test_root, 'tree', 'fulltext3.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy3')
        with open(os.path.join(self.test_root, 'tree', 'fulltext4.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy4')
        with open(os.path.join(self.test_root, 'tree', 'fulltext6.js'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy6')

        book = Book(Host(self.test_root))
        book.fulltext = {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy text 1 中文',
                },
                'frame.html': {
                    'content': 'frame page content',
                },
            },
            '20200101000000001': {
                'index.html': {
                    'content': 'dummy text 2 中文',
                },
            },
        }

        book.save_fulltext_files()

        with open(os.path.join(self.test_root, 'tree', 'fulltext.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy text 1 中文"
  },
  "frame.html": {
   "content": "frame page content"
  }
 }
})""")
        with open(os.path.join(self.test_root, 'tree', 'fulltext1.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({
 "20200101000000001": {
  "index.html": {
   "content": "dummy text 2 中文"
  }
 }
})""")
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'fulltext2.js')))
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'fulltext3.js')))
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'fulltext4.js')))
        self.assertFalse(os.path.exists(os.path.join(self.test_root, 'tree', 'fulltext5.js')))
        self.assertTrue(os.path.exists(os.path.join(self.test_root, 'tree', 'fulltext6.js')))

    def test_save_fulltext_files04(self):
        """Check if U+2028 and U+2029 are escaped in the embedded JSON."""
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.fulltext = {
            '20200101\u2028000000000': {
                'index.html': {
                    'content': 'dummy text 1 中文',
                },
            },
            '20200101\u2029000000001': {
                'index.html': {
                    'content': 'dummy text 2 中文',
                },
            },
        }

        book.save_fulltext_files()

        with open(os.path.join(self.test_root, 'tree', 'fulltext.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), r"""/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({
 "20200101\u2028000000000": {
  "index.html": {
   "content": "dummy text 1 中文"
  }
 },
 "20200101\u2029000000001": {
  "index.html": {
   "content": "dummy text 2 中文"
  }
 }
})""")

    @mock.patch('webscrapbook.scrapbook.host.Host.auto_backup')
    def test_backup(self, mock_func):
        test_file = os.path.join(self.test_root, 'tree', 'meta.js')
        host = Host(self.test_root)
        book = Book(host)

        book.backup(test_file)
        mock_func.assert_called_with(test_file)

        book.backup(test_file, base=self.test_wsbdir, move=False)
        mock_func.assert_called_with(test_file, base=self.test_wsbdir, move=False)

    @mock.patch('webscrapbook.scrapbook.host.FileLock')
    def test_get_lock01(self, mock_filelock):
        self.create_general_config()
        host = Host(self.test_root)
        book = Book(host)
        book.get_lock('test')
        mock_filelock.assert_called_once_with(host, 'book--test')

    @mock.patch('webscrapbook.scrapbook.host.FileLock')
    def test_get_lock02(self, mock_filelock):
        """With parameters"""
        self.create_general_config()
        host = Host(self.test_root)
        book = Book(host)
        book.get_lock(
            'test',
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True,
        )
        mock_filelock.assert_called_once_with(
            host, 'book--test',
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True,
        )

    @mock.patch('webscrapbook.scrapbook.book.Book.get_lock')
    def test_get_tree_lock01(self, mock_get_lock):
        self.create_general_config()
        host = Host(self.test_root)
        book = Book(host)
        book.get_tree_lock()
        mock_get_lock.assert_called_once_with('tree')

    @mock.patch('webscrapbook.scrapbook.book.Book.get_lock')
    def test_get_tree_lock02(self, mock_get_lock):
        """With parameters"""
        self.create_general_config()
        host = Host(self.test_root)
        book = Book(host)
        book.get_tree_lock(
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True,
        )
        mock_get_lock.assert_called_once_with(
            'tree',
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True,
        )

    def test_get_index_paths01(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        self.assertEqual(book.get_index_paths('20200101000000000/index.html'), ['index.html'])
        self.assertEqual(book.get_index_paths('20200101000000000.html'), ['20200101000000000.html'])
        self.assertEqual(book.get_index_paths('20200101000000000.htz'), ['index.html'])

    def test_get_index_paths02(self):
        """MAFF with single page"""
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'data'))
        archive_file = os.path.join(self.test_root, 'data', '20200101000000000.maff')
        with zipfile.ZipFile(archive_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """dummy""")
        book = Book(Host(self.test_root))

        self.assertEqual(book.get_index_paths('20200101000000000.maff'), ['20200101000000000/index.html'])

    def test_get_index_paths03(self):
        """MAFF with multiple pages"""
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'data'))
        archive_file = os.path.join(self.test_root, 'data', '20200101000000000.maff')
        with zipfile.ZipFile(archive_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """dummy""")
            zh.writestr('20200101000000001/index.html', """dummy""")
        book = Book(Host(self.test_root))

        self.assertEqual(book.get_index_paths('20200101000000000.maff'), ['20200101000000000/index.html', '20200101000000001/index.html'])

    def test_get_index_paths04(self):
        """MAFF with no page"""
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'data'))
        archive_file = os.path.join(self.test_root, 'data', '20200101000000000.maff')
        with zipfile.ZipFile(archive_file, 'w'):
            pass
        book = Book(Host(self.test_root))

        self.assertEqual(book.get_index_paths('20200101000000000.maff'), [])

    def test_get_icon_file01(self):
        """Pass if file not exist."""
        book = Book(Host(self.test_root))

        self.assertIsNone(book.get_icon_file({
            'index': '20200101000000000/index.html',
            'icon': 'http://example.com',
        }))

        self.assertIsNone(book.get_icon_file({
            'index': '20200101000000000/index.html',
            'icon': 'data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA',
        }))

        self.assertIsNone(book.get_icon_file({
            'index': '20200101000000000/index.html',
            'icon': '//example.com',
        }))

        self.assertIsNone(book.get_icon_file({
            'index': '20200101000000000/index.html',
            'icon': '/favicon.ico',
        }))

        self.assertIsNone(book.get_icon_file({
            'index': '20200101000000000/index.html',
            'icon': '',
        }))

        self.assertIsNone(book.get_icon_file({
            'index': '20200101000000000/index.html',
            'icon': '?id=123',
        }))

        self.assertIsNone(book.get_icon_file({
            'index': '20200101000000000/index.html',
            'icon': '#test',
        }))

        self.assertEqual(
            book.get_icon_file({
                'icon': 'favicon.ico?id=123#test',
            }),
            os.path.join(book.data_dir, 'favicon.ico'),
        )

        self.assertEqual(
            book.get_icon_file({
                'icon': '%E4%B8%AD%E6%96%87%231.ico?id=123#test',
            }),
            os.path.join(book.data_dir, '中文#1.ico'),
        )

        self.assertEqual(
            book.get_icon_file({
                'index': '20200101000000000/index.html',
                'icon': 'favicon.ico?id=123#test',
            }),
            os.path.join(book.data_dir, '20200101000000000', 'favicon.ico'),
        )

        self.assertEqual(
            book.get_icon_file({
                'index': '20200101000000000.html',
                'icon': 'favicon.ico?id=123#test',
            }),
            os.path.join(book.data_dir, 'favicon.ico'),
        )

        self.assertEqual(
            book.get_icon_file({
                'index': '20200101000000000.maff',
                'icon': 'favicon.ico?id=123#test',
            }),
            os.path.join(book.data_dir, 'favicon.ico'),
        )

        self.assertEqual(
            book.get_icon_file({
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp?id=123#test',
            }),
            os.path.join(book.tree_dir, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'),
        )

    def test_load_postit_file01(self):
        """Test for common postit file wrapper."""
        test_file = os.path.join(self.test_root, 'index.html')
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html><html><head><meta charset="UTF-8">\
<meta name="viewport" content="width=device-width">\
<style>pre{white-space: pre-wrap; overflow-wrap: break-word;}</style>\
</head><body><pre>
postit content
2nd line
3rd line
</pre></body></html>""")

        book = Book(Host(self.test_root))
        content = book.load_postit_file(test_file)
        self.assertEqual(content, """\
postit content
2nd line
3rd line""")

    def test_load_postit_file02(self):
        """Test for common legacy postit file wrapper."""
        test_file = os.path.join(self.test_root, 'index.html')
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<html><head><meta http-equiv="Content-Type" content="text/html;Charset=UTF-8"></head><body><pre>
postit content
2nd line
3rd line
</pre></body></html>""")

        book = Book(Host(self.test_root))
        content = book.load_postit_file(test_file)
        self.assertEqual(content, """\
postit content
2nd line
3rd line""")

    def test_load_postit_file03(self):
        """Return original text if malformatted."""
        test_file = os.path.join(self.test_root, 'index.html')
        html = """\
<html><head><meta http-equiv="Content-Type" content="text/html;Charset=UTF-8"></head><body>
postit content
2nd line
3rd line
</body></html>"""
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write(html)

        book = Book(Host(self.test_root))
        content = book.load_postit_file(test_file)
        self.assertEqual(content, html)

    def test_save_postit_file(self):
        """Test saving. Enforce LF linefeeds."""
        test_file = os.path.join(self.test_root, 'index.html')

        book = Book(Host(self.test_root))
        book.save_postit_file(test_file, """\
postit content
2nd line
3rd line""")

        with open(test_file, encoding='UTF-8', newline='') as fh:
            self.assertEqual(fh.read(), """\
<!DOCTYPE html><html><head>\
<meta charset="UTF-8">\
<meta name="viewport" content="width=device-width">\
<style>pre { white-space: pre-wrap; overflow-wrap: break-word; }</style>\
</head><body><pre>
postit content
2nd line
3rd line
</pre></body></html>""")

    def test_auto_backup(self):
        """Auto backup tree files if backup_dir is set."""
        test_dir = os.path.join(self.test_root, WSB_DIR, 'tree')
        os.makedirs(test_dir)

        meta0 = """
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})"""
        meta1 = """
scrapbook.meta({
  "20200101000000001": {
    "index": "20200101000000001/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000001",
    "modify": "20200101000000001"
  }
})"""
        toc0 = """
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000000001",
    "20200101000000002"
  ],
  "20200101000000000": [
    "20200101000000003"
  ]
})"""
        toc1 = """
scrapbook.toc({
  "20200101000000001": [
    "20200101000000004"
  ]
})"""
        fulltext0 = """
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy text 1 中文"
  }
 },
 "20200101000000001": {
  "index.html": {
   "content": "dummy text 2 中文"
  }
 }
})"""
        fulltext1 = """
scrapbook.fulltext({
 "20200101000000002": {
  "index.html": {
   "content": "dummy text 2 中文"
  }
 }
})"""

        with open(os.path.join(test_dir, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write(meta0)
        with open(os.path.join(test_dir, 'meta1.js'), 'w', encoding='UTF-8') as fh:
            fh.write(meta1)
        with open(os.path.join(test_dir, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write(toc0)
        with open(os.path.join(test_dir, 'toc1.js'), 'w', encoding='UTF-8') as fh:
            fh.write(toc1)
        with open(os.path.join(test_dir, 'fulltext.js'), 'w', encoding='UTF-8') as fh:
            fh.write(fulltext0)
        with open(os.path.join(test_dir, 'fulltext1.js'), 'w', encoding='UTF-8') as fh:
            fh.write(fulltext1)

        host = Host(self.test_root)
        book = Book(host)
        host.init_auto_backup()
        book.load_meta_files()
        book.load_toc_files()
        book.load_fulltext_files()
        book.save_meta_files()
        book.save_toc_files()
        book.save_fulltext_files()

        with open(os.path.join(host._auto_backup_dir, WSB_DIR, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), meta0)
        with open(os.path.join(host._auto_backup_dir, WSB_DIR, 'tree', 'meta1.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), meta1)
        with open(os.path.join(host._auto_backup_dir, WSB_DIR, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), toc0)
        with open(os.path.join(host._auto_backup_dir, WSB_DIR, 'tree', 'toc1.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), toc1)
        with open(os.path.join(host._auto_backup_dir, WSB_DIR, 'tree', 'fulltext.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), fulltext0)
        with open(os.path.join(host._auto_backup_dir, WSB_DIR, 'tree', 'fulltext1.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), fulltext1)

    def test_get_reachable_items(self):
        host = Host(self.test_root)
        book = Book(host)

        # basic: deep first
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
            'item1': [
                'item1-1',
                'item1-2',
            ],
            'item1-1': [
                'item1-1-1',
            ],
        }
        self.assertEqual(
            list(book.get_reachable_items('root')),
            ['root', 'item1', 'item1-1', 'item1-1-1', 'item1-2', 'item2', 'item3', 'item4'],
        )

        # no duplicate
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
                'item2',
                'item1',
                'item3',
            ],
        }
        self.assertEqual(
            list(book.get_reachable_items('root')),
            ['root', 'item1', 'item2', 'item3'],
        )

        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
            'item1': [
                'item3',
                'item4',
            ],
        }
        self.assertEqual(
            list(book.get_reachable_items('root')),
            ['root', 'item1', 'item3', 'item4', 'item2'],
        )

        # circular
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item4',
            ],
            'item4': [
                'item1',
            ],
        }
        self.assertEqual(
            list(book.get_reachable_items('item3')),
            ['item3', 'item4', 'item1', 'item2'],
        )

    def test_get_unique_id(self):
        self.create_general_config()
        host = Host(self.test_root)
        book = Book(host)
        book.toc = {}

        # get ID from current time
        book.meta = {}
        with mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000'):
            self.assertEqual(book.get_unique_id(), '20200101000000000')

        # increment if ID exists in meta
        book.meta = {
            '20200101000000000': {},
        }
        with mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000'):
            self.assertEqual(book.get_unique_id(), '20200101000000001')

        book.meta = {
            '20200101000000000': {},
            '20200101000000001': {},
            '20200101000000002': {},
            '20200101000000003': {},
        }
        with mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000'):
            self.assertEqual(book.get_unique_id(), '20200101000000004')

        # increment if a data file named after ID exists
        book.meta = {}
        util.fs.mkdir(os.path.join(book.data_dir, '20200101000000000'))
        util.fs.mkzip(os.path.join(book.data_dir, '20200101000000001.htz'))
        util.fs.mkzip(os.path.join(book.data_dir, '20200101000000002.maff'))
        util.fs.save(os.path.join(book.data_dir, '20200101000000003.html'), b'')
        util.fs.save(os.path.join(book.data_dir, '20200101000000004.md'), b'')
        with mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000'):
            self.assertEqual(book.get_unique_id(), '20200101000000005')

        # get ID from a pre-generated one
        book.meta = {}
        self.assertEqual(book.get_unique_id('20220101000000000'), '20220101000000000')

        # increment if ID exists in metaa (should skip bad timestamps)
        book.meta = {
            '20220101000059999': {},
            '20220101000100000': {},
            '20220101000100001': {},
            '20220101000100002': {},
        }
        self.assertEqual(book.get_unique_id('20220101000059999'), '20220101000100003')


class TestGetItem(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)

        # meta(+), toc(+)
        book.meta = {
            'item1': {
                'title': 'Item 1',
                'create': '20200101000000000',
                'modify': '20200102000000000',
            },
            'item2': {
                'title': 'Item 2',
                'create': '20210101000000000',
                'modify': '20210102000000000',
            },
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
        }
        self.assertEqual(book.get_item('item1'), {
            'meta': {
                'title': 'Item 1',
                'create': '20200101000000000',
                'modify': '20200102000000000',
            },
            'children': [
                'item2',
            ],
        })

        # meta(+), toc(-)
        book.meta = {
            'item1': {
                'title': 'Item 1',
                'create': '20200101000000000',
                'modify': '20200102000000000',
            },
        }
        book.toc = {
            'root': [
                'item1',
            ],
        }
        self.assertEqual(book.get_item('item1'), {
            'meta': {
                'title': 'Item 1',
                'create': '20200101000000000',
                'modify': '20200102000000000',
            },
        })

        # meta(-), toc(+)
        book.meta = {
            'item2': {
                'title': 'Item 2',
                'create': '20210101000000000',
                'modify': '20210102000000000',
            },
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
        }
        self.assertEqual(book.get_item('item1'), {
            'children': [
                'item2',
            ],
        })

        # meta(-), toc(-)
        book.meta = {}
        book.toc = {}
        self.assertEqual(book.get_item('item1'), None)

    def test_include_parents(self):
        host = Host(self.test_root)
        book = Book(host)

        # meta(+), toc(+)
        book.meta = {
            'item1': {
                'title': 'Item 1',
                'create': '20200101000000000',
                'modify': '20200102000000000',
            },
            'item2': {
                'title': 'Item 2',
                'create': '20210101000000000',
                'modify': '20210102000000000',
            },
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'hidden': [
                'item1',
            ],
        }
        self.assertEqual(book.get_item('item1', include_parents=True), {
            'meta': {
                'title': 'Item 1',
                'create': '20200101000000000',
                'modify': '20200102000000000',
            },
            'children': [
                'item2',
            ],
            'parents': [
                ('root', 0),
                ('root', 2),
                ('hidden', 0),
            ],
        })

        # meta(-), toc(-)
        book.meta = {}
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item1',
            ],
            'hidden': [
                'item1',
            ],
        }
        self.assertEqual(book.get_item('item1', include_parents=True), {
            'parents': [
                ('root', 0),
                ('root', 2),
                ('hidden', 0),
            ],
        })


class TestGetItems(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)

        book.meta = {
            'item1': {
                'title': 'Item 1',
                'create': '20200101000000000',
                'modify': '20200102000000000',
            },
            'item2': {
                'title': 'Item 2',
                'create': '20210101000000000',
                'modify': '20210102000000000',
            },
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
        }
        self.assertEqual(book.get_items(['root', 'item1', 'item2']), {
            'root': {
                'children': [
                    'item1',
                ],
            },
            'item1': {
                'meta': {
                    'title': 'Item 1',
                    'create': '20200101000000000',
                    'modify': '20200102000000000',
                },
                'children': [
                    'item2',
                ],
            },
            'item2': {
                'meta': {
                    'title': 'Item 2',
                    'create': '20210101000000000',
                    'modify': '20210102000000000',
                },
            },
        })

    def test_include_parents(self):
        host = Host(self.test_root)
        book = Book(host)

        book.meta = {
            'item1': {
                'title': 'Item 1',
                'create': '20200101000000000',
                'modify': '20200102000000000',
            },
            'item2': {
                'title': 'Item 2',
                'create': '20210101000000000',
                'modify': '20210102000000000',
            },
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
        }
        self.assertEqual(book.get_items(['root', 'item1', 'item2'], include_parents=True), {
            'root': {
                'children': [
                    'item1',
                ],
            },
            'item1': {
                'meta': {
                    'title': 'Item 1',
                    'create': '20200101000000000',
                    'modify': '20200102000000000',
                },
                'children': [
                    'item2',
                ],
                'parents': [
                    ('root', 0),
                ],
            },
            'item2': {
                'meta': {
                    'title': 'Item 2',
                    'create': '20210101000000000',
                    'modify': '20210102000000000',
                },
                'parents': [
                    ('item1', 0),
                ],
            },
        })


class TestAddItem(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)

        # generate new ID, create, and modify
        book.meta = {}
        book.toc = {}
        with mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000'):
            self.assertEqual(
                book.add_item(),
                {
                    '20200101000000000': {
                        'create': '20200101000000000',
                        'modify': '20200101000000000',
                    },
                },
            )
        self.assertEqual(book.meta, {
            '20200101000000000': {
                'create': '20200101000000000',
                'modify': '20200101000000000',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

        # use same base timestamp for new ID and create
        book.meta = {
            '20200101000059999': {},
        }
        book.toc = {}
        with mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000059999'):
            self.assertEqual(
                book.add_item(),
                {
                    '20200101000100000': {
                        'create': '20200101000059999',
                        'modify': '20200101000059999',
                    },
                },
            )
        self.assertEqual(book.meta, {
            '20200101000059999': {},
            '20200101000100000': {
                'create': '20200101000059999',
                'modify': '20200101000059999',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000100000',
            ],
        })

        # generate new create and modify
        book.meta = {}
        book.toc = {}
        with mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20210101000000000'):
            self.assertEqual(
                book.add_item({
                    'id': '20200101000000000',
                }),
                {
                    '20200101000000000': {
                        'create': '20210101000000000',
                        'modify': '20210101000000000',
                    },
                },
            )
        self.assertEqual(book.meta, {
            '20200101000000000': {
                'create': '20210101000000000',
                'modify': '20210101000000000',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

        # generate new modify from create
        book.meta = {}
        book.toc = {}
        self.assertEqual(
            book.add_item({
                'id': '20200101000000000',
                'create': '20220101000000000',
            }),
            {
                '20200101000000000': {
                    'create': '20220101000000000',
                    'modify': '20220101000000000',
                },
            },
        )
        self.assertEqual(book.meta, {
            '20200101000000000': {
                'create': '20220101000000000',
                'modify': '20220101000000000',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

        # generate nothing
        book.meta = {}
        book.toc = {}
        self.assertEqual(
            book.add_item({
                'id': '20200101000000000',
                'create': '20220101000000000',
                'modify': '20220102000000000',
            }),
            {
                '20200101000000000': {
                    'create': '20220101000000000',
                    'modify': '20220102000000000',
                },
            },
        )
        self.assertEqual(book.meta, {
            '20200101000000000': {
                'create': '20220101000000000',
                'modify': '20220102000000000',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })

        # append to target
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
        }
        self.assertEqual(
            book.add_item({
                'id': 'myitemid',
                'create': '20220101000000000',
                'modify': '20220102000000000',
            }, 'item1'),
            {
                'myitemid': {
                    'create': '20220101000000000',
                    'modify': '20220102000000000',
                },
            },
        )
        self.assertEqual(book.meta, {
            'item1': {},
            'myitemid': {
                'create': '20220101000000000',
                'modify': '20220102000000000',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'myitemid',
            ],
        })

        # insert to target and index
        book.meta = {
            'item1': {},
            'item2': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
        }
        self.assertEqual(
            book.add_item({
                'id': 'myitemid',
                'create': '20220101000000000',
                'modify': '20220102000000000',
            }, 'item1', 0),
            {
                'myitemid': {
                    'create': '20220101000000000',
                    'modify': '20220102000000000',
                },
            },
        )
        self.assertEqual(book.meta, {
            'item1': {},
            'item2': {},
            'myitemid': {
                'create': '20220101000000000',
                'modify': '20220102000000000',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'myitemid',
                'item2',
            ],
        })

        # no insert
        book.meta = {}
        book.toc = {}
        self.assertEqual(
            book.add_item({
                'id': 'myitemid',
                'create': '20220101000000000',
                'modify': '20220102000000000',
            }, None),
            {
                'myitemid': {
                    'create': '20220101000000000',
                    'modify': '20220102000000000',
                },
            },
        )
        self.assertEqual(book.meta, {
            'myitemid': {
                'create': '20220101000000000',
                'modify': '20220102000000000',
            },
        })
        self.assertEqual(book.toc, {})

    def test_bad_id_exist(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {}

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.add_item({
                'id': 'item1',
                'create': '20220101000000000',
                'modify': '20220102000000000',
            })
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_id_special(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}
        book.toc = {}

        for item_id in book.SPECIAL_ITEM_ID:
            with self.subTest(item_id=item_id):
                orig_meta = copy.deepcopy(book.meta)
                orig_toc = copy.deepcopy(book.toc)
                with self.assertRaises(ValueError):
                    book.add_item({
                        'id': item_id,
                        'create': '20220101000000000',
                        'modify': '20220102000000000',
                    })
                self.assertEqual(book.meta, orig_meta)
                self.assertEqual(book.toc, orig_toc)

    def test_bad_target_index_negative(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.add_item(None, 'root', -1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_target_parent_nonexist(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}
        book.toc = {}

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.add_item(None, 'nonexist')
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)


class TestAddItems(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}
        book.toc = {}
        self.assertEqual(
            book.add_items([
                {
                    'id': 'item1',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                },
                {
                    'id': 'item2',
                    'create': '20200102000000000',
                    'modify': '20200102000000000',
                },
            ]),
            {
                'item1': {
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                },
                'item2': {
                    'create': '20200102000000000',
                    'modify': '20200102000000000',
                },
            },
        )
        self.assertEqual(book.meta, {
            'item1': {
                'create': '20200101000000000',
                'modify': '20200101000000000',
            },
            'item2': {
                'create': '20200102000000000',
                'modify': '20200102000000000',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
            ],
        })

    def test_bad_id_duplicated(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}
        book.toc = {}

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.add_items([
                {
                    'id': 'item1',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                },
                {
                    'id': 'item1',
                    'create': '20200102000000000',
                    'modify': '20200102000000000',
                },
            ])
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)


class TestUpdateItem(TestBook):
    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        case_meta = {
            'item1': {
                'title': 'My Item 1',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102000000000',
                'index': 'item1/index.html',
                'source': 'http://example.com',
            },
        }
        case_toc = {
            'root': [
                'item1',
            ],
        }

        # auto update modify
        book.meta = copy.deepcopy(case_meta)
        book.toc = copy.deepcopy(case_toc)
        self.assertEqual(
            book.update_item({
                'id': 'item1',
                'title': 'My New Title',
                'type': '',
                'create': '20210101000000000',
                'modify': '20210102000000000',
                'index': 'item1.htz',
                'source': 'https://example.com',
            }),
            {
                'item1': {
                    'title': 'My New Title',
                    'type': '',
                    'create': '20210101000000000',
                    'modify': '20230101000000000',
                    'index': 'item1.htz',
                    'source': 'https://example.com',
                },
            },
        )
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My New Title',
                'type': '',
                'create': '20210101000000000',
                'modify': '20230101000000000',
                'index': 'item1.htz',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, case_toc)

        # no auto update modify
        book.meta = copy.deepcopy(case_meta)
        book.toc = copy.deepcopy(case_toc)
        self.assertEqual(
            book.update_item({
                'id': 'item1',
                'title': 'My New Title',
                'type': '',
                'create': '20210101000000000',
                'modify': '20210102000000000',
                'index': 'item1.htz',
                'source': 'https://example.com',
            }, auto_modify=False),
            {
                'item1': {
                    'title': 'My New Title',
                    'type': '',
                    'create': '20210101000000000',
                    'modify': '20210102000000000',
                    'index': 'item1.htz',
                    'source': 'https://example.com',
                },
            },
        )
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My New Title',
                'type': '',
                'create': '20210101000000000',
                'modify': '20210102000000000',
                'index': 'item1.htz',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, case_toc)

    def test_bad_id_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {}

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.update_item({
                'title': 'My New Title',
                'type': '',
                'create': '20210101000000000',
                'modify': '20210102000000000',
                'index': 'item1.htz',
                'source': 'https://example.com',
            })
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_meta_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}
        book.toc = {}

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.update_item({
                'id': 'item1',
                'title': 'My New Title',
                'type': '',
                'create': '20210101000000000',
                'modify': '20210102000000000',
                'index': 'item1.htz',
                'source': 'https://example.com',
            })
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)


class TestUpdateItems(TestBook):
    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        case_meta = {
            'item1': {
                'title': 'My Item 1',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102000000000',
                'index': 'item1/index.html',
                'source': 'http://example.com',
            },
            'item2': {
                'title': 'My Item 2',
                'type': '',
                'create': '20200201000000000',
                'modify': '20200202000000000',
                'index': 'item2.htz',
                'source': 'http://example.com/page2',
            },
        }
        case_toc = {
            'root': [
                'item1',
                'item2',
            ],
        }

        # auto update modify
        book.meta = copy.deepcopy(case_meta)
        book.toc = copy.deepcopy(case_toc)
        self.assertEqual(
            book.update_items([
                {
                    'id': 'item1',
                    'title': 'My New Title',
                    'type': '',
                    'create': '20210101000000000',
                    'modify': '20210102000000000',
                    'index': 'item1.htz',
                    'source': 'https://example.com',
                },
                {
                    'id': 'item2',
                    'title': 'My New Title 2',
                    'type': '',
                    'create': '20220201000000000',
                    'modify': '20220202000000000',
                    'index': 'item2.htz',
                    'source': 'https://example.com/page2',
                },
            ]),
            {
                'item1': {
                    'title': 'My New Title',
                    'type': '',
                    'create': '20210101000000000',
                    'modify': '20230101000000000',
                    'index': 'item1.htz',
                    'source': 'https://example.com',
                },
                'item2': {
                    'title': 'My New Title 2',
                    'type': '',
                    'create': '20220201000000000',
                    'modify': '20230101000000000',
                    'index': 'item2.htz',
                    'source': 'https://example.com/page2',
                },
            },
        )
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My New Title',
                'type': '',
                'create': '20210101000000000',
                'modify': '20230101000000000',
                'index': 'item1.htz',
                'source': 'https://example.com',
            },
            'item2': {
                'title': 'My New Title 2',
                'type': '',
                'create': '20220201000000000',
                'modify': '20230101000000000',
                'index': 'item2.htz',
                'source': 'https://example.com/page2',
            },
        })
        self.assertEqual(book.toc, case_toc)

        # no auto update modify
        book.meta = copy.deepcopy(case_meta)
        book.toc = copy.deepcopy(case_toc)
        self.assertEqual(
            book.update_items([
                {
                    'id': 'item1',
                    'title': 'My New Title',
                    'type': '',
                    'create': '20210101000000000',
                    'modify': '20210102000000000',
                    'index': 'item1.htz',
                    'source': 'https://example.com',
                },
                {
                    'id': 'item2',
                    'title': 'My New Title 2',
                    'type': '',
                    'create': '20220201000000000',
                    'modify': '20220202000000000',
                    'index': 'item2.htz',
                    'source': 'https://example.com/page2',
                },
            ], auto_modify=False),
            {
                'item1': {
                    'title': 'My New Title',
                    'type': '',
                    'create': '20210101000000000',
                    'modify': '20210102000000000',
                    'index': 'item1.htz',
                    'source': 'https://example.com',
                },
                'item2': {
                    'title': 'My New Title 2',
                    'type': '',
                    'create': '20220201000000000',
                    'modify': '20220202000000000',
                    'index': 'item2.htz',
                    'source': 'https://example.com/page2',
                },
            },
        )
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My New Title',
                'type': '',
                'create': '20210101000000000',
                'modify': '20210102000000000',
                'index': 'item1.htz',
                'source': 'https://example.com',
            },
            'item2': {
                'title': 'My New Title 2',
                'type': '',
                'create': '20220201000000000',
                'modify': '20220202000000000',
                'index': 'item2.htz',
                'source': 'https://example.com/page2',
            },
        })
        self.assertEqual(book.toc, case_toc)

    def test_timestamp(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }
        book.update_items([
            {
                'id': 'item1',
                'title': 'My New Title',
            },
            {
                'id': 'item2',
                'title': 'My New Title 2',
            },
            {
                'id': 'item3',
                'title': 'My New Title 3',
            },
        ])
        self.assertAlmostEqual(
            int(book.meta['item1']['modify'], 10),
            int(util.datetime_to_id(), 10),
            delta=30,
        )
        self.assertEqual(book.meta['item1']['modify'], book.meta['item2']['modify'])
        self.assertEqual(book.meta['item1']['modify'], book.meta['item3']['modify'])


class TestMoveItem(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item1-1': {},
            'item1-2': {},
            'item2-1': {},
            'item2-2': {},
        }
        case = {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('folder1', 0, 'folder2', 0), 0)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-2',
            ],
            'folder2': [
                'item1-1',
                'item2-1',
                'item2-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('folder1', 0, 'folder2', 1), 1)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item1-1',
                'item2-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('folder1', 0, 'folder2', 2), 2)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('folder1', 0, 'folder2', 3), 2)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('folder1', 0, 'folder2', None), 2)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
            ],
        })

    def test_same_parent(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
            'item4': {},
        }
        case = {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 1, 'root', 0), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item1',
                'item3',
                'item4',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 1, 'root', 1), 1)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 1, 'root', 2), 1)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 1, 'root', 3), 2)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item3',
                'item2',
                'item4',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 1, 'root', 4), 3)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item3',
                'item4',
                'item2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 1, 'root', 5), 3)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item3',
                'item4',
                'item2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 1, 'root', None), 3)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item3',
                'item4',
                'item2',
            ],
        })

    def test_special(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
            ],
            'hidden': [
                'item3',
            ],
        }

        self.assertEqual(book.move_item('root', 0, 'hidden', None), 1)
        self.assertEqual(book.toc, {
            'root': [
                'item2',
            ],
            'hidden': [
                'item3',
                'item1',
            ],
        })

    def test_multi(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item1-1': {},
            'item1-2': {},
            'item2-1': {},
            'item2-2': {},
        }
        book.toc = {
            'root': [
                'folder1',
                'folder2',
                'item1-1',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
                'item1-1',
            ],
            'folder2': [
                'item1-1',
                'item2-1',
                'item2-2',
            ],
        }

        self.assertEqual(book.move_item('folder1', 2, 'folder2', None), 3)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
                'item1-1',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item1-1',
                'item2-1',
                'item2-2',
                'item1-1',
            ],
        })

    def test_target_no_toc(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        case = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 0, 'item2', 0), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item3',
            ],
            'item2': [
                'item1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 0, 'item2', 1), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item3',
            ],
            'item2': [
                'item1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.move_item('root', 0, 'item2', None), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item3',
            ],
            'item2': [
                'item1',
            ],
        })

    def test_bad_current_parent_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.move_item('nonexist', 0, 'root', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_out_of_range(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.move_item('root', 3, 'root', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_negative(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.move_item('root', -1, 'root', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_target_index_negative(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.move_item('root', 0, 'root', -1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_target_parent_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.move_item('root', 0, 'nonexist', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_to_descendant(self):
        """Silently fail when moving into a descendant"""
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        self.assertEqual(book.move_item('root', 0, 'item1', None), 1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        self.assertEqual(book.move_item('root', 0, 'item2', None), 1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        self.assertEqual(book.move_item('root', 0, 'item3', None), 0)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_to_descendant_circular(self):
        """Silently fail when moving into a descendant"""
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
            'item4': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item4',
            ],
            'item4': [
                'item1',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        self.assertEqual(book.move_item('item2', 0, 'item1', None), 1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_to_same_parent_circular(self):
        """Allow moving into the same parent if parent is a descendant (circularly)."""
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
            'item3-1': {},
            'item3-2': {},
            'item4': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3-1',
                'item3',
                'item3-2',
            ],
            'item3': [
                'item4',
            ],
            'item4': [
                'item1',
            ],
        }

        self.assertEqual(book.move_item('item2', 1, 'item2', 3), 2)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3-1',
                'item3-2',
                'item3',
            ],
            'item3': [
                'item4',
            ],
            'item4': [
                'item1',
            ],
        })


class TestMoveItems(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item1-1': {},
            'item1-2': {},
            'item2-1': {},
            'item2-2': {},
        }
        case = {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', 0),
            0,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder2': [
                'item1-1',
                'item1-2',
                'item2-1',
                'item2-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', 1),
            1,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder2': [
                'item2-1',
                'item1-1',
                'item1-2',
                'item2-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', 2),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
                'item1-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', 3),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
                'item1-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', None),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
                'item1-2',
            ],
        })

    def test_same_parent(self):
        """Moving multiple items within the same parent needs special care, as
        the index of siblings will changed when each item is moved.
        """
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
            'item4': {},
            'item5': {},
            'item6': {},
        }
        case = {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
                'item5',
                'item6',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('root', 3),
                ('root', 4),
                ('root', 5),
            ], 'root', 1),
            1,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item4',
                'item5',
                'item6',
                'item2',
                'item3',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('root', 0),
                ('root', 1),
                ('root', 2),
            ], 'root', 5),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item4',
                'item5',
                'item1',
                'item2',
                'item3',
                'item6',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('root', 1),
                ('root', 3),
                ('root', 5),
            ], 'root', 0),
            0,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item4',
                'item6',
                'item1',
                'item3',
                'item5',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('root', 0),
                ('root', 2),
                ('root', 4),
            ], 'root', 5),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item4',
                'item1',
                'item3',
                'item5',
                'item6',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('root', 1),
                ('root', 3),
                ('root', 5),
            ], 'root', 4),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item3',
                'item2',
                'item4',
                'item6',
                'item5',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('root', 0),
                ('root', 2),
                ('root', 4),
            ], 'root', 1),
            0,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item3',
                'item5',
                'item2',
                'item4',
                'item6',
            ],
        })

    def test_parent_with_child(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item1-1': {},
            'item1-1-1': {},
            'item1-1-2': {},
            'item1-2': {},
            'item2-1': {},
            'item2-2': {},
        }
        book.toc = {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
            ],
            'item1-1': [
                'item1-1-1',
                'item1-1-2',
            ],
        }

        self.assertEqual(
            book.move_items([
                ('folder1', 0),
                ('item1-1', 0),
                ('item1-1', 1),
            ], 'folder2', None),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
                'item1-1-1',
                'item1-1-2',
            ],
        })

    def test_duplicated_items(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        case = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item1',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('item1', 0),
                ('item2', 0),
                ('item3', 0),
                ('item1', 0),
            ], 'hidden', None),
            0,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'hidden': [
                'item2',
                'item3',
                'item1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.move_items([
                ('root', 0),
                ('item1', 0),
                ('item2', 0),
                ('item3', 0),
                ('item1', 0),
            ], 'hidden', None),
            0,
        )
        self.assertEqual(book.toc, {
            'hidden': [
                'item1',
                'item2',
                'item3',
                'item1',
            ],
        })

    def test_partial_circular(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
            'item4': {},
            'item5': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item4',
            ],
            'item4': [
                'item5',
            ],
        }

        self.assertEqual(
            book.move_items([
                ('root', 0),
                ('item1', 0),
                ('item2', 0),
                ('item3', 0),
                ('item4', 0),
            ], 'item2', None),
            0,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
                'item4',
                'item5',
            ],
        })


class TestLinkItem(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item1-1': {},
            'item1-2': {},
            'item2-1': {},
            'item2-2': {},
        }
        case = {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('folder1', 0, 'folder2', 0), 0)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item1-1',
                'item2-1',
                'item2-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('folder1', 0, 'folder2', 1), 1)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item1-1',
                'item2-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('folder1', 0, 'folder2', 2), 2)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('folder1', 0, 'folder2', 3), 2)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('folder1', 0, 'folder2', None), 2)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
            ],
        })

    def test_special(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        case = {
            'root': [
                'item1',
                'item2',
            ],
            'hidden': [
                'item3',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('root', 0, 'hidden', None), 1)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
            ],
            'hidden': [
                'item3',
                'item1',
            ],
        })

    def test_multi(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item1-1': {},
            'item1-2': {},
            'item2-1': {},
            'item2-2': {},
        }
        case = {
            'root': [
                'folder1',
                'folder2',
                'item1-1',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
                'item1-1',
            ],
            'folder2': [
                'item1-1',
                'item2-1',
                'item2-2',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('folder1', 2, 'folder2', None), 3)
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
                'item1-1',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
                'item1-1',
            ],
            'folder2': [
                'item1-1',
                'item2-1',
                'item2-2',
                'item1-1',
            ],
        })

    def test_target_no_toc(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        case = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('root', 0, 'item2', 0), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
            'item2': [
                'item1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('root', 0, 'item2', 1), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
            'item2': [
                'item1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(book.link_item('root', 0, 'item2', None), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
            'item2': [
                'item1',
            ],
        })

    def test_bad_current_parent_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.link_item('nonexist', 0, 'root', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_out_of_range(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.link_item('root', 3, 'root', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_negative(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.link_item('root', -1, 'root', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_target_index_negative(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.link_item('root', 0, 'root', -1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_target_parent_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.link_item('root', 0, 'nonexist', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)


class TestLinkItems(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item1-1': {},
            'item1-2': {},
            'item2-1': {},
            'item2-2': {},
        }
        case = {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.link_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', 0),
            0,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item1-1',
                'item1-2',
                'item2-1',
                'item2-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.link_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', 1),
            1,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item1-1',
                'item1-2',
                'item2-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.link_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', 2),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
                'item1-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.link_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', 3),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
                'item1-2',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.link_items([
                ('folder1', 0),
                ('folder1', 1),
            ], 'folder2', None),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
                'item1-2',
            ],
        })

    def test_parent_with_child(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item1-1': {},
            'item1-1-1': {},
            'item1-1-2': {},
            'item1-2': {},
            'item2-1': {},
            'item2-2': {},
        }
        case = {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
            ],
            'item1-1': [
                'item1-1-1',
                'item1-1-2',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.link_items([
                ('folder1', 0),
                ('item1-1', 0),
                ('item1-1', 1),
            ], 'folder2', None),
            2,
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'folder1': [
                'item1-1',
                'item1-2',
            ],
            'folder2': [
                'item2-1',
                'item2-2',
                'item1-1',
                'item1-1-1',
                'item1-1-2',
            ],
            'item1-1': [
                'item1-1-1',
                'item1-1-2',
            ],
        })

    def test_duplicated_items(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        case = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item1',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.link_items([
                ('item1', 0),
                ('item2', 0),
                ('item3', 0),
                ('item1', 0),
            ], 'hidden', None),
            0,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item1',
            ],
            'hidden': [
                'item2',
                'item3',
                'item1',
            ],
        })

        book.toc = copy.deepcopy(case)
        self.assertEqual(
            book.link_items([
                ('root', 0),
                ('item1', 0),
                ('item2', 0),
                ('item3', 0),
                ('item1', 0),
            ], 'hidden', None),
            0,
        )
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item1',
            ],
            'hidden': [
                'item1',
                'item2',
                'item3',
                'item1',
            ],
        })


class TestCopyItemBase(TestBook):
    def create_general_case(self):
        with open(self.test_config, 'w', encoding='UTF-8') as fh:
            fh.write("""\
[book ""]
name = Scrapbook
top_dir = scrapbook1
data_dir = data
tree_dir = tree
no_tree = false

[book "book2"]
name = Scrapbook 2
top_dir = scrapbook2
data_dir = Data
tree_dir = Tree
no_tree = false

[book "book3"]
name = Scrapbook 3
top_dir = scrapbook3
data_dir = data
tree_dir = tree
no_tree = true
""")

        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
        }
        util.fs.save(os.path.join(book.data_dir, 'item1', 'index.html'), b'dummy')
        util.fs.save(os.path.join(book.data_dir, 'item1', 'favicon.ico'), b'icon')
        util.fs.save(os.path.join(book.data_dir, 'item1-1.htz'), b'dummy1')
        util.fs.save(os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'), b'icon1')
        util.fs.save(os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'), b'icon11')
        util.fs.save(os.path.join(book.data_dir, 'item1-2.maff'), b'dummy2')
        util.fs.save(os.path.join(book.data_dir, 'item1-3.html'), b'dummy3')

        book2 = host.books['book2']
        book2.meta = {}
        book2.toc = {}

        return SimpleNamespace(**locals())


class TestCopyItem(TestCopyItemBase):
    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_basic_non_recursive(self):
        case = self.create_general_case()
        book = case.book

        self.assertEqual(book.copy_item('root', 0, 'hidden', None, recursively=False), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'hidden': [
                '20200101000000000',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
            '20200101000000000': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.ico',
            },
        })
        self.assertEqual(glob_files(book.data_dir), {
            os.path.join(book.data_dir, ''),
            os.path.join(book.data_dir, 'item1'),
            os.path.join(book.data_dir, 'item1', 'index.html'),
            os.path.join(book.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book.data_dir, 'item1-1.htz'),
            os.path.join(book.data_dir, 'item1-2.maff'),
            os.path.join(book.data_dir, 'item1-3.html'),
            os.path.join(book.data_dir, '20200101000000000'),
            os.path.join(book.data_dir, '20200101000000000', 'index.html'),
            os.path.join(book.data_dir, '20200101000000000', 'favicon.ico'),
        })
        self.assertEqual(glob_files(book.tree_dir), {
            os.path.join(book.tree_dir, ''),
            os.path.join(book.tree_dir, 'favicon'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })
        with open(os.path.join(book.data_dir, '20200101000000000', 'index.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy')
        with open(os.path.join(book.data_dir, '20200101000000000', 'favicon.ico'), 'rb') as fh:
            self.assertEqual(fh.read(), b'icon')

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_basic_recursive(self):
        case = self.create_general_case()
        book = case.book

        self.assertEqual(book.copy_item('root', 0, 'hidden', None), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'hidden': [
                '20200101000000000',
            ],
            '20200101000000000': [
                '20200101000000001',
                '20200101000000003',
                '20200101000000004',
            ],
            '20200101000000001': [
                '20200101000000002',
            ],
            '20200101000000003': [
                '20200101000000000',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
            '20200101000000000': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.ico',
            },
            '20200101000000001': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': '20200101000000001.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            '20200101000000002': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            '20200101000000003': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': '20200101000000003.maff',
                'icon': '',
            },
            '20200101000000004': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': '20200101000000004.html',
            },
        })
        self.assertEqual(glob_files(book.data_dir), {
            os.path.join(book.data_dir, ''),
            os.path.join(book.data_dir, 'item1'),
            os.path.join(book.data_dir, 'item1', 'index.html'),
            os.path.join(book.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book.data_dir, 'item1-1.htz'),
            os.path.join(book.data_dir, 'item1-2.maff'),
            os.path.join(book.data_dir, 'item1-3.html'),
            os.path.join(book.data_dir, '20200101000000000'),
            os.path.join(book.data_dir, '20200101000000000', 'index.html'),
            os.path.join(book.data_dir, '20200101000000000', 'favicon.ico'),
            os.path.join(book.data_dir, '20200101000000001.htz'),
            os.path.join(book.data_dir, '20200101000000003.maff'),
            os.path.join(book.data_dir, '20200101000000004.html'),
        })
        self.assertEqual(glob_files(book.tree_dir), {
            os.path.join(book.tree_dir, ''),
            os.path.join(book.tree_dir, 'favicon'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })
        with open(os.path.join(book.data_dir, '20200101000000000', 'index.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy')
        with open(os.path.join(book.data_dir, '20200101000000000', 'favicon.ico'), 'rb') as fh:
            self.assertEqual(fh.read(), b'icon')
        with open(os.path.join(book.data_dir, '20200101000000001.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy1')
        with open(os.path.join(book.data_dir, '20200101000000003.maff'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy2')
        with open(os.path.join(book.data_dir, '20200101000000004.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy3')

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_basic_cross_book_non_recursive(self):
        case = self.create_general_case()
        book = case.book
        book2 = case.host.books['book2']

        self.assertEqual(book.copy_item('root', 0, 'hidden', None, target_book_id='book2', recursively=False), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
        })
        self.assertEqual(glob_files(book.data_dir), {
            os.path.join(book.data_dir, ''),
            os.path.join(book.data_dir, 'item1'),
            os.path.join(book.data_dir, 'item1', 'index.html'),
            os.path.join(book.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book.data_dir, 'item1-1.htz'),
            os.path.join(book.data_dir, 'item1-2.maff'),
            os.path.join(book.data_dir, 'item1-3.html'),
        })
        self.assertEqual(glob_files(book.tree_dir), {
            os.path.join(book.tree_dir, ''),
            os.path.join(book.tree_dir, 'favicon'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })
        self.assertEqual(book2.toc, {
            'hidden': [
                'item1',
            ],
        })
        self.assertEqual(book2.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
        })
        self.assertEqual(glob_files(book2.data_dir), {
            os.path.join(book2.data_dir, ''),
            os.path.join(book2.data_dir, 'item1'),
            os.path.join(book2.data_dir, 'item1', 'index.html'),
            os.path.join(book2.data_dir, 'item1', 'favicon.ico'),
        })
        self.assertEqual(glob_files(book2.tree_dir), {
            os.path.join(book2.tree_dir, ''),
        })
        with open(os.path.join(book2.data_dir, 'item1', 'index.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy')
        with open(os.path.join(book2.data_dir, 'item1', 'favicon.ico'), 'rb') as fh:
            self.assertEqual(fh.read(), b'icon')

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_basic_cross_book_recursive(self):
        case = self.create_general_case()
        book = case.book
        book2 = case.host.books['book2']

        self.assertEqual(book.copy_item('root', 0, 'hidden', None, target_book_id='book2'), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
        })
        self.assertEqual(glob_files(book.data_dir), {
            os.path.join(book.data_dir, ''),
            os.path.join(book.data_dir, 'item1'),
            os.path.join(book.data_dir, 'item1', 'index.html'),
            os.path.join(book.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book.data_dir, 'item1-1.htz'),
            os.path.join(book.data_dir, 'item1-2.maff'),
            os.path.join(book.data_dir, 'item1-3.html'),
        })
        self.assertEqual(glob_files(book.tree_dir), {
            os.path.join(book.tree_dir, ''),
            os.path.join(book.tree_dir, 'favicon'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })
        self.assertEqual(book2.toc, {
            'hidden': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
        })
        self.assertEqual(book2.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../Tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../Tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
        })
        self.assertEqual(glob_files(book2.data_dir), {
            os.path.join(book2.data_dir, ''),
            os.path.join(book2.data_dir, 'item1'),
            os.path.join(book2.data_dir, 'item1', 'index.html'),
            os.path.join(book2.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book2.data_dir, 'item1-1.htz'),
            os.path.join(book2.data_dir, 'item1-2.maff'),
            os.path.join(book2.data_dir, 'item1-3.html'),
        })
        self.assertEqual(glob_files(book2.tree_dir), {
            os.path.join(book2.tree_dir, ''),
            os.path.join(book2.tree_dir, 'favicon'),
            os.path.join(book2.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book2.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })
        with open(os.path.join(book2.data_dir, 'item1', 'index.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy')
        with open(os.path.join(book2.data_dir, 'item1', 'favicon.ico'), 'rb') as fh:
            self.assertEqual(fh.read(), b'icon')
        with open(os.path.join(book2.data_dir, 'item1-1.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy1')
        with open(os.path.join(book2.data_dir, 'item1-2.maff'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy2')
        with open(os.path.join(book2.data_dir, 'item1-3.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy3')
        with open(os.path.join(book2.tree_dir, 'favicon', 'b64favicon#1.ico'), 'rb') as fh:
            self.assertEqual(fh.read(), b'icon1')
        with open(os.path.join(book2.tree_dir, 'favicon', 'b64favicon%11.ico'), 'rb') as fh:
            self.assertEqual(fh.read(), b'icon11')

    def test_bad_current_parent_missing(self):
        case = self.create_general_case()
        book = case.book

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.copy_item('nonexist', 0, 'hidden', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_out_of_range(self):
        case = self.create_general_case()
        book = case.book

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.copy_item('root', 10, 'hidden', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_negative(self):
        case = self.create_general_case()
        book = case.book

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.copy_item('root', -1, 'hidden', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_meta_missing(self):
        case = self.create_general_case()
        book = case.book
        del book.meta['item1']

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.copy_item('root', 0, 'hidden', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_target_index_negative(self):
        case = self.create_general_case()
        book = case.book

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.copy_item('root', 0, 'hidden', -1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_target_parent_missing(self):
        case = self.create_general_case()
        book = case.book

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.copy_item('root', 0, 'nonexist', None)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_target_book_missing(self):
        case = self.create_general_case()
        book = case.book

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.copy_item('root', 0, 'hidden', None, target_book_id='nonexist')
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_to_descendant(self):
        """Silently fail when copying into a descendant recursively."""
        case = self.create_general_case()
        book = case.book

        self.assertEqual(book.copy_item('root', 0, 'item1-3', None), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'item1-3': [
                '20200101000000000',
            ],
            '20200101000000000': [
                '20200101000000001',
                '20200101000000003',
                '20200101000000004',
            ],
            '20200101000000001': [
                '20200101000000002',
            ],
            '20200101000000003': [
                '20200101000000000',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
            '20200101000000000': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.ico',
            },
            '20200101000000001': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': '20200101000000001.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            '20200101000000002': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            '20200101000000003': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': '20200101000000003.maff',
                'icon': '',
            },
            '20200101000000004': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': '20200101000000004.html',
            },
        })


class TestCopyItems(TestCopyItemBase):
    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_basic_non_recursive(self):
        case = self.create_general_case()
        book = case.book

        self.assertEqual(book.copy_items([
            ['item1', 0],
            ['item1', 1],
            ['item1', 2],
        ], 'hidden', None, recursively=False), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'hidden': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
            '20200101000000000': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': '20200101000000000.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            '20200101000000001': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': '20200101000000001.maff',
                'icon': '',
            },
            '20200101000000002': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': '20200101000000002.html',
            },
        })
        self.assertEqual(glob_files(book.data_dir), {
            os.path.join(book.data_dir, ''),
            os.path.join(book.data_dir, 'item1'),
            os.path.join(book.data_dir, 'item1', 'index.html'),
            os.path.join(book.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book.data_dir, 'item1-1.htz'),
            os.path.join(book.data_dir, 'item1-2.maff'),
            os.path.join(book.data_dir, 'item1-3.html'),
            os.path.join(book.data_dir, '20200101000000000.htz'),
            os.path.join(book.data_dir, '20200101000000001.maff'),
            os.path.join(book.data_dir, '20200101000000002.html'),
        })
        self.assertEqual(glob_files(book.tree_dir), {
            os.path.join(book.tree_dir, ''),
            os.path.join(book.tree_dir, 'favicon'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })
        with open(os.path.join(book.data_dir, '20200101000000000.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy1')
        with open(os.path.join(book.data_dir, '20200101000000001.maff'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy2')
        with open(os.path.join(book.data_dir, '20200101000000002.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy3')

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_basic_recursive(self):
        case = self.create_general_case()
        book = case.book

        self.assertEqual(book.copy_items([
            ['item1', 0],
            ['item1', 1],
            ['item1', 2],
        ], 'hidden', None), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'hidden': [
                '20200101000000000',
                '20200101000000002',
                '20200101000000004',
            ],
            '20200101000000000': [
                '20200101000000001',
            ],
            '20200101000000002': [
                '20200101000000003',
            ],
            '20200101000000003': [
                '20200101000000000',
                '20200101000000002',
                '20200101000000004',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
            '20200101000000000': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': '20200101000000000.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            '20200101000000001': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            '20200101000000002': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': '20200101000000002.maff',
                'icon': '',
            },
            '20200101000000003': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': '20200101000000003/index.html',
                'icon': 'favicon.ico',
            },
            '20200101000000004': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': '20200101000000004.html',
            },
        })
        self.assertEqual(glob_files(book.data_dir), {
            os.path.join(book.data_dir, ''),
            os.path.join(book.data_dir, 'item1'),
            os.path.join(book.data_dir, 'item1', 'index.html'),
            os.path.join(book.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book.data_dir, 'item1-1.htz'),
            os.path.join(book.data_dir, 'item1-2.maff'),
            os.path.join(book.data_dir, 'item1-3.html'),
            os.path.join(book.data_dir, '20200101000000000.htz'),
            os.path.join(book.data_dir, '20200101000000002.maff'),
            os.path.join(book.data_dir, '20200101000000003'),
            os.path.join(book.data_dir, '20200101000000003', 'index.html'),
            os.path.join(book.data_dir, '20200101000000003', 'favicon.ico'),
            os.path.join(book.data_dir, '20200101000000004.html'),
        })
        self.assertEqual(glob_files(book.tree_dir), {
            os.path.join(book.tree_dir, ''),
            os.path.join(book.tree_dir, 'favicon'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })
        with open(os.path.join(book.data_dir, '20200101000000000.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy1')
        with open(os.path.join(book.data_dir, '20200101000000002.maff'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy2')
        with open(os.path.join(book.data_dir, '20200101000000003', 'index.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy')
        with open(os.path.join(book.data_dir, '20200101000000003', 'favicon.ico'), 'rb') as fh:
            self.assertEqual(fh.read(), b'icon')
        with open(os.path.join(book.data_dir, '20200101000000004.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy3')

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_parent_with_child(self):
        case = self.create_general_case()
        book = case.book

        self.assertEqual(book.copy_items([
            ['root', 0],
            ['item1', 0],
            ['item1-1', 0],
        ], 'hidden', None), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'hidden': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
            ],
            '20200101000000000': [
                '20200101000000001',
                '20200101000000003',
                '20200101000000004',
            ],
            '20200101000000001': [
                '20200101000000002',
            ],
            '20200101000000003': [
                '20200101000000000',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
            '20200101000000000': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.ico',
            },
            '20200101000000001': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': '20200101000000001.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            '20200101000000002': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            '20200101000000003': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': '20200101000000003.maff',
                'icon': '',
            },
            '20200101000000004': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': '20200101000000004.html',
            },
        })
        self.assertEqual(glob_files(book.data_dir), {
            os.path.join(book.data_dir, ''),
            os.path.join(book.data_dir, 'item1'),
            os.path.join(book.data_dir, 'item1', 'index.html'),
            os.path.join(book.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book.data_dir, 'item1-1.htz'),
            os.path.join(book.data_dir, 'item1-2.maff'),
            os.path.join(book.data_dir, 'item1-3.html'),
            os.path.join(book.data_dir, '20200101000000000'),
            os.path.join(book.data_dir, '20200101000000000', 'index.html'),
            os.path.join(book.data_dir, '20200101000000000', 'favicon.ico'),
            os.path.join(book.data_dir, '20200101000000001.htz'),
            os.path.join(book.data_dir, '20200101000000003.maff'),
            os.path.join(book.data_dir, '20200101000000004.html'),
        })
        self.assertEqual(glob_files(book.tree_dir), {
            os.path.join(book.tree_dir, ''),
            os.path.join(book.tree_dir, 'favicon'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })
        with open(os.path.join(book.data_dir, '20200101000000000', 'index.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy')
        with open(os.path.join(book.data_dir, '20200101000000000', 'favicon.ico'), 'rb') as fh:
            self.assertEqual(fh.read(), b'icon')
        with open(os.path.join(book.data_dir, '20200101000000001.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy1')
        with open(os.path.join(book.data_dir, '20200101000000003.maff'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy2')
        with open(os.path.join(book.data_dir, '20200101000000004.html'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy3')

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_duplicated_items(self):
        case = self.create_general_case()
        book = case.book

        self.assertEqual(book.copy_items([
            ['item1', 1],
            ['item1-2', 0],
            ['item1', 0],
            ['item1', 1],
        ], 'hidden', None, recursively=False), 0)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'hidden': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': 'item1/index.html',
                'icon': 'favicon.ico',
            },
            'item1-1': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': 'item1-1.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
            'item1-1-1': {
                'title': 'My Item 1-1-1',
                'create': '20000103000000000',
                'modify': '20010103000000000',
                'type': 'bookmark',
                'icon': '../tree/favicon/b64favicon%2511.ico',
            },
            'item1-2': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': 'item1-2.maff',
                'icon': '',
            },
            'item1-3': {
                'title': 'My Item 1-3',
                'create': '20000105000000000',
                'modify': '20010105000000000',
                'index': 'item1-3.html',
            },
            '20200101000000000': {
                'title': 'My Item 1-2',
                'create': '20000104000000000',
                'modify': '20010104000000000',
                'index': '20200101000000000.maff',
                'icon': '',
            },
            '20200101000000001': {
                'title': 'My Item 1',
                'create': '20000101000000000',
                'modify': '20010101000000000',
                'index': '20200101000000001/index.html',
                'icon': 'favicon.ico',
            },
            '20200101000000002': {
                'title': 'My Item 1-1',
                'create': '20000102000000000',
                'modify': '20010102000000000',
                'index': '20200101000000002.htz',
                'icon': '../tree/favicon/b64favicon%231.ico',
            },
        })
        self.assertEqual(glob_files(book.data_dir), {
            os.path.join(book.data_dir, ''),
            os.path.join(book.data_dir, 'item1'),
            os.path.join(book.data_dir, 'item1', 'index.html'),
            os.path.join(book.data_dir, 'item1', 'favicon.ico'),
            os.path.join(book.data_dir, 'item1-1.htz'),
            os.path.join(book.data_dir, 'item1-2.maff'),
            os.path.join(book.data_dir, 'item1-3.html'),
            os.path.join(book.data_dir, '20200101000000000.maff'),
            os.path.join(book.data_dir, '20200101000000001'),
            os.path.join(book.data_dir, '20200101000000001', 'index.html'),
            os.path.join(book.data_dir, '20200101000000001', 'favicon.ico'),
            os.path.join(book.data_dir, '20200101000000002.htz'),
        })
        self.assertEqual(glob_files(book.tree_dir), {
            os.path.join(book.tree_dir, ''),
            os.path.join(book.tree_dir, 'favicon'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon#1.ico'),
            os.path.join(book.tree_dir, 'favicon', 'b64favicon%11.ico'),
        })


class TestRecycleItem(TestBook):
    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
            ],
        }

        self.assertCountEqual(book.recycle_item('root', 0), {'item1'})
        self.assertEqual(book.toc, {
            'root': [
                'item2',
            ],
            'recycle': [
                'item1',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'parent': 'root',
                'recycled': '20200101000000000',
            },
            'item2': {},
        })

    def test_multi(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item1',
            ],
        }

        self.assertCountEqual(book.recycle_item('root', 0), set())
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item1',
            ],
        })
        self.assertEqual(book.meta['item1'], {})

    def test_bad_current_parent_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.recycle_item('nonexist', 0)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_out_of_range(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.recycle_item('root', 3)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_negative(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.recycle_item('root', -1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_meta_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.recycle_item('root', 0)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)


class TestRecycleItems(TestBook):
    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
        }
        book.toc = {
            'root': [
                'item1',
                'item2',
            ],
        }

        self.assertCountEqual(
            book.recycle_items([
                ('root', 0),
                ('root', 1),
            ]),
            {
                'item1',
                'item2',
            },
        )
        self.assertEqual(book.toc, {
            'recycle': [
                'item1',
                'item2',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'parent': 'root',
                'recycled': '20200101000000000',
            },
            'item2': {
                'parent': 'root',
                'recycled': '20200101000000000',
            },
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20200101000000000')
    def test_duplicated_items(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item1',
            ],
        }

        self.assertCountEqual(
            book.recycle_items([
                ('root', 0),
                ('item1', 0),
                ('item2', 0),
                ('item3', 0),
                ('item1', 0),
            ]),
            {
                'item1',
                'item2',
                'item3',
            },
        )
        self.assertEqual(book.toc, {
            'recycle': [
                'item1',
                'item2',
                'item3',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {
                'parent': 'root',
                'recycled': '20200101000000000',
            },
            'item2': {
                'parent': 'item1',
                'recycled': '20200101000000000',
            },
            'item3': {
                'parent': 'item2',
                'recycled': '20200101000000000',
            },
        })

    def test_timestamp(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'folder1': {},
            'folder2': {},
            'item0': {},
            'item1': {},
            'item2': {},
        }
        book.toc = {
            'root': [
                'folder1',
                'folder2',
                'item0',
            ],
            'folder1': [
                'item1',
            ],
            'folder2': [
                'item2',
            ],
        }

        self.assertCountEqual(
            book.recycle_items([
                ('root', 2),
                ('folder1', 0),
                ('folder2', 0),
            ]),
            {
                'item0',
                'item1',
                'item2',
            },
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
            ],
            'recycle': [
                'item0',
                'item1',
                'item2',
            ],
        })
        self.assertAlmostEqual(
            int(book.meta['item0']['recycled'], 10),
            int(util.datetime_to_id(), 10),
            delta=30,
        )
        self.assertEqual(book.meta['item0']['recycled'], book.meta['item1']['recycled'])
        self.assertEqual(book.meta['item0']['recycled'], book.meta['item2']['recycled'])


class TestUnrecycleItem(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)

        # unrecycle to parent
        book.meta = {
            'item1': {
                'parent': 'item2',
                'recycled': '20000101000000000',
            },
            'item2': {},
        }
        book.toc = {
            'root': [
                'item2',
            ],
            'recycle': [
                'item1',
            ],
        }
        self.assertEqual(book.unrecycle_item('recycle', 0), {
            'item1': 'item2',
        })
        self.assertEqual(book.toc, {
            'root': [
                'item2',
            ],
            'item2': [
                'item1',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {},
            'item2': {},
        })

        # unrecycle to root if parent no more exists
        book.meta = {
            'item1': {
                'parent': 'item2',
                'recycled': '20000101000000000',
            },
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }
        self.assertEqual(book.unrecycle_item('recycle', 0), {
            'item1': 'root',
        })
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {},
        })

        # unrecycle to root if 'parent' record missing
        book.meta = {
            'item1': {
                'recycled': '20000101000000000',
            },
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }
        self.assertEqual(book.unrecycle_item('recycle', 0), {
            'item1': 'root',
        })
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {},
        })

        # no error if 'parent' and 'recycled' records missing
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }
        self.assertEqual(book.unrecycle_item('recycle', 0), {
            'item1': 'root',
        })
        self.assertEqual(book.toc, {
            'root': [
                'item1',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {},
        })

    def test_bad_current_parent_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.unrecycle_item('nonexist', 0)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_out_of_range(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.unrecycle_item('recycle', 10)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_negative(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.unrecycle_item('recycle', -1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_meta_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}
        book.toc = {
            'recycle': [
                'item1',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.unrecycle_item('recycle', 0)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)


class TestUnrecycleItems(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {
                'parent': 'folder1',
                'recycled': '20000101000000000',
            },
            'item1-1': {},
            'item2': {
                'parent': 'folder2',
                'recycled': '20000102000000000',
            },
            'item3': {
                'parent': 'folder3',
                'recycled': '20000103000000000',
            },
            'folder1': {},
            'folder2': {},
        }
        book.toc = {
            'root': [
                'folder1',
                'folder2',
            ],
            'recycle': [
                'item1',
                'item2',
                'item3',
            ],
            'item1': [
                'item1-1',
            ],
        }

        self.assertEqual(
            book.unrecycle_items([
                ('recycle', 0),
                ('recycle', 1),
                ('recycle', 2),
            ]),
            {
                'item1': 'folder1',
                'item2': 'folder2',
                'item3': 'root',
            }
        )
        self.assertEqual(book.toc, {
            'root': [
                'folder1',
                'folder2',
                'item3',
            ],
            'item1': [
                'item1-1',
            ],
            'folder1': [
                'item1',
            ],
            'folder2': [
                'item2',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {},
            'item1-1': {},
            'item2': {},
            'item3': {},
            'folder1': {},
            'folder2': {},
        })

    def test_multi(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {
                'parent': 'folder1',
                'recycled': '20000101000000000',
            },
            'item2': {
                'parent': 'folder2',
                'recycled': '20000102000000000',
            },
            'item3': {
                'parent': 'folder3',
                'recycled': '20000103000000000',
            },
        }
        book.toc = {
            'recycle': [
                'item1',
                'item2',
                'item3',
                'item1',
            ],
        }

        self.assertEqual(
            book.unrecycle_items([
                ('recycle', 0),
                ('recycle', 1),
                ('recycle', 2),
                ('recycle', 3),
            ]),
            {
                'item1': 'root',
                'item2': 'root',
                'item3': 'root',
            }
        )
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        })
        self.assertEqual(book.meta, {
            'item1': {},
            'item2': {},
            'item3': {},
        })


class TestDeleteItem(TestBook):
    def test_basic_folder(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {
                'index': 'item1/index.html',
            },
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }
        datafile = os.path.join(book.data_dir, 'item1')
        util.fs.save(os.path.join(datafile, 'index.html'), DUMMY_BYTES)

        self.assertCountEqual(book.delete_item('recycle', 0), {'item1'})
        self.assertEqual(book.toc, {})
        self.assertEqual(book.meta, {})
        self.assertFalse(os.path.lexists(datafile))

    def test_basic_file(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {
                'index': 'item1.htz',
            },
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }
        datafile = os.path.join(book.data_dir, 'item1.htz')
        util.fs.mkzip(datafile)

        self.assertCountEqual(book.delete_item('recycle', 0), {'item1'})
        self.assertEqual(book.toc, {})
        self.assertEqual(book.meta, {})
        self.assertFalse(os.path.lexists(datafile))

    def test_basic_no_index(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }

        self.assertCountEqual(book.delete_item('recycle', 0), {'item1'})
        self.assertEqual(book.toc, {})
        self.assertEqual(book.meta, {})

    def test_index_file_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {
                'index': 'item1.htz',
            },
        }
        book.toc = {
            'recycle': [
                'item1',
            ],
        }

        self.assertCountEqual(book.delete_item('recycle', 0), {'item1'})
        self.assertEqual(book.toc, {})
        self.assertEqual(book.meta, {})

    def test_recursive(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item1-1': {},
            'item1-1-1': {},
            'item1-2': {},
            'item2': {},
        }
        book.toc = {
            'recycle': [
                'item1',
                'item2',
            ],
            'item1': [
                'item1-1',
                'item1-2',
            ],
            'item1-1': [
                'item1-1-1',
            ],
        }

        self.assertCountEqual(book.delete_item('recycle', 0), {
            'item1', 'item1-1', 'item1-1-1', 'item1-2',
        })
        self.assertEqual(book.toc, {
            'recycle': [
                'item2',
            ],
        })
        self.assertEqual(book.meta, {
            'item2': {},
        })

    def test_recursive_partialy_missing_meta(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item1-1': {},
            'item1-1-1': {},
            'item2': {},
        }
        book.toc = {
            'recycle': [
                'item1',
                'item2',
            ],
            'item1': [
                'item1-1',
                'item1-2',
            ],
            'item1-1': [
                'item1-1-1',
            ],
        }

        self.assertCountEqual(book.delete_item('recycle', 0), {
            'item1', 'item1-1', 'item1-1-1', 'item1-2',
        })
        self.assertEqual(book.toc, {
            'recycle': [
                'item2',
            ],
        })
        self.assertEqual(book.meta, {
            'item2': {},
        })

    def test_multi(self):
        host = Host(self.test_root)
        book = Book(host)
        case_meta = {
            'item1': {},
            'item2': {},
        }
        case = {
            'root': [
                'item1',
                'item2',
                'item1',
            ],
        }

        book.meta = copy.deepcopy(case_meta)
        book.toc = copy.deepcopy(case)
        self.assertCountEqual(book.delete_item('root', 0), set())
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item1',
            ],
        })
        self.assertEqual(book.meta, case_meta)

    def test_bad_current_parent_missing(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}
        book.toc = {}

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.delete_item('nonexist', 0)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_out_of_range(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.delete_item('root', 10)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_bad_current_index_negative(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
        }
        book.toc = {
            'root': [
                'item1',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.delete_item('root', -1)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)


class TestDeleteItems(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        book.toc = {
            'recycle': [
                'item1',
                'item2',
                'item3',
            ],
        }

        self.assertCountEqual(
            book.delete_items([
                ('recycle', 0),
                ('recycle', 2),
            ]),
            {'item1', 'item3'},
        )
        self.assertEqual(book.toc, {
            'recycle': [
                'item2',
            ],
        })
        self.assertEqual(book.meta, {
            'item2': {},
        })

    def test_duplicated_items(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
        }
        case = {
            'root': [
                'item1',
            ],
            'item1': [
                'item2',
            ],
            'item2': [
                'item3',
            ],
            'item3': [
                'item1',
            ],
        }

        book.toc = copy.deepcopy(case)
        self.assertCountEqual(
            book.delete_items([
                ('root', 0),
                ('item1', 0),
                ('item2', 0),
                ('item3', 0),
                ('item1', 0),
            ]),
            {'item1', 'item2', 'item3'},
        )
        self.assertEqual(book.toc, {})
        self.assertEqual(book.meta, {})


class TestSortItem(TestBook):
    def test_reverse(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}

        book.toc = {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        }
        book.sort_item('root', 'reverse')
        self.assertEqual(book.toc, {
            'root': [
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_by_id(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}

        # normal
        book.toc = {
            'root': [
                'item2',
                'item1',
                'item3',
            ],
        }
        book.sort_item('root', 'id')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        })

        # reverse
        book.toc = {
            'root': [
                'item2',
                'item1',
                'item3',
            ],
        }
        book.sort_item('root', 'id', True)
        self.assertEqual(book.toc, {
            'root': [
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_by_type(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {
                'type': 'folder',
            },
            'item2': {},
            'item3': {
                'type': '',
            },
            'item4': {
                'type': 'site',
            },
            'item5': {
                'type': 'bookmark',
            },
            'item6': {
                'type': 'postit',
            },
        }

        # normal
        book.toc = {
            'root': [
                'item6',
                'item5',
                'item2',
                'item3',
                'item4',
                'item1',
            ],
        }
        book.sort_item('root', 'type')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
                'item5',
                'item6',
            ],
        })

        # reverse
        book.toc = {
            'root': [
                'item1',
                'item4',
                'item3',
                'item2',
                'item5',
                'item6',
            ],
        }
        book.sort_item('root', 'type', True)
        self.assertEqual(book.toc, {
            'root': [
                'item6',
                'item5',
                'item4',
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_by_title(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {
                'title': '',
            },
            'item3': {
                'title': 'abc',
            },
            'item4': {
                'title': 'xyz',
            },
        }

        # normal
        book.toc = {
            'root': [
                'item4',
                'item1',
                'item3',
                'item2',
            ],
        }
        book.sort_item('root', 'title')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
        })

        # reverse
        book.toc = {
            'root': [
                'item2',
                'item3',
                'item1',
                'item4',
            ],
        }
        book.sort_item('root', 'title', True)
        self.assertEqual(book.toc, {
            'root': [
                'item4',
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_by_index(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {
                'index': 'item2/index.html',
            },
            'item3': {
                'index': 'item3.htz',
            },
            'item4': {
                'index': 'item4.maff',
            },
        }

        # normal
        book.toc = {
            'root': [
                'item4',
                'item1',
                'item3',
                'item2',
            ],
        }
        book.sort_item('root', 'index')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
        })

        # reverse
        book.toc = {
            'root': [
                'item2',
                'item3',
                'item1',
                'item4',
            ],
        }
        book.sort_item('root', 'index', True)
        self.assertEqual(book.toc, {
            'root': [
                'item4',
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_by_source(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {
                'source': '',
            },
            'item3': {
                'source': 'http://example.com',
            },
            'item4': {
                'source': 'http://w3c.org',
            },
        }

        # normal
        book.toc = {
            'root': [
                'item4',
                'item1',
                'item3',
                'item2',
            ],
        }
        book.sort_item('root', 'source')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
        })

        # reverse
        book.toc = {
            'root': [
                'item2',
                'item3',
                'item1',
                'item4',
            ],
        }
        book.sort_item('root', 'source', True)
        self.assertEqual(book.toc, {
            'root': [
                'item4',
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_by_create(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {
                'create': '20200101000000000',
            },
            'item3': {
                'create': '20210101000000000',
            },
            'item4': {
                'create': '20220101000000000',
            },
        }

        # normal
        book.toc = {
            'root': [
                'item4',
                'item1',
                'item3',
                'item2',
            ],
        }
        book.sort_item('root', 'create')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
        })

        # reverse
        book.toc = {
            'root': [
                'item2',
                'item3',
                'item1',
                'item4',
            ],
        }
        book.sort_item('root', 'create', True)
        self.assertEqual(book.toc, {
            'root': [
                'item4',
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_by_modify(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {
                'modify': '20200101000000000',
            },
            'item3': {
                'modify': '20210101000000000',
            },
            'item4': {
                'modify': '20220101000000000',
            },
        }

        # normal
        book.toc = {
            'root': [
                'item4',
                'item1',
                'item3',
                'item2',
            ],
        }
        book.sort_item('root', 'modify')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
                'item4',
            ],
        })

        # reverse
        book.toc = {
            'root': [
                'item2',
                'item3',
                'item1',
                'item4',
            ],
        }
        book.sort_item('root', 'modify', True)
        self.assertEqual(book.toc, {
            'root': [
                'item4',
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_by_marked(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {
                'marked': False,
            },
            'item3': {
                'marked': True,
            },
        }

        # normal
        book.toc = {
            'root': [
                'item1',
                'item3',
                'item2',
            ],
        }
        book.sort_item('root', 'marked')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
        })

        # reverse
        book.toc = {
            'root': [
                'item2',
                'item1',
                'item3',
            ],
        }
        book.sort_item('root', 'marked', True)
        self.assertEqual(book.toc, {
            'root': [
                'item3',
                'item2',
                'item1',
            ],
        })

    def test_bad_by_unknown(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {
            'item1': {},
            'item2': {},
            'item3': {},
            'item4': {},
        }
        book.toc = {
            'root': [
                'item4',
                'item1',
                'item3',
                'item2',
            ],
        }

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.sort_item('root', 'unknown')
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

        orig_meta = copy.deepcopy(book.meta)
        orig_toc = copy.deepcopy(book.toc)
        with self.assertRaises(ValueError):
            book.sort_item('root', 'unknown', True)
        self.assertEqual(book.meta, orig_meta)
        self.assertEqual(book.toc, orig_toc)

    def test_recursive(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}

        # recursively=False
        book.toc = {
            'root': [
                'item2',
                'item1',
                'item3',
            ],
            'item1': [
                'item1-1',
                'item1-3',
                'item1-2',
            ],
            'item1-1': [
                'item1-1-2',
                'item1-1-3',
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'item2': [
                'item2-3',
                'item2-1',
                'item2-2',
            ],
        }
        book.sort_item('root', 'id')
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
            'item1': [
                'item1-1',
                'item1-3',
                'item1-2',
            ],
            'item1-1': [
                'item1-1-2',
                'item1-1-3',
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'item2': [
                'item2-3',
                'item2-1',
                'item2-2',
            ],
        })

        # recursively=True
        book.toc = {
            'root': [
                'item2',
                'item1',
                'item3',
            ],
            'item1': [
                'item1-1',
                'item1-3',
                'item1-2',
            ],
            'item1-1': [
                'item1-1-2',
                'item1-1-3',
                'item1-1-1',
            ],
            'item1-2': [
                'item1',
            ],
            'item2': [
                'item2-3',
                'item2-1',
                'item2-2',
            ],
        }
        book.sort_item('root', 'id', recursively=True)
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                'item2',
                'item3',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item1-1': [
                'item1-1-1',
                'item1-1-2',
                'item1-1-3',
            ],
            'item1-2': [
                'item1',
            ],
            'item2': [
                'item2-1',
                'item2-2',
                'item2-3',
            ],
        })


class TestSortItems(TestBook):
    def test_basic(self):
        host = Host(self.test_root)
        book = Book(host)
        book.meta = {}

        book.toc = {
            'root': [
                'item2',
                'item1',
                'item3',
            ],
            'item1': [
                'item1-1',
                'item1-3',
                'item1-2',
            ],
            'item2': [
                'item2-3',
                'item2-1',
                'item2-2',
            ],
        }
        book.sort_items(['item1', 'item2'], 'id')
        self.assertEqual(book.toc, {
            'root': [
                'item2',
                'item1',
                'item3',
            ],
            'item1': [
                'item1-1',
                'item1-2',
                'item1-3',
            ],
            'item2': [
                'item2-1',
                'item2-2',
                'item2-3',
            ],
        })


if __name__ == '__main__':
    unittest.main()
