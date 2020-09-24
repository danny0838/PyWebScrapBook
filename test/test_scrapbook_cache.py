from unittest import mock
import unittest
import os
import shutil
import io
import zipfile
import time
import functools
from webscrapbook import WSB_DIR
from webscrapbook.scrapbook.host import Host
from webscrapbook.scrapbook import cache as wsb_cache

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_scrapbook_cache')

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

class TestCache(unittest.TestCase):
    def setUp(self):
        """Set up a general temp test folder
        """
        self.maxDiff = 8192
        self.test_root = os.path.join(test_root, 'general')
        self.test_config = os.path.join(self.test_root, WSB_DIR, 'config.ini')

    def tearDown(self):
        """Remove general temp test folder
        """
        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

class TestFuncGenerate(TestCache):
    @mock.patch('webscrapbook.scrapbook.cache.Host')
    def test_param_root(self, mock_host):
        for info in wsb_cache.generate(self.test_root):
            pass

        mock_host.assert_called_once_with(self.test_root, None)

    @mock.patch('webscrapbook.scrapbook.cache.Host')
    def test_param_config(self, mock_host):
        for info in wsb_cache.generate(self.test_root, config={}):
            pass

        mock_host.assert_called_once_with(self.test_root, {})

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_param_no_lock01(self, mock_func):
        for info in wsb_cache.generate(self.test_root, no_lock=False):
            pass

        mock_func.assert_called_once_with()

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_param_no_lock02(self, mock_func):
        for info in wsb_cache.generate(self.test_root, no_lock=True):
            pass

        mock_func.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.host.Book')
    def test_param_book_ids01(self, mock_book):
        """Include effective provided IDs"""
        os.makedirs(os.path.dirname(self.test_config))
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[book "id1"]

[book "id2"]

[book "id4"]

