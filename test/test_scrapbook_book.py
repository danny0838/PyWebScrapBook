from unittest import mock
import unittest
import os
import shutil
import io
import re
import zipfile
import time
import functools
from webscrapbook import WSB_DIR, Config
from webscrapbook import util
from webscrapbook.scrapbook.host import Host
from webscrapbook.scrapbook import book as wsb_book
from webscrapbook.scrapbook.book import Book

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_scrapbook_book')

def setUpModule():
    # mock out user config
    global mockings
    mockings = [
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(test_root, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_DIR', os.path.join(test_root, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_CONFIG', test_root),
        ]
    for mocking in mockings:
        mocking.start()

def tearDownModule():
    # stop mock
    for mocking in mockings:
        mocking.stop()

class TestBook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192
        cls.test_root = os.path.join(test_root, 'general')
        cls.test_wsbdir = os.path.join(cls.test_root, WSB_DIR)
        cls.test_config = os.path.join(cls.test_root, WSB_DIR, 'config.ini')

    def setUp(self):
        """Set up a general temp test folder
        """
        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

        os.makedirs(self.test_wsbdir)

    def tearDown(self):
        """Remove general temp test folder
        """
        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

    def create_general_config(self):
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""[book ""]
name = scrapbook
top_dir =
data_dir = data
tree_dir = tree
index = tree/map.html
no_tree = false
""")

    def test_init01(self):
        """Check basic"""
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""[book ""]
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
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""[book "book1"]
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
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
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
        with open(os.path.join(self.test_root, 'tree', 'meta.js'), 'w', encoding='UTF-8') as f:
            pass
        with open(os.path.join(self.test_root, 'tree', 'meta1.js'), 'w', encoding='UTF-8') as f:
            pass
        with open(os.path.join(self.test_root, 'tree', 'meta2.js'), 'w', encoding='UTF-8') as f:
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
        with open(os.path.join(self.test_root, 'tree', 'meta.js'), 'w', encoding='UTF-8') as f:
            pass
        with open(os.path.join(self.test_root, 'tree', 'meta1.js'), 'w', encoding='UTF-8') as f:
            pass
        with open(os.path.join(self.test_root, 'tree', 'meta3.js'), 'w', encoding='UTF-8') as f:
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
        for i in book.iter_meta_files():
            pass
        mock_func.assert_called_once_with('meta')

    @mock.patch('webscrapbook.scrapbook.book.Book.iter_tree_files')
    def test_iter_toc_files(self, mock_func):
        book = Book(Host(self.test_root))
        for i in book.iter_toc_files():
            pass
        mock_func.assert_called_once_with('toc')

    @mock.patch('webscrapbook.scrapbook.book.Book.iter_tree_files')
    def test_iter_fulltext_files(self, mock_func):
        book = Book(Host(self.test_root))
        for i in book.iter_fulltext_files():
            pass
        mock_func.assert_called_once_with('fulltext')

    def test_load_tree_file01(self):
        """Test normal loading"""
        self.create_general_config()
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as f:
            f.write("""/**
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
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as f:
            f.write("""
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
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as f:
            f.write("""
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
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as f:
            f.write("""({
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
        with open(os.path.join(self.test_root, 'meta.js'), 'w', encoding='UTF-8') as f:
            f.write("""
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

    def test_load_tree_files01(self):
        """Test normal loading

        - Item of same ID from the latter overwrites the formatter.
        - Item with None value should be removed.
        """
        self.create_general_config()
        os.makedirs(os.path.join(self.test_root, 'tree'))
        with open(os.path.join(self.test_root, 'tree', 'meta.js'), 'w', encoding='UTF-8') as f:
            f.write("""/**
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
        with open(os.path.join(self.test_root, 'tree', 'meta1.js'), 'w', encoding='UTF-8') as f:
            f.write("""/**
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

    def test_save_fulltext_files01(self):
        self.create_general_config()
        book = Book(Host(self.test_root))
        book.fulltext = {
            "20200101000000000": {
                'index.html': {
                    'content': 'dummy text 1 中文',
                    }
                },
            "20200101000000001": {
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
            "20200101000000000": {
                'index.html': {
                    'content': 'dummy text 1 中文',
                    },
                'frame.html': {
                    'content': 'frame page content',
                    },
                },
            "20200101000000001": {
                'index.html': {
                    'content': 'dummy text 2 中文',
                    },
                },
            "20200101000000002": {
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
            "20200101000000000": {
                'index.html': {
                    'content': 'dummy text 1 中文',
                    },
                'frame.html': {
                    'content': 'frame page content',
                    },
                },
            "20200101000000001": {
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

    def test_init_backup(self):
        book = Book(Host(self.test_root))

        book.init_backup(True)
        self.assertRegex(
            book.backup_dir,
            r'^' + re.escape(os.path.join(self.test_root, WSB_DIR, 'backup', '')) + r'\d{17}$',
            )

        ts = util.datetime_to_id()
        book.init_backup(ts)
        self.assertEqual(
            book.backup_dir,
            os.path.join(self.test_root, WSB_DIR, 'backup', ts),
            )

        book.init_backup(False)
        self.assertIsNone(book.backup_dir)

    def test_backup01(self):
        """A common case."""
        test_file = os.path.join(self.test_root, 'tree', 'meta.js')
        os.makedirs(os.path.dirname(test_file))
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('abc')

        book = Book(Host(self.test_root))
        book.init_backup()
        book.backup(test_file)

        with open(os.path.join(book.backup_dir, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')

    def test_backup02(self):
        """A common directory case."""
        test_dir = os.path.join(self.test_root, 'tree')
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write('abc')
        with open(os.path.join(test_dir, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write('def')

        book = Book(Host(self.test_root))
        book.init_backup()
        book.backup(test_dir)

        with open(os.path.join(book.backup_dir, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')
        with open(os.path.join(book.backup_dir, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'def')

    def test_backup03(self):
        """Pass if backup_dir not set."""
        test_file = os.path.join(self.test_wsbdir, 'icon', 'test.txt')
        os.makedirs(os.path.dirname(test_file))
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('abc')
        test_stat = os.stat(test_file)

        book = Book(Host(self.test_root))
        book.backup(test_file)

        self.assertListEqual(os.listdir(self.test_wsbdir), ['icon'])

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
        book.get_lock('test',
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True)
        mock_filelock.assert_called_once_with(host, 'book--test',
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True)

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
        book.get_tree_lock(timeout=10, stale=120, poll_interval=0.3, assume_acquired=True)
        mock_get_lock.assert_called_once_with('tree',
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True)

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
        with zipfile.ZipFile(archive_file, 'w') as zh:
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

        self.assertEqual(book.get_icon_file({
            'icon': 'favicon.ico?id=123#test',
            }),
            os.path.join(book.data_dir, 'favicon.ico'),
            )

        self.assertEqual(book.get_icon_file({
            'icon': '%E4%B8%AD%E6%96%87%231.ico?id=123#test',
            }),
            os.path.join(book.data_dir, '中文#1.ico'),
            )

        self.assertEqual(book.get_icon_file({
            'index': '20200101000000000/index.html',
            'icon': 'favicon.ico?id=123#test',
            }),
            os.path.join(book.data_dir, '20200101000000000', 'favicon.ico'),
            )

        self.assertEqual(book.get_icon_file({
            'index': '20200101000000000.html',
            'icon': 'favicon.ico?id=123#test',
            }),
            os.path.join(book.data_dir, 'favicon.ico'),
            )

        self.assertEqual(book.get_icon_file({
            'index': '20200101000000000.maff',
            'icon': 'favicon.ico?id=123#test',
            }),
            os.path.join(book.data_dir, 'favicon.ico'),
            )

        self.assertEqual(book.get_icon_file({
            'index': '20200101000000000.maff',
            'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp?id=123#test',
            }),
            os.path.join(book.tree_dir, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'),
            )

    def test_load_note_file01(self):
        """Test for common note file wrapper."""
        test_file = os.path.join(self.test_root, 'index.html')
        with open(test_file, 'w', encoding='UTF-8') as f:
            f.write("""\
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width"><style>pre{white-space: pre-wrap; overflow-wrap: break-word;}</style></head><body><pre>
Note content
2nd line
3rd line
</pre></body></html>""")

        book = Book(Host(self.test_root))
        content = book.load_note_file(test_file)
        self.assertEqual(content, """\
Note content
2nd line
3rd line""")

    def test_load_note_file02(self):
        """Test for common legacy note file wrapper."""
        test_file = os.path.join(self.test_root, 'index.html')
        with open(test_file, 'w', encoding='UTF-8') as f:
            f.write("""\
<html><head><meta http-equiv="Content-Type" content="text/html;Charset=UTF-8"></head><body><pre>
Note content
2nd line
3rd line
</pre></body></html>""")

        book = Book(Host(self.test_root))
        content = book.load_note_file(test_file)
        self.assertEqual(content, """\
Note content
2nd line
3rd line""")

    def test_load_note_file03(self):
        """Return original text if malformatted."""
        test_file = os.path.join(self.test_root, 'index.html')
        html = """\
<html><head><meta http-equiv="Content-Type" content="text/html;Charset=UTF-8"></head><body>
Note content
2nd line
3rd line
</body></html>"""
        with open(test_file, 'w', encoding='UTF-8') as f:
            f.write(html)

        book = Book(Host(self.test_root))
        content = book.load_note_file(test_file)
        self.assertEqual(content, html)

    def test_save_note_file01(self):
        """Test saving. Enforce LF linefeeds."""
        test_file = os.path.join(self.test_root, 'index.html')

        book = Book(Host(self.test_root))
        book.save_note_file(test_file, """\
Note content
2nd line
3rd line""")

        with open(test_file, encoding='UTF-8', newline='') as fh:
            self.assertEqual(fh.read(), """\
<!DOCTYPE html><html><head>\
<meta charset="UTF-8">\
<meta name="viewport" content="width=device-width">\
<style>pre { white-space: pre-wrap; overflow-wrap: break-word; }</style>\
</head><body><pre>
Note content
2nd line
3rd line
</pre></body></html>""")

if __name__ == '__main__':
    unittest.main()
