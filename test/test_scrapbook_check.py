from unittest import mock
import unittest
import mimetypes
import os
import shutil
import zipfile
from datetime import datetime, timezone, timedelta
from base64 import b64decode

from webscrapbook import WSB_DIR
from webscrapbook import util
from webscrapbook.scrapbook.host import Host
from webscrapbook.scrapbook import check as wsb_check

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_scrapbook_check')

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

    # only 'image/x-ms-bmp' is available on Linux by default
    mimetypes.add_type('image/bmp', '.bmp')

def tearDownModule():
    # stop mock
    for mocking in mockings:
        mocking.stop()

class TestCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192
        cls.test_root = os.path.join(test_root, 'general')
        cls.test_tree = os.path.join(cls.test_root, WSB_DIR, 'tree')

    def setUp(self):
        """Set up a general temp test folder
        """
        os.makedirs(self.test_tree)

    def tearDown(self):
        """Remove general temp test folder
        """
        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

class TestBookChecker(TestCheck):
    def test_normal(self):
        """A simple normal check case. No error should raise."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "root": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_invalid_id=True)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {})
        self.assertDictEqual(book.toc, {'root': ['20200101000000000']})

    def test_resolve_missing_index(self):
        """Resolve item with missing index"""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "title": "MyTitle中文",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_index=True)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {})
        self.assertDictEqual(book.toc, {'root': ['20200101000000000']})

    def test_resolve_missing_index_file(self):
        """Resolve item with missing index file"""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_index_file=True)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {})
        self.assertDictEqual(book.toc, {'root': ['20200101000000000']})

    def test_resolve_missing_create01(self):
        """Resolve item with empty create (infer from ID)"""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "create": "",
    "modify": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "modify": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "foobar": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "create": "",
    "modify": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "foobar"
  ]
})""")
        ts = util.id_to_datetime(util.datetime_to_id()).timestamp()
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "foobar": {
    "title": "MyTitle中文",
    "type": "folder",
    "create": "",
    "modify": "20200101000000000"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "foobar"
  ]
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "foobar": {
    "title": "MyTitle中文",
    "type": "folder",
    "create": ""
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "foobar"
  ]
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "create": "20200101000000000",
    "modify": "",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "create": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "title": "MyTitle中文",
    "type": "folder",
    "create": "20200101000000000",
    "modify": ""
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "foobar": {
    "title": "MyTitle中文",
    "type": "folder",
    "create": "",
    "modify": ""
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "foobar"
  ]
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_missing_date=True)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "MyTitle中文",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "source": "http://example.com",
    "icon": "favicon.ico"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_older_mtime=True)
        for info in generator.run():
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

    def test_resolve_toc_invalid(self):
        """Remove invalid items from TOC."""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "item1": {
    "title": "MyTitle中文",
    "type": "folder"
  },
  "item2": {
    "title": "MyTitle2",
    "type": "separator"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "item1",
    "unknown1",
    "unknown2",
    "hidden",
    "recycle"
  ],
  "item1": [
    "item2",
    "unknown3",
    "root"
  ],
  "item3": [
    "item1"
  ],
  "recycle": [
    "item4"
  ]
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_toc_invalid=True)
        for info in generator.run():
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

    def test_resolve_toc_unreachable(self):
        """Resolve unreachable items."""
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "item1": {
    "title": "MyTitle中文",
    "type": "folder"
  },
  "item2": {
    "title": "MyTitle2",
    "type": "separator"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": []
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_toc_unreachable=True)
        for info in generator.run():
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
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "item1": {
    "title": "MyTitle中文",
    "type": "folder"
  },
  "item2": {
    "title": "MyTitle2",
    "type": "separator"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "item1",
    "item2"
  ],
  "item1": [],
  "item2": []
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_toc_empty_subtree=True)
        for info in generator.run():
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
        """Check for unindexed files.

        - Favicons should be cached regardless of other resolve options.
        """
        test_index = os.path.join(self.test_root, '20200101000000000.htz')
        with zipfile.ZipFile(test_index, 'w') as zh:
            zh.writestr('index.html', """<!DOCTYPE html>
<html
    data-scrapbook-create="20200102030405067"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
<link rel="shortcut icon" href="favicon.bmp">
</head>
<body>
page content
</body>
</html>""")
            zh.writestr('favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_unindexed_files=True)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.htz',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200102030405067',
                'modify': '20200102030405067',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                'source': 'http://example.com',
                'comment': '',
                },
            })
        self.assertEqual(os.listdir(os.path.join(self.test_tree, 'favicon')),
            ['dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'])

    def test_resolve_absolute_icon01(self):
        """Check favicon with absolute URL."""
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.html",
    "icon": "data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA"
  }
})""")
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_absolute_icon=True)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'type': '',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                },
            })
        self.assertEqual(os.listdir(os.path.join(self.test_tree, 'favicon')),
            ['dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'])

    def test_resolve_absolute_icon02(self):
        """Keep original value for bad data URL."""
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.html",
    "icon": "data:"
  }
})""")
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_absolute_icon=True)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.html",
    "icon": "data:image/bmp;base64,Qk08AAA-------"
  }
})""")
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_absolute_icon=True)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.html",
    "icon": "blob:http%3A//example.com/c94d498c-7818-49b3-8e79-d3959938ba0a"
  }
})""")
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_absolute_icon=True)
        for info in generator.run():
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
        test_index = os.path.join(self.test_root, '20200101000000000.htz')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.htz",
    "type": "",
    "icon": ".wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp"
  }
})""")
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

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_unused_icon=True)
        for info in generator.run():
            pass

        self.assertEqual(os.listdir(os.path.join(self.test_tree, 'favicon')),
            ['dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'])
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
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "item1": {
    "title": "MyTitle中文",
    "type": "folder"
  },
  "item2": {
    "title": "MyTitle2",
    "type": "separator"
  },
  "item3": {
    "title": "MyTitle2",
    "type": "",
    "index": "item3.html"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "item1",
    "item2"
  ],
  "item1": ["item3", "nonexistent"],
  "item2": ["recycle"]
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.BookChecker(book, resolve_all=True)
        for info in generator.run():
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

class TestIndexer(TestCheck):
    def test_normal(self):
        """A simple normal check case. No error should raise."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