[book "id5"]
""")

        for info in wsb_cache.generate(self.test_root, book_ids=['', 'id1', 'id2', 'id3', 'id4']):
            pass

        self.assertEqual([i[0][1] for i in mock_book.call_args_list], ['', 'id1', 'id2', 'id4'])

    @mock.patch('webscrapbook.scrapbook.host.Book')
    def test_param_book_ids02(self, mock_book):
        """Include all available IDs if None provided"""
        os.makedirs(os.path.dirname(self.test_config))
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[book "id1"]

[book "id2"]

[book "id4"]

[book "id5"]
""")

        for info in wsb_cache.generate(self.test_root):
            pass

        self.assertEqual([i[0][1] for i in mock_book.call_args_list], ['', 'id1', 'id2', 'id4', 'id5'])

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_no_tree(self, mock_lock):
        """Books with no_tree=True should be skipped."""
        os.makedirs(os.path.dirname(self.test_config))
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[book ""]
no_tree = true
""")

        for info in wsb_cache.generate(self.test_root):
            pass

        mock_lock.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator')
    def test_param_fulltext01(self, mock_cls):
        """Check fulltext=True"""
        for info in wsb_cache.generate(self.test_root, fulltext=True):
            pass

        mock_cls.assert_called_once()

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator')
    def test_param_fulltext02(self, mock_cls):
        """Check fulltext=False"""
        for info in wsb_cache.generate(self.test_root, fulltext=False):
            pass

        mock_cls.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator')
    def test_param_inclusive_frames01(self, mock_cls):
        for info in wsb_cache.generate(self.test_root, inclusive_frames=True):
            pass

        self.assertTrue(mock_cls.call_args[1]['inclusive_frames'])

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator')
    def test_param_inclusive_frames02(self, mock_cls):
        for info in wsb_cache.generate(self.test_root, inclusive_frames=False):
            pass

        self.assertFalse(mock_cls.call_args[1]['inclusive_frames'])

class TestFulltextCacheGenerator(TestCache):
    def setUp(self):
        """Generate general temp test folder
        """
        self.maxDiff = 8192
        self.test_root = os.path.join(test_root, 'general')
        self.test_tree = os.path.join(self.test_root, WSB_DIR, 'tree')
        self.test_meta = os.path.join(self.test_root, WSB_DIR, 'tree', 'meta.js')
        self.test_toc = os.path.join(self.test_root, WSB_DIR, 'tree', 'toc.js')
        self.test_fulltext = os.path.join(self.test_root, WSB_DIR, 'tree', 'fulltext.js')
        self.test_dir = os.path.join(self.test_root, '20200101000000000')
        self.test_file = os.path.join(self.test_root, '20200101000000000', 'index.html')

        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

        os.makedirs(self.test_tree)
        os.makedirs(self.test_dir)

    def create_meta(self):
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")

    def create_meta_htz(self):
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.htz",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")

    def create_meta_maff(self):
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.maff",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")

    def create_meta_singlehtml(self):
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")

    def create_meta_charset_big5(self):
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "charset": "big5"
  }
})""")

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator._cache_item')
    def test_id_pool01(self, mock_func):
        """Include id in meta or fulltext"""
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000001": {},
  "20200101000000002": {},
  "20200101000000003": {},
  "20200101000000004": {}
})""")
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
  "20200101000000002": {},
  "20200101000000003": {},
  "20200101000000005": {},
  "20200101000000006": {}
})""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list, [
            mock.call('20200101000000001'),
            mock.call('20200101000000002'),
            mock.call('20200101000000003'),
            mock.call('20200101000000004'),
            mock.call('20200101000000005'),
            mock.call('20200101000000006'),
            ])

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator._cache_item')
    def test_id_pool02(self, mock_func):
        """Include each provided id in meta or fulltext"""
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000001": {},
  "20200101000000002": {},
  "20200101000000003": {},
  "20200101000000004": {}
})""")
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
  "20200101000000002": {},
  "20200101000000003": {},
  "20200101000000005": {},
  "20200101000000006": {}
})""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run([
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
                '20200101000000005',
                '20200101000000007',
                ]):
            pass

        self.assertEqual(mock_func.call_args_list, [
            mock.call('20200101000000001'),
            mock.call('20200101000000002'),
            mock.call('20200101000000005'),
            ])

    def test_update01(self):
        """Update if no cache"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content.'
                    },
                }
            })

    def test_update02(self):
        """Update if index file not in cache"""
        self.create_meta()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content.'
                    },
                }
            })

    def test_update03(self):
        """Update if cache index is None"""
        self.create_meta()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": null
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content.'
                    },
                }
            })

    def test_update04(self):
        """Update if index file newer than cache"""
        self.create_meta()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (2000, 2000))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content.'
                    },
                }
            })

    def test_update05(self):
        """Don't include if index file older than cache"""
        self.create_meta()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (2000, 2000))
        os.utime(self.test_file, (1000, 1000))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy'
                    },
                }
            })

    def test_update06(self):
        """Remove if id not in meta"""
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update07(self):
        """Remove if meta[id] is None"""
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000000": null
})""")
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update08(self):
        """Remove if item no index"""
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000000": {
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update09(self):
        """Remove if item index is falsy"""
        with open(self.test_meta, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "",
    "title": "Dummy",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000"
  }
})""")
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update10(self):
        """Remove if index file not exist"""
        self.create_meta()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  }
 }
})""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update11(self):
        """Update subfile if not yet in cache.

        - As long as referred.
        - Even if mtime older than cache.
        """
        self.create_meta()
        linked_file = os.path.join(self.test_dir, 'linked.html')
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="linked.html">link</a>
</body>
</html>
""")
        with open(linked_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (2000, 2000))
        os.utime(linked_file, (900, 900))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link'
                    },
                'linked.html': {
                    'content': 'Linked page content.'
                    },
                }
            })

    def test_update12(self):
        """Update subfile if mtime newer than cache

        - Even if no more referred by index file.
        - Even if index file not updating.
        """
        self.create_meta()
        linked_file = os.path.join(self.test_dir, 'linked.html')
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  },
  "linked.html": {
   "content": "dummy2"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        with open(linked_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (900, 900))
        os.utime(linked_file, (2000, 2000))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy'
                    },
                'linked.html': {
                    'content': 'Linked page content.'
                    },
                }
            })

    def test_update13(self):
        """Don't update subfile if mtime older than cache

        - Even if no more referred by index file.
        - Even if index file not updating.
        """
        self.create_meta()
        linked_file = os.path.join(self.test_dir, 'linked.html')
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  },
  "linked.html": {
   "content": "dummy2"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        with open(linked_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (900, 900))
        os.utime(linked_file, (800, 800))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy'
                    },
                'linked.html': {
                    'content': 'dummy2'
                    },
                }
            })

    def test_update14(self):
        """Remove subfile if no more exist

        - Even if index file not updating.
        """
        self.create_meta()
        linked_file = os.path.join(self.test_dir, 'linked.html')
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  },
  "linked.html": {
   "content": "dummy2"
  }
 }
})""")
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (900, 900))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy'
                    }
                }
            })

    def test_update15(self):
        """Update subfiles if archive newer than cache
        """
        self.create_meta_htz()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  },
  "linked_exist.html": {
   "content": "dummy2"
  },
  "linked_old.html": {
   "content": "dummy3"
  },
  "linked_nonexist.html": {
   "content": "dummy4"
  }
 }
})""")
        archive_file = os.path.join(self.test_root, '20200101000000000.htz')
        with zipfile.ZipFile(archive_file, 'w') as zh:
            zh.writestr('index.html', """<!DOCTYPE html>