<link rel="shortcut icon" href="favicon.png">
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'icon': 'favicon.png',
                'source': 'http://example.com',
                'comment': '',
                },
            })

    def test_item_id(self):
        """Test if id is provided."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-id="myid"
    data-scrapbook-create="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
<link rel="shortcut icon" href="favicon.png">
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            'myid': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'icon': 'favicon.png',
                'source': 'http://example.com',
                'comment': '',
                },
            })

    def test_item_id_used(self):
        """Skip if id is provided but used."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "myid": {
    "title": "dummy",
    "type": "folder"
  }
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-id="myid"
    data-scrapbook-create="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
<link rel="shortcut icon" href="favicon.png">
</head>
<body>
page content
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            'myid': {
                'title': 'dummy',
                'type': 'folder',
                },
            })

    def test_item_id_special(self):
        """Skip if id is special."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-id="root"
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
</head>
<body>
page content
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {})

    def test_item_id_filename01(self):
        """Test if filename corresponds to standard ID format."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
</head>
<body>
page content
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': 'http://example.com',
                'comment': '',
                },
            })

    def test_item_id_filename02(self):
        """Test if base filename corresponds to standard ID format."""
        test_index = os.path.join(self.test_root, 'subdir', '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
</head>
<body>
page content
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': 'subdir/20200101000000000/index.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': 'http://example.com',
                'comment': '',
                },
            })

    def test_item_id_filename03(self):
        """Generate new ID if filename corresponds to standard ID format but used."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "title": "dummy",
    "type": "folder"
  }
})""")
        with open(os.path.join(self.test_tree, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
</head>
<body>
page content
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        new_id = list(book.meta.keys())[-1]
        self.assertRegex(new_id, r'^\d{17}$')

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'title': 'dummy',
                'type': 'folder',
                },
            new_id: {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': 'http://example.com',
                'comment': '',
                },
            })

    def test_item_id_filename04(self):
        """Generate new ID if filename not corresponds to standard ID format."""
        test_index = os.path.join(self.test_root, 'foo', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
</head>
<body>
page content
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        new_id = list(book.meta.keys())[-1]
        self.assertRegex(new_id, r'^\d{17}$')

        self.assertDictEqual(book.meta, {
            new_id: {
                'index': 'foo/index.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': 'http://example.com',
                'comment': '',
                },
            })

    def test_item_title01(self):
        """Test title with descendant tags."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com/mypage.html">
<head>
<meta charset="UTF-8">
<title>my<span>page</span>中文</title>
</head>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'my<span>page</span>中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': 'http://example.com/mypage.html',
                'comment': '',
                },
            })

    def test_item_title02(self):
        """Infer from source URL."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com/mypage.html">
<head>
<meta charset="UTF-8">
</head>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mypage.html',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': 'http://example.com/mypage.html',
                'comment': '',
                },
            })

    def test_item_title03(self):
        """Infer from ID if not separator."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com">
<head>
<meta charset="UTF-8">
</head>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': '20200101000000000',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': 'http://example.com',
                'comment': '',
                },
            })

    def test_item_title04(self):
        """Keep empty for separator."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-type="separator"
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000"
    data-scrapbook-source="http://example.com"
    >