<html>
<body>
<p>Page content.</p>
<a href="linked_added.html">link1</a>
<a href="linked_exist.html">link2</a>
<a href="linked_old.html">link3</a>
<a href="linked_nonexist.html">link4</a>
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('linked_added.html', """<!DOCTYPE html>
<html>
<body>
Linked page content 1.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('linked_exist.html', """<!DOCTYPE html>
<html>
<body>
Linked page content 2.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr(zipfile.ZipInfo('linked_old.html', (2000, 1, 1, 0, 0, 0)), """<!DOCTYPE html>
<html>
<body>
Linked page content 3.
</body>
</html>
""".encode('UTF-8'))

        t = time.mktime((2020, 2, 2, 0, 0, 0, 0, 0, -1))
        os.utime(self.test_fulltext, (t, t))
        t = time.mktime((2020, 3, 2, 0, 0, 0, 0, 0, -1))
        os.utime(archive_file, (t, t))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content. link1 link2 link3 link4'
                    },
                'linked_added.html': {
                    'content': 'Linked page content 1.'
                    },
                'linked_exist.html': {
                    'content': 'Linked page content 2.'
                    },
                'linked_old.html': {
                    'content': 'dummy3'
                    },
                }
            })

    def test_update16(self):
        """Don't update any subfiles if archive older than cache
        """
        self.create_meta_htz()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  },
  "linked_exist.html": {
   "content": "dummy2"
  },
  "linked_old.html": {
   "content": "dummy3"
  },
  "linked_nonexist.html": {
   "content": "dummy4"
  }
 }
})""")
        archive_file = os.path.join(self.test_root, '20200101000000000.htz')
        with zipfile.ZipFile(archive_file, 'w') as zh:
            zh.writestr('index.html', """<!DOCTYPE html>
<html>
<body>
<p>Page content.</p>
<a href="linked_added.html">link1</a>
<a href="linked_exist.html">link2</a>
<a href="linked_old.html">link3</a>
<a href="linked_nonexist.html">link4</a>
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('linked_added.html', """<!DOCTYPE html>
<html>
<body>
Linked page content 1.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('linked_exist.html', """<!DOCTYPE html>
<html>
<body>
Linked page content 2.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr(zipfile.ZipInfo('linked_old.html', (2000, 1, 1, 0, 0, 0)), """<!DOCTYPE html>
<html>
<body>
Linked page content 3.
</body>
</html>
""".encode('UTF-8'))

        t = time.mktime((2020, 2, 2, 0, 0, 0, 0, 0, -1))
        os.utime(self.test_fulltext, (t, t))
        t = time.mktime((2020, 1, 2, 0, 0, 0, 0, 0, -1))
        os.utime(archive_file, (t, t))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy'
                    },
                'linked_exist.html': {
                    'content': 'dummy2'
                    },
                'linked_old.html': {
                    'content': 'dummy3'
                    },
                'linked_nonexist.html': {
                    'content': 'dummy4'
                    },
                }
            })

    def test_update17(self):
        """Treat as no file exists if archive corrupted
        """
        self.create_meta_htz()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "index.html": {
   "content": "dummy"
  },
  "linked_exist.html": {
   "content": "dummy2"
  },
  "linked_old.html": {
   "content": "dummy3"
  },
  "linked_nonexist.html": {
   "content": "dummy4"
  }
 }
})""")
        archive_file = os.path.join(self.test_root, '20200101000000000.htz')
        with open(archive_file, 'wb'):
            pass

        t = time.mktime((2020, 2, 2, 0, 0, 0, 0, 0, -1))
        os.utime(self.test_fulltext, (t, t))
        t = time.mktime((2020, 3, 2, 0, 0, 0, 0, 0, -1))
        os.utime(archive_file, (t, t))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {}
            })

    def test_update18(self):
        """Update all indexes for a MAFF if archive newer than cache
        """
        self.create_meta_maff()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "20200101000000000/index.html": {
   "content": "dummy"
  },
  "20200101000000000/linked_exist.html": {
   "content": "dummy2"
  },
  "20200101000000000/linked_old.html": {
   "content": "dummy3"
  },
  "20200101000000000/linked_nonexist.html": {
   "content": "dummy4"
  }
 }
})""")
        archive_file = os.path.join(self.test_root, '20200101000000000.maff')
        with zipfile.ZipFile(archive_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """<!DOCTYPE html>
<html>
<body>
<p>Page content.</p>
<a href="linked_added.html">link1</a>
<a href="linked_exist.html">link2</a>
<a href="linked_old.html">link3</a>
<a href="linked_nonexist.html">link4</a>
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('20200101000000000/linked_added.html', """<!DOCTYPE html>
<html>
<body>
Linked page content 1.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('20200101000000000/linked_exist.html', """<!DOCTYPE html>
<html>
<body>
Linked page content 2.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr(zipfile.ZipInfo('20200101000000000/linked_old.html', (2000, 1, 1, 0, 0, 0)), """<!DOCTYPE html>
<html>
<body>
Linked page content 3.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('20200101000000001/index.html', """<!DOCTYPE html>
<html>
<body>
<p>Page content 2.</p>
</body>
</html>
""".encode('UTF-8'))

        t = time.mktime((2020, 2, 2, 0, 0, 0, 0, 0, -1))
        os.utime(self.test_fulltext, (t, t))
        t = time.mktime((2020, 3, 2, 0, 0, 0, 0, 0, -1))
        os.utime(archive_file, (t, t))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                '20200101000000000/index.html': {
                    'content': 'Page content. link1 link2 link3 link4'
                    },
                '20200101000000000/linked_added.html': {
                    'content': 'Linked page content 1.'
                    },
                '20200101000000000/linked_exist.html': {
                    'content': 'Linked page content 2.'
                    },
                '20200101000000000/linked_old.html': {
                    'content': 'dummy3'
                    },
                '20200101000000001/index.html': {
                    'content': 'Page content 2.'
                    },
                }
            })

    def test_update19(self):
        """Don't update any subfile for a MAFF if archive older than cache
        """
        self.create_meta_maff()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "20200101000000000/index.html": {
   "content": "dummy"
  },
  "20200101000000000/linked_exist.html": {
   "content": "dummy2"
  },
  "20200101000000000/linked_old.html": {
   "content": "dummy3"
  },
  "20200101000000000/linked_nonexist.html": {
   "content": "dummy4"
  }
 }
})""")
        archive_file = os.path.join(self.test_root, '20200101000000000.maff')
        with zipfile.ZipFile(archive_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """<!DOCTYPE html>
<html>
<body>
<p>Page content.</p>
<a href="linked_added.html">link1</a>
<a href="linked_exist.html">link2</a>
<a href="linked_old.html">link3</a>
<a href="linked_nonexist.html">link4</a>
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('20200101000000000/linked_added.html', """<!DOCTYPE html>
<html>
<body>
Linked page content 1.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('20200101000000000/linked_exist.html', """<!DOCTYPE html>
<html>
<body>
Linked page content 2.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr(zipfile.ZipInfo('20200101000000000/linked_old.html', (2000, 1, 1, 0, 0, 0)), """<!DOCTYPE html>
<html>
<body>
Linked page content 3.
</body>
</html>
""".encode('UTF-8'))
            zh.writestr('20200101000000001/index.html', """<!DOCTYPE html>
<html>
<body>
<p>Page content 2.</p>
</body>
</html>
""".encode('UTF-8'))

        t = time.mktime((2020, 2, 2, 0, 0, 0, 0, 0, -1))
        os.utime(self.test_fulltext, (t, t))
        t = time.mktime((2020, 1, 2, 0, 0, 0, 0, 0, -1))
        os.utime(archive_file, (t, t))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                '20200101000000000/index.html': {
                    'content': 'dummy'
                    },
                '20200101000000000/linked_exist.html': {
                    'content': 'dummy2'
                    },
                '20200101000000000/linked_old.html': {
                    'content': 'dummy3'
                    },
                '20200101000000000/linked_nonexist.html': {
                    'content': 'dummy4'
                    },
                }
            })

    def test_update20(self):
        """Treat as no file exists if MAFF archive corrupted
        """
        self.create_meta_maff()
        with open(self.test_fulltext, 'w', encoding='UTF-8') as f:
            f.write("""\
scrapbook.fulltext({
 "20200101000000000": {
  "20200101000000000/index.html": {
   "content": "dummy"
  },
  "20200101000000000/linked_exist.html": {
   "content": "dummy2"
  },
  "20200101000000000/linked_old.html": {
   "content": "dummy3"
  },
  "20200101000000000/linked_nonexist.html": {
   "content": "dummy4"
  }
 }
})""")
        archive_file = os.path.join(self.test_root, '20200101000000000.maff')
        with open(archive_file, 'w') as zh:
            pass

        t = time.mktime((2020, 2, 2, 0, 0, 0, 0, 0, -1))
        os.utime(self.test_fulltext, (t, t))
        t = time.mktime((2020, 3, 2, 0, 0, 0, 0, 0, -1))
        os.utime(archive_file, (t, t))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {}
            })

    def test_update21(self):
        """Inline a frame with higher priority than cache as another page."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="iframe.html">link</a>
<iframe src="iframe.html">Frame label</iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link Iframe page content.'
                    },
                }
            })

    def test_update22(self):
        """Inline a frame unless it's already cached as another page."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="linked.html">link1</a>