<head>
<meta charset="UTF-8">
</head>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': '',
                'type': 'separator',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': 'http://example.com',
                'comment': '',
                },
            })

    def test_item_icon(self):
        """Check if favicon in an archive page is correctly cached."""
        test_index = os.path.join(self.test_root, '20200101000000000.htz')
        with zipfile.ZipFile(test_index, 'w') as zh:
            zh.writestr('index.html', """\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000">
<head>
<meta charset="UTF-8">
<title>MyTitle 中文</title>
<link rel="shortcut icon" href="favicon.bmp">
</head>
<body>
page content
</body>
</html>
""")
            zh.writestr('favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.htz',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                'source': '',
                'comment': '',
                },
            })

    def test_param_handle_ie_meta01(self):
        """handle_ie_meta=True"""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<!-- saved from url=(0029)http://example.com/?a=123#456 -->
<html>
<head>
<meta charset="UTF-8">
<title>mytitle</title>
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book, handle_ie_meta=True)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'icon': '',
                'source': 'http://example.com/?a=123#456',
                'comment': '',
                },
            })

    def test_param_handle_ie_meta02(self):
        """handle_ie_meta=False"""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<!-- saved from url=(0029)http://example.com/?a=123#456 -->
<html>
<head>
<meta charset="UTF-8">
<title>mytitle</title>
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book, handle_ie_meta=False)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'icon': '',
                'source': '',
                'comment': '',
                },
            })

    def test_param_handle_singlefile_meta01(self):
        """handle_singlefile_meta=True"""
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html><html><!--
 Page saved with SingleFile 
 url: http://example.com/?a=123#456 
 saved date: Wed Jan 01 2020 10:00:00 GMT+0800 (台北標準時間)
--><head>
<meta charset="UTF-8">
<title>mytitle</title>
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book, handle_singlefile_meta=True)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101020000000',
                'modify': '20200102030405067',
                'icon': '',
                'source': 'http://example.com/?a=123#456',
                'comment': '',
                },
            })

    def test_param_handle_singlefile_meta02(self):
        """handle_singlefile_meta=False"""
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html><html><!--
 Page saved with SingleFile 
 url: http://example.com/?a=123#456 
 saved date: Wed Jan 01 2020 10:00:00 GMT+0800 (台北標準時間)
--><head>
<meta charset="UTF-8">
<title>mytitle</title>
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book, handle_singlefile_meta=False)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'icon': '',
                'source': '',
                'comment': '',
                },
            })

    def test_param_handle_savepagewe_meta01(self):
        """handle_savepagewe_meta=True"""
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html>
<head>
<base href="http://example.com/?a=123#456">
<meta charset="UTF-8">
<title>mytitle</title>
<meta name="savepage-url" content="http://example.com/?a=123#456">
<meta name="savepage-title" content="MY TITLE">
<meta name="savepage-from" content="http://example.com/?a=123#456">
<meta name="savepage-date" content="Wed Jan 01 2020 10:00:00 GMT+0800 (台北標準時間)">
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book, handle_savepagewe_meta=True)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'MY TITLE',
                'type': '',
                'create': '20200101020000000',
                'modify': '20200102030405067',
                'icon': '',
                'source': 'http://example.com/?a=123#456',
                'comment': '',
                },
            })

    def test_param_handle_savepagewe_meta02(self):
        """handle_savepagewe_meta=False"""
        test_index = os.path.join(self.test_root, '20200101000000000.html')
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html>
<head>
<base href="http://example.com/?a=123#456">
<meta charset="UTF-8">
<title>mytitle</title>
<meta name="savepage-url" content="http://example.com/?a=123#456">
<meta name="savepage-title" content="MY TITLE">
<meta name="savepage-from" content="http://example.com/?a=123#456">
<meta name="savepage-date" content="Wed Jan 01 2020 10:00:00 GMT+0800 (台北標準時間)">
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book, handle_savepagewe_meta=False)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'icon': '',
                'source': '',
                'comment': '',
                },
            })

    def test_param_handle_maoxian_meta01(self):
        """handle_maoxian_meta=True"""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html>
<!-- OriginalSrc: http://example.com/?a=123#456 -->
<head>
<meta charset="UTF-8">
<title>mytitle</title>
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book, handle_maoxian_meta=True)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'icon': '',
                'source': 'http://example.com/?a=123#456',
                'comment': '',
                },
            })

    def test_param_handle_maoxian_meta02(self):
        """handle_maoxian_meta=False"""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html>
<!-- OriginalSrc: http://example.com/?a=123#456 -->
<head>
<meta charset="UTF-8">
<title>mytitle</title>
</head>
<body>
page content
</body>
</html>
""")
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = wsb_check.Indexer(book, handle_maoxian_meta=False)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'icon': '',
                'source': '',
                'comment': '',
                },
            })

class FavIconCacher(TestCheck):
    def test_cache01(self):
        """Cache absolute URL.

        Test using data URL. Should also work for a remote URL.
        """
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "icon": "data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA"
  }
})""")

        book = Host(self.test_root).books['']
        generator = wsb_check.FavIconCacher(book)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '../.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                },
            })

if __name__ == '__main__':
    unittest.main()