<a href="iframe.html">link2</a>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
<iframe src="iframe.html"></iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link1 link2'
                    },
                'linked.html': {
                    'content': 'Linked page content. Iframe page content.'
                    },
                }
            })

    def test_update23(self):
        """Inline a frame unless it's already cached as another page."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="iframe.html">link1</a>
<a href="linked.html">link2</a>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
<iframe src="iframe.html"></iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link1 link2'
                    },
                'linked.html': {
                    'content': 'Linked page content.'
                    },
                'iframe.html': {
                    'content': 'Iframe page content.'
                    },
                }
            })

    def test_path01(self):
        """Don't include a path beyond directory of index
        """
        self.create_meta()
        other_file = os.path.join(self.test_root, '20200101000000001', 'index.html')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="../20200101000000001/index.html">link</a>
</body>
</html>
""")
        os.makedirs(os.path.dirname(other_file))
        with open(other_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link'
                    },
                }
            })

    def test_path02(self):
        """Include sibling files of single HTML.
        """
        self.create_meta_singlehtml()
        test_file = os.path.join(self.test_root, '20200101000000000.html')
        other_file = os.path.join(self.test_root, '20200101000000001.html')
        with open(test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="20200101000000001.html">link</a>
</body>
</html>
""")
        with open(other_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                '20200101000000000.html': {
                    'content': 'link'
                    },
                '20200101000000001.html': {
                    'content': 'Linked page content.'
                    },
                }
            })

    def test_path03(self):
        """Don't include external paths or self
        """
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="http://example.com/test.html">link1</a>
<a href="//example.com/test.html">link2</a>
<a href="/test.html">link3</a>
<a href="file:///home/example/test.html">link4</a>
<a href="index.html">link5</a>
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link1 link2 link3 link4 link5'
                    },
                }
            })

    def test_path04(self):
        """Test for a path with special chars
        """
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="ABC%E4%B8%AD%E6%96%87!%23%24%25%26%2B%2C%3B%3D%40%5B%5D%5E%60%7B%7D.html?id=1#123">link</a>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'ABC中文!#$%&+,;=@[]^`{}.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link'
                    },
                'ABC中文!#$%&+,;=@[]^`{}.html': {
                    'content': 'Linked page content.'
                    },
                }
            })

    def test_path05(self):
        """Test for a meta refresh path with special chars
        """
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<meta http-equiv="refresh" content="0;url=ABC%E4%B8%AD%E6%96%87!%23%24%25%26%2B%2C%3B%3D%40%5B%5D%5E%60%7B%7D.html?id=1#123">
</html>
""")
        with open(os.path.join(self.test_dir, 'ABC中文!#$%&+,;=@[]^`{}.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'ABC中文!#$%&+,;=@[]^`{}.html': {
                    'content': 'Linked page content.'
                    },
                }
            })

    def test_path06(self):
        """Don't include links inside a data URL page
        """
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="data:text/html,frame%20%3Ca%20href%3D%22linked.html%22%3Elink%3C%2Fa%3E"></iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'frame link'
                    },
                }
            })

    def test_html_charset01(self):
        """Detect charset from BOM. (UTF-16-LE)"""
        self.create_meta()
        with open(self.test_file, 'wb') as f:
            f.write(b'\xff\xfe')
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body>
English
中文
</body>
</html>
""".encode('UTF-16-LE'))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文'
                    },
                }
            })

    def test_html_charset02(self):
        """Detect charset from BOM. (UTF-16-BE)"""
        self.create_meta()
        with open(self.test_file, 'wb') as f:
            f.write(b'\xfe\xff')
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body>
English
中文
</body>
</html>
""".encode('UTF-16-BE'))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文'
                    },
                }
            })

    def test_html_charset03(self):
        """Get charset from meta[charset] if no BOM."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='big5') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta charset="big5">
</head>
<body>
English
中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文'
                    },
                }
            })

    def test_html_charset04(self):
        """Get charset from meta[http-equiv="content-type"] if no BOM."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='big5') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=big5">
</head>
<body>
English
中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文'
                    },
                }
            })

    def test_html_charset05(self):
        """Get charset from item charset if no BOM or meta."""
        self.create_meta_charset_big5()
        with open(self.test_file, 'w', encoding='big5') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
English
中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文'
                    },
                }
            })

    def test_html_charset06(self):
        """Fallback to UTF-8 if no BOM, meta, or item charset."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
English
中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文'
                    },
                }
            })

    def test_html_charset07(self):
        """Fix certain charsets of the web page."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='cp950') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=big5">
</head>
<body>
碁銹裏墻恒粧嫺
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '碁銹裏墻恒粧嫺'
                    },
                }
            })

    def test_html_elems(self):
        """Text in certain HTML tags should not be cached."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>title text</title>
<style>/* style text */</style>
<script>/* script text */</script>
</head>
<body>
before paragraph <p>paragraph text</p> after paragraph

before iframe <iframe>iframe text</iframe> after iframe

before object <object>object text</object> after object
before applet <applet>applet text</applet> after applet

before audio <audio>audio text</audio> after audio
before video <video>video text</video> after video
before canvas <canvas>canvas text</canvas> after canvas

before noframes <noframes>noframes text</noframes> after noframes
before noscript <noscript>noscript text</noscript> after noscript
before noembed <noembed>noembed text</noembed> after noembed
before svg <svg><text>svg text</text></svg> after svg
before math <math><mtext>math text</mtext></math> after math
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': (
                    """before paragraph paragraph text after paragraph """
                    """before iframe after iframe """
                    """before object after object """
                    """before applet after applet """
                    """before audio after audio """
                    """before video after video """
                    """before canvas after canvas """
                    """before noframes after noframes """
                    """before noscript after noscript """
                    """before noembed after noembed """
                    """before svg after svg """
                    """before math after math"""
                    )},
                }
            })

    def test_xhtml_elems(self):
        """Text in certain HTML tags should not be cached."""
        self.create_meta()
        xhtml_file = os.path.join(self.test_dir, 'index.xhtml')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=index.xhtml">
""")
        with open(xhtml_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html>
<head>
<meta charset="UTF-8"/>
<title>title text</title>
<style>/* style text */</style>
<script>/* script text */</script>
</head>
<body>
before paragraph <p>paragraph text</p> after paragraph

before iframe <iframe>iframe text</iframe> after iframe

before object <object>object text</object> after object
before applet <applet>applet text</applet> after applet

before audio <audio>audio text</audio> after audio
before video <video>video text</video> after video
before canvas <canvas>canvas text</canvas> after canvas

before noframes <noframes>noframes text</noframes> after noframes
before noscript <noscript>noscript text</noscript> after noscript
before noembed <noembed>noembed text</noembed> after noembed
before svg <svg><text>svg text</text></svg> after svg
before math <math><mtext>math text</mtext></math> after math
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'index.xhtml': {
                    'content': (
                    """before paragraph paragraph text after paragraph """
                    """before iframe after iframe """
                    """before object after object """
                    """before applet after applet """
                    """before audio after audio """
                    """before video after video """
                    """before canvas after canvas """
                    """before noframes after noframes """
                    """before noscript after noscript """
                    """before noembed after noembed """
                    """before svg after svg """
                    """before math after math"""
                    )},
                }
            })

    def test_xhtml_malformed(self):
        """lxml seems to work for malformed XHTML"""
        self.create_meta()
        xhtml_file = os.path.join(self.test_dir, 'index.xhtml')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=index.xhtml">
""")
        with open(xhtml_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html>
<head>
<meta charset="UTF-8">
</head>
<body>
first line <br>
second line <br>
<p>paragraph
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'index.xhtml': {
                    'content': 'first line second line paragraph'
                    },
                },
            })

    def test_html_iframe01(self):
        """Include iframe content in index page"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="iframe.html">Frame label 中文</iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content. 中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Iframe page content. 中文'
                    },
                }
            })

    def test_html_iframe02(self):
        """Treat iframe content as another page if specified"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="iframe.html">Frame label 中文</iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content. 中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book, inclusive_frames=False)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'iframe.html': {
                    'content': 'Iframe page content. 中文'
                    },
                }
            })

    def test_html_iframe_datauri01(self):
        """Include data URL content"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="data:text/plain;base64,QUJDMTIz5Lit5paH">Frame label 中文</iframe>
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文'
                    },
                }
            })

    def test_html_iframe_datauri02(self):
        """Include data URL content, regardless of inclusion mode"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="data:text/plain;base64,QUJDMTIz5Lit5paH">Frame label 中文</iframe>
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文'
                    },
                }
            })

    def test_html_frame01(self):
        """Include iframe content in index page"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<frameset cols="*,*">
<frame name="toc" src="frame1.html"></frame>
<frame name="main" src="frame2.html"></frame>
</frameset>
</html>
""")
        with open(os.path.join(self.test_dir, 'frame1.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Frame page content 1.
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'frame2.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Frame page content 1. 中文'
                    },
                }
            })

    def test_html_frame02(self):
        """Treat iframe content as another page if specified"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<frameset cols="*,*">
<frame name="toc" src="frame1.html"></frame>
<frame name="main" src="frame2.html"></frame>
</frameset>
</html>
""")
        with open(os.path.join(self.test_dir, 'frame1.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Frame page content 1.
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'frame2.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book, inclusive_frames=False)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'frame1.html': {
                    'content': 'Frame page content 1.'
                    },
                'frame2.html': {
                    'content': '中文'
                    },
                }
            })

    def test_html_frame_datauri01(self):
        """Include data URL content"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<frameset cols="*,*">
<frame name="toc" src="data:text/plain,ABC123%E4%B8%AD%E6%96%87"></frame>
<frame name="main" src="data:text/plain;base64,QUJDMTIz5Lit5paH"></frame>
</frameset>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 ABC123中文'
                    },
                }
            })

    def test_html_frame_datauri02(self):
        """Include data URL content, regardless of inclusion mode"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<frameset cols="*,*">
<frame name="toc" src="data:text/plain,ABC123%E4%B8%AD%E6%96%87"></frame>
<frame name="main" src="data:text/plain;base64,QUJDMTIz5Lit5paH"></frame>
</frameset>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 ABC123中文'
                    },
                }
            })

    def test_html_refresh01(self):
        """Don't cache content for a page with an instant meta refresh"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0;url=refreshed1.html">
<meta http-equiv="refresh" content="0;url=refreshed2.html">
<meta http-equiv="refresh" content="3;url=refreshed3.html">
</head>
<body>
Main page content.
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed1.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 1. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed2.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 2. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed3.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 3. 中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'refreshed1.html': {
                    'content': 'Refreshed page content 1. 中文'
                    },
                'refreshed2.html': {
                    'content': 'Refreshed page content 2. 中文'
                    },
                'refreshed3.html': {
                    'content': 'Refreshed page content 3. 中文'
                    },
                }
            })

    def test_html_refresh02(self):
        """Cache content for a page without an instant meta refresh"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="1;url=refreshed1.html">
<meta http-equiv="refresh" content="2;url=refreshed2.html">
<meta http-equiv="refresh" content="3;url=refreshed3.html">
</head>
<body>
Main page content.
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed1.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 1. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed2.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 2. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed3.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 3. 中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Main page content.'
                    },
                'refreshed1.html': {
                    'content': 'Refreshed page content 1. 中文'
                    },
                'refreshed2.html': {
                    'content': 'Refreshed page content 2. 中文'
                    },
                'refreshed3.html': {
                    'content': 'Refreshed page content 3. 中文'
                    },
                }
            })

    def test_html_refresh_datauri01(self):
        """Include all refresh target data URL pages, regardless of refresh time"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0;url=data:text/plain,ABC123%E4%B8%AD%E6%96%87">
<meta http-equiv="refresh" content="1;url=data:text/plain;base64,QUJDMTIz5Lit5paH">
</head>
<body>
Main page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 ABC123中文'
                    },
                }
            })

    def test_html_refresh_datauri02(self):
        """Include all refresh target data URL pages, regardless of refresh time"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="1;url=data:text/plain,ABC123%E4%B8%AD%E6%96%87">
<meta http-equiv="refresh" content="2;url=data:text/plain;base64,QUJDMTIz5Lit5paH">
</head>
<body>
Main page content.
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 ABC123中文 Main page content.'
                    },
                }
            })

    def test_html_link(self):
        """Cache linked pages"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="linked.html">link 中文</a>
<area href="linked2.html">
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked2.html'), 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
Linked page content 2. 中文
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link 中文'
                    },
                'linked.html': {
                    'content': 'Linked page content. 中文'
                    },
                'linked2.html': {
                    'content': 'Linked page content 2. 中文'
                    },
                }
            })

    def test_html_link_datauri(self):
        """Include linked data URL pages"""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="data:text/plain,ABC123%E4%B8%AD%E6%96%87">link 中文</a>
<area href="data:text/plain;base64,QUJDMTIz5Lit5paH">
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 link 中文 ABC123中文'
                    },
                }
            })

    def test_text_charset01(self):
        """Detect charset from BOM. (UTF-16-LE)"""
        self.create_meta_charset_big5()
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'wb') as f:
            f.write(b'\xff\xfe')
            f.write("""中文""".encode('UTF-16-LE'))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'file.txt': {
                    'content': '中文'
                    },
                }
            })

    def test_text_charset02(self):
        """Detect charset from BOM. (UTF-16-BE)"""
        self.create_meta_charset_big5()
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'wb') as f:
            f.write(b'\xfe\xff')
            f.write("""中文""".encode('UTF-16-BE'))

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'file.txt': {
                    'content': '中文'
                    },
                }
            })

    def test_text_charset03(self):
        """Use item charset if no BOM."""
        self.create_meta_charset_big5()
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'w', encoding='big5') as f:
            f.write("""\
Text file content
中文
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'file.txt': {
                    'content': 'Text file content 中文'
                    },
                }
            })

    def test_text_charset04(self):
        """Fallback to UTF-8 if no BOM or item charset."""
        self.create_meta()
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'w', encoding='UTF-8') as f:
            f.write("""\
Text file content
中文
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'file.txt': {
                    'content': 'Text file content 中文'
                    },
                }
            })

    def test_text_charset05(self):
        """Certain charsets of the web page need fix."""
        self.create_meta_charset_big5()
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'w', encoding='cp950') as f:
            f.write("""碁銹裏墻恒粧嫺""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'file.txt': {
                    'content': '碁銹裏墻恒粧嫺'
                    },
                }
            })

    def test_text_charset06(self):
        """Wrong encoding produces gibberish, but won't fail out."""
        self.create_meta_charset_big5()
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'w', encoding='UTF-8') as f:
            f.write("""Text file content 中文""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                'file.txt': {
                    'content': 'Text file content 銝剜��'
                    },
                }
            })

    def test_binary(self):
        """Don't include binary in cache"""
        self.create_meta()
        bin_file = os.path.join(self.test_root, '20200101000000000', 'image.jpg')
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=image.jpg">
""")
        with open(bin_file, 'wb') as f:
            pass

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': ''
                    },
                }
            })

    def test_datauri_html(self):
        """Cache HTML files."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="data:text/html,<b>test</b>">link1</a>
<a href="data:application/xhtml+xml,<b>test</b>">link2</a>
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'test link1 test link2'
                    },
                }
            })

    def test_datauri_text(self):
        """Cache text files only."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="data:text/plain,text/plain">link1</a>
<a href="data:text/css,text/css">link2</a>
<a href="data:text/xml,text/xml">link3</a>
<a href="data:image/svg+xml,image/svg+xml">link4</a>
<a href="data:application/javascript,application/javascript">link5</a>
<a href="data:application/octet-stream,application/octet-stream">link6</a>
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': (
                        'text/plain link1 '
                        'text/css link2 '
                        'text/xml link3 '
                        'link4 '
                        'link5 '
                        'link6'
                    )},
                }
            })

    def test_datauri_malformed(self):
        """Skip caching data of a malformed data URL."""
        self.create_meta()
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<body>
<a href="data:text/html;base64,wtf">link</a>
</body>
</html>
""")

        book = Host(self.test_root).books['']
        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link'
                    },
                }
            })

if __name__ == '__main__':
    unittest.main()
