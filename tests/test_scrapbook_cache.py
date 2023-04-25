import collections
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from lxml import etree

from webscrapbook import WSB_DIR
from webscrapbook._polyfill import zipfile
from webscrapbook.scrapbook import cache as wsb_cache

from . import TEMP_DIR, TestBookMixin


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='cache-', dir=TEMP_DIR)
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


class TestCache(TestBookMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_tree = os.path.join(self.test_root, WSB_DIR, 'tree')
        os.makedirs(self.test_tree)


class TestFuncGenerate(TestCache):
    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_param_lock01(self, mock_func):
        for _info in wsb_cache.generate(self.test_root, lock=True):
            pass

        mock_func.assert_called_once_with()

    @mock.patch('webscrapbook.scrapbook.host.Book.get_tree_lock')
    def test_param_lock02(self, mock_func):
        for _info in wsb_cache.generate(self.test_root, lock=False):
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

        for _info in wsb_cache.generate(self.test_root, book_ids=['', 'id1', 'id2', 'id3', 'id4']):
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

        for _info in wsb_cache.generate(self.test_root):
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

        for _info in wsb_cache.generate(self.test_root):
            pass

        mock_lock.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator')
    def test_param_fulltext01(self, mock_cls):
        """Check fulltext=True"""
        for _info in wsb_cache.generate(self.test_root, fulltext=True):
            pass

        mock_cls.assert_called_once()

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator')
    def test_param_fulltext02(self, mock_cls):
        """Check fulltext=False"""
        for _info in wsb_cache.generate(self.test_root, fulltext=False):
            pass

        mock_cls.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator')
    def test_param_inclusive_frames01(self, mock_cls):
        for _info in wsb_cache.generate(self.test_root, inclusive_frames=True):
            pass

        self.assertTrue(mock_cls.call_args[1]['inclusive_frames'])

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator')
    def test_param_inclusive_frames02(self, mock_cls):
        for _info in wsb_cache.generate(self.test_root, inclusive_frames=False):
            pass

        self.assertFalse(mock_cls.call_args[1]['inclusive_frames'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_static_site01(self, mock_cls):
        for _info in wsb_cache.generate(self.test_root, static_site=True):
            pass

        mock_cls.assert_called_once()

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_static_site02(self, mock_cls):
        for _info in wsb_cache.generate(self.test_root, static_site=False):
            pass

        mock_cls.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_static_index01(self, mock_cls):
        for _info in wsb_cache.generate(self.test_root, static_site=True, static_index=True):
            pass

        self.assertTrue(mock_cls.call_args[1]['static_index'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_static_index02(self, mock_cls):
        for _info in wsb_cache.generate(self.test_root, static_site=True, static_index=False):
            pass

        self.assertFalse(mock_cls.call_args[1]['static_index'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_locale(self, mock_cls):
        for _info in wsb_cache.generate(self.test_root, static_site=True, locale='zh_TW'):
            pass

        self.assertEqual(mock_cls.call_args[1]['locale'], 'zh_TW')

    @mock.patch('webscrapbook.scrapbook.cache.RssFeedGenerator')
    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_rss_root01(self, mock_ssg, mock_rss):
        for _info in wsb_cache.generate(self.test_root, static_site=True, rss_root='http://example.com:8000/wsb/'):
            pass

        self.assertTrue(mock_ssg.call_args[1]['rss'])
        mock_rss.assert_called_once()

    @mock.patch('webscrapbook.scrapbook.cache.RssFeedGenerator')
    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator')
    def test_param_rss_root02(self, mock_ssg, mock_rss):
        for _info in wsb_cache.generate(self.test_root, static_site=True, rss_root=None):
            pass

        self.assertFalse(mock_ssg.call_args[1]['rss'])
        mock_rss.assert_not_called()

    @mock.patch('webscrapbook.scrapbook.host.Host.get_subpath', lambda *_: '')
    @mock.patch('webscrapbook.scrapbook.host.Host.init_auto_backup')
    def test_param_backup01(self, mock_func):
        for _info in wsb_cache.generate(self.test_root, static_site=True, backup=True):
            pass

        self.assertEqual(mock_func.call_args_list, [mock.call(note='cache'), mock.call(False)])

    @mock.patch('webscrapbook.scrapbook.host.Host.init_auto_backup')
    def test_param_backup02(self, mock_func):
        for _info in wsb_cache.generate(self.test_root, static_site=True, backup=False):
            pass

        mock_func.assert_not_called()


class TestFulltextCacheGenerator(TestCache):
    def setUp(self):
        """Generate general temp test folder
        """
        super().setUp()
        self.test_meta = os.path.join(self.test_tree, 'meta.js')
        self.test_toc = os.path.join(self.test_tree, 'toc.js')
        self.test_fulltext = os.path.join(self.test_tree, 'fulltext.js')
        self.test_dir = os.path.join(self.test_root, '20200101000000000')
        self.test_file = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(self.test_dir)

    def general_meta(self):
        return {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'Dummy',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
            },
        }

    def general_meta_htz(self):
        return {
            '20200101000000000': {
                'index': '20200101000000000.htz',
                'title': 'Dummy',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
            },
        }

    def general_meta_maff(self):
        return {
            '20200101000000000': {
                'index': '20200101000000000.maff',
                'title': 'Dummy',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
            },
        }

    def general_meta_singlehtml(self):
        return {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'Dummy',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
            },
        }

    def general_meta_charset_big5(self):
        return {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'Dummy',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'charset': 'big5',
            },
        }

    @mock.patch('webscrapbook.scrapbook.cache.FulltextCacheGenerator._cache_item')
    def test_id_pool01(self, mock_func):
        """Include id in meta or fulltext"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000001': {},
                '20200101000000002': {},
                '20200101000000003': {},
                '20200101000000004': {},
            },
            fulltext={
                '20200101000000002': {},
                '20200101000000003': {},
                '20200101000000005': {},
                '20200101000000006': {},
            },
        )
        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
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
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000001': {},
                '20200101000000002': {},
                '20200101000000003': {},
                '20200101000000004': {},
            },
            fulltext={
                '20200101000000002': {},
                '20200101000000003': {},
                '20200101000000005': {},
                '20200101000000006': {},
            },
        )
        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run([
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

    def test_recreate(self):
        """Check if current cache is ignored"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000001': {
                    'index': '20200101000000001/index.html',
                    'title': 'Dummy1',
                    'type': '',
                    'create': '20200101000000001',
                    'modify': '20200101000000001',
                },
                '20200101000000002': {
                    'index': '20200101000000002/index.html',
                    'title': 'Dummy2',
                    'type': '',
                    'create': '20200101000000002',
                    'modify': '20200101000000002',
                },
            },
            fulltext={
                '20200101000000001': {
                    'index.html': {
                        'content': 'dummy1',
                    },
                },
                '20200101000000002': {
                    'index.html': {
                        'content': 'dummy2',
                    },
                },
            },
        )
        test_file1 = os.path.join(self.test_root, '20200101000000001', 'index.html')
        test_file2 = os.path.join(self.test_root, '20200101000000002', 'index.html')
        os.makedirs(os.path.dirname(test_file1), exist_ok=True)
        with open(test_file1, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content 1.
</body>
</html>
""")
        os.makedirs(os.path.dirname(test_file2), exist_ok=True)
        with open(test_file2, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content 2.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(test_file1, (2001, 2001))
        os.utime(test_file2, (2002, 2002))

        generator = wsb_cache.FulltextCacheGenerator(book, recreate=True)
        for _info in generator.run(['20200101000000001']):
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000001': {
                'index.html': {
                    'content': 'Page content 1.',
                },
            },
        })

    def test_update01(self):
        """Update if no cache"""
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content.',
                },
            },
        })

    def test_update02(self):
        """Update if index file not in cache"""
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={},
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content.',
                },
            },
        })

    def test_update03(self):
        """Update if cache index is None"""
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={
                '20200101000000000': None,
            },
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content.',
                },
            },
        })

    def test_update04(self):
        """Update if index file newer than cache"""
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                },
            },
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (2000, 2000))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content.',
                },
            },
        })

    def test_update05(self):
        """Don't include if index file older than cache"""
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                },
            },
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (2000, 2000))
        os.utime(self.test_file, (1000, 1000))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy',
                },
            },
        })

    def test_update06(self):
        """Remove if id not in meta"""
        book = self.init_book(
            self.test_root,
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                },
            },
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update07(self):
        """Remove if meta[id] is None"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': None,
            },
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                },
            },
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update08(self):
        """Remove if item no index"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'title': 'Dummy',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                },
            },
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                },
            },
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update09(self):
        """Remove if item index is falsy"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '',
                    'title': 'Dummy',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                },
            },
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                },
            },
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update10(self):
        """Remove if index file not exist"""
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                },
            },
        )

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {})

    def test_update11(self):
        """Update subfile if not yet in cache.

        - As long as referred.
        - Even if mtime older than cache.
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                },
            },
        )
        linked_file = os.path.join(self.test_dir, 'linked.html')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="linked.html">link</a>
</body>
</html>
""")
        with open(linked_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (2000, 2000))
        os.utime(linked_file, (900, 900))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link',
                },
                'linked.html': {
                    'content': 'Linked page content.',
                },
            },
        })

    def test_update12(self):
        """Update subfile if mtime newer than cache

        - Even if no more referred by index file.
        - Even if index file not updating.
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                    'linked.html': {
                        'content': 'dummy2',
                    },
                },
            },
        )
        linked_file = os.path.join(self.test_dir, 'linked.html')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        with open(linked_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (900, 900))
        os.utime(linked_file, (2000, 2000))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy',
                },
                'linked.html': {
                    'content': 'Linked page content.',
                },
            },
        })

    def test_update13(self):
        """Don't update subfile if mtime older than cache

        - Even if no more referred by index file.
        - Even if index file not updating.
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                    'linked.html': {
                        'content': 'dummy2',
                    },
                },
            },
        )
        linked_file = os.path.join(self.test_dir, 'linked.html')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        with open(linked_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (900, 900))
        os.utime(linked_file, (800, 800))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy',
                },
                'linked.html': {
                    'content': 'dummy2',
                },
            },
        })

    def test_update14(self):
        """Remove subfile if no more exist

        - Even if index file not updating.
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                    'linked.html': {
                        'content': 'dummy2',
                    },
                },
            },
        )
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Page content.
</body>
</html>
""")
        os.utime(self.test_fulltext, (1000, 1000))
        os.utime(self.test_file, (900, 900))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy',
                },
            },
        })

    def test_update15(self):
        """Update subfiles if archive newer than cache
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta_htz(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy'
                    },
                    'linked_exist.html': {
                        'content': 'dummy2',
                    },
                    'linked_old.html': {
                        'content': 'dummy3',
                    },
                    'linked_nonexist.html': {
                        'content': 'dummy4',
                    },
                },
            },
        )
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

        t = datetime(2020, 2, 2, 0, 0, 0).timestamp()
        os.utime(self.test_fulltext, (t, t))
        t = datetime(2020, 3, 2, 0, 0, 0).timestamp()
        os.utime(archive_file, (t, t))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Page content. link1 link2 link3 link4',
                },
                'linked_added.html': {
                    'content': 'Linked page content 1.',
                },
                'linked_exist.html': {
                    'content': 'Linked page content 2.',
                },
                'linked_old.html': {
                    'content': 'dummy3',
                },
            },
        })

    def test_update16(self):
        """Don't update any subfiles if archive older than cache
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta_htz(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                    'linked_exist.html': {
                        'content': 'dummy2',
                    },
                    'linked_old.html': {
                        'content': 'dummy3',
                    },
                    'linked_nonexist.html': {
                        'content': 'dummy4',
                    },
                },
            },
        )
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

        t = datetime(2020, 2, 2, 0, 0, 0).timestamp()
        os.utime(self.test_fulltext, (t, t))
        t = datetime(2020, 1, 2, 0, 0, 0).timestamp()
        os.utime(archive_file, (t, t))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'dummy',
                },
                'linked_exist.html': {
                    'content': 'dummy2',
                },
                'linked_old.html': {
                    'content': 'dummy3',
                },
                'linked_nonexist.html': {
                    'content': 'dummy4',
                },
            },
        })

    def test_update17(self):
        """Treat as no file exists if archive corrupted
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta_htz(),
            fulltext={
                '20200101000000000': {
                    'index.html': {
                        'content': 'dummy',
                    },
                    'linked_exist.html': {
                        'content': 'dummy2',
                    },
                    'linked_old.html': {
                        'content': 'dummy3',
                    },
                    'linked_nonexist.html': {
                        'content': 'dummy4',
                    },
                },
            },
        )
        archive_file = os.path.join(self.test_root, '20200101000000000.htz')
        with open(archive_file, 'wb'):
            pass

        t = datetime(2020, 2, 2, 0, 0, 0).timestamp()
        os.utime(self.test_fulltext, (t, t))
        t = datetime(2020, 3, 2, 0, 0, 0).timestamp()
        os.utime(archive_file, (t, t))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {},
        })

    def test_update18(self):
        """Update all indexes for a MAFF if archive newer than cache
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta_maff(),
            fulltext={
                '20200101000000000': {
                    '20200101000000000/index.html': {
                        'content': 'dummy',
                    },
                    '20200101000000000/linked_exist.html': {
                        'content': 'dummy2',
                    },
                    '20200101000000000/linked_old.html': {
                        'content': 'dummy3',
                    },
                    '20200101000000000/linked_nonexist.html': {
                        'content': 'dummy4',
                    },
                },
            },
        )
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

        t = datetime(2020, 2, 2, 0, 0, 0).timestamp()
        os.utime(self.test_fulltext, (t, t))
        t = datetime(2020, 3, 2, 0, 0, 0).timestamp()
        os.utime(archive_file, (t, t))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                '20200101000000000/index.html': {
                    'content': 'Page content. link1 link2 link3 link4',
                },
                '20200101000000000/linked_added.html': {
                    'content': 'Linked page content 1.',
                },
                '20200101000000000/linked_exist.html': {
                    'content': 'Linked page content 2.',
                },
                '20200101000000000/linked_old.html': {
                    'content': 'dummy3',
                },
                '20200101000000001/index.html': {
                    'content': 'Page content 2.',
                },
            },
        })

    def test_update19(self):
        """Don't update any subfile for a MAFF if archive older than cache
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta_maff(),
            fulltext={
                '20200101000000000': {
                    '20200101000000000/index.html': {
                        'content': 'dummy',
                    },
                    '20200101000000000/linked_exist.html': {
                        'content': 'dummy2',
                    },
                    '20200101000000000/linked_old.html': {
                        'content': 'dummy3',
                    },
                    '20200101000000000/linked_nonexist.html': {
                        'content': 'dummy4',
                    },
                },
            },
        )
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

        t = datetime(2020, 2, 2, 0, 0, 0).timestamp()
        os.utime(self.test_fulltext, (t, t))
        t = datetime(2020, 1, 2, 0, 0, 0).timestamp()
        os.utime(archive_file, (t, t))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                '20200101000000000/index.html': {
                    'content': 'dummy',
                },
                '20200101000000000/linked_exist.html': {
                    'content': 'dummy2',
                },
                '20200101000000000/linked_old.html': {
                    'content': 'dummy3',
                },
                '20200101000000000/linked_nonexist.html': {
                    'content': 'dummy4',
                },
            },
        })

    def test_update20(self):
        """Treat as no file exists if MAFF archive corrupted
        """
        book = self.init_book(
            self.test_root,
            meta=self.general_meta_maff(),
            fulltext={
                '20200101000000000': {
                    '20200101000000000/index.html': {
                        'content': 'dummy',
                    },
                    '20200101000000000/linked_exist.html': {
                        'content': 'dummy2',
                    },
                    '20200101000000000/linked_old.html': {
                        'content': 'dummy3',
                    },
                    '20200101000000000/linked_nonexist.html': {
                        'content': 'dummy4',
                    },
                },
            },
        )
        archive_file = os.path.join(self.test_root, '20200101000000000.maff')
        with open(archive_file, 'w'):
            pass

        t = datetime(2020, 2, 2, 0, 0, 0).timestamp()
        os.utime(self.test_fulltext, (t, t))
        t = datetime(2020, 3, 2, 0, 0, 0).timestamp()
        os.utime(archive_file, (t, t))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {},
        })

    def test_update21(self):
        """Inline a frame with higher priority than cache as another page."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="iframe.html">link</a>
<iframe src="iframe.html">Frame label</iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link Iframe page content.',
                },
            },
        })

    def test_update22(self):
        """Inline a frame unless it's already cached as another page."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="linked.html">link1</a>
<a href="iframe.html">link2</a>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
<iframe src="iframe.html"></iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link1 link2',
                },
                'linked.html': {
                    'content': 'Linked page content. Iframe page content.',
                },
            },
        })

    def test_update23(self):
        """Inline a frame unless it's already cached as another page."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="iframe.html">link1</a>
<a href="linked.html">link2</a>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
<iframe src="iframe.html"></iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link1 link2',
                },
                'linked.html': {
                    'content': 'Linked page content.',
                },
                'iframe.html': {
                    'content': 'Iframe page content.',
                },
            },
        })

    def test_path01(self):
        """Don't include a path beyond directory of index
        """
        book = self.init_book(self.test_root, meta=self.general_meta())
        other_file = os.path.join(self.test_root, '20200101000000001', 'index.html')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="../20200101000000001/index.html">link</a>
</body>
</html>
""")
        os.makedirs(os.path.dirname(other_file))
        with open(other_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link',
                },
            },
        })

    def test_path02(self):
        """Include sibling files of single HTML.
        """
        book = self.init_book(self.test_root, meta=self.general_meta_singlehtml())
        test_file = os.path.join(self.test_root, '20200101000000000.html')
        other_file = os.path.join(self.test_root, '20200101000000001.html')
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="20200101000000001.html">link</a>
</body>
</html>
""")
        with open(other_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                '20200101000000000.html': {
                    'content': 'link',
                },
                '20200101000000001.html': {
                    'content': 'Linked page content.',
                },
            },
        })

    def test_path03(self):
        """Don't include external paths or self
        """
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link1 link2 link3 link4 link5',
                },
            },
        })

    def test_path04(self):
        """Test for a path with special chars
        """
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="ABC%E4%B8%AD%E6%96%87!%23%24%25%26%2B%2C%3B%3D%40%5B%5D%5E%60%7B%7D.html?id=1#123">link</a>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'ABC中文!#$%&+,;=@[]^`{}.html'), 'w', encoding='UTF-8') as fh:  # noqa: P103
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link',
                },
                'ABC中文!#$%&+,;=@[]^`{}.html': {  # noqa: P103
                    'content': 'Linked page content.',
                },
            },
        })

    def test_path05(self):
        """Test for a meta refresh path with special chars
        """
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<meta http-equiv="refresh" content="0;url=ABC%E4%B8%AD%E6%96%87!%23%24%25%26%2B%2C%3B%3D%40%5B%5D%5E%60%7B%7D.html?id=1#123">
</html>
""")
        with open(os.path.join(self.test_dir, 'ABC中文!#$%&+,;=@[]^`{}.html'), 'w', encoding='UTF-8') as fh:  # noqa: P103
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'ABC中文!#$%&+,;=@[]^`{}.html': {  # noqa: P103
                    'content': 'Linked page content.',
                },
            },
        })

    def test_path06(self):
        """Don't include links inside a data URL page
        """
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="data:text/html,frame%20%3Ca%20href%3D%22linked.html%22%3Elink%3C%2Fa%3E"></iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'frame link',
                },
            },
        })

    def test_html_empty(self):
        """Generate an empty cache for an empty HTML (without error)."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'wb'):
            pass

        generator = wsb_cache.FulltextCacheGenerator(book)
        for info in generator.run():
            self.assertNotEqual(info.type, 'error')

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
            },
        })

    def test_html_charset01(self):
        """Detect charset from BOM. (UTF-16-LE)"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'wb') as fh:
            fh.write(b'\xff\xfe')
            fh.write("""<!DOCTYPE html>
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文',
                },
            },
        })

    def test_html_charset02(self):
        """Detect charset from BOM. (UTF-16-BE)"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'wb') as fh:
            fh.write(b'\xfe\xff')
            fh.write("""<!DOCTYPE html>
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文',
                },
            },
        })

    def test_html_charset03(self):
        """Get charset from meta[charset] if no BOM."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='big5') as fh:
            fh.write("""<!DOCTYPE html>
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文',
                },
            },
        })

    def test_html_charset04(self):
        """Get charset from meta[http-equiv="content-type"] if no BOM."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='big5') as fh:
            fh.write("""<!DOCTYPE html>
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文',
                },
            },
        })

    def test_html_charset05(self):
        """Get charset from item charset if no BOM or meta."""
        book = self.init_book(self.test_root, meta=self.general_meta_charset_big5())
        with open(self.test_file, 'w', encoding='big5') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
English
中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文',
                },
            },
        })

    def test_html_charset06(self):
        """Fallback to UTF-8 if no BOM, meta, or item charset."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
English
中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'English 中文',
                },
            },
        })

    def test_html_charset07(self):
        """Fix certain charsets of the web page."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='cp950') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=big5">
</head>
<body>
碁銹裏墻恒粧嫺
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '碁銹裏墻恒粧嫺',
                },
            },
        })

    def test_html_elems(self):
        """Text in certain HTML tags should not be cached."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>title text</title>
<style>/* style text */</style>
<script>/* script text */</script>
</head>
<body>
before paragraph <p>paragraph text</p> after paragraph

before template <template>template text<div>element</div> more text</template> after template

before iframe <iframe>iframe text</iframe> after iframe

before object <object>object text</object> after object
before applet <applet>applet text</applet> after applet

before audio <audio>audio text</audio> after audio
before video <video>video text</video> after video
before canvas <canvas>canvas text</canvas> after canvas

before noframes <noframes>noframes text</noframes> after noframes
before noscript <noscript>noscript text</noscript> after noscript
before noembed <noembed>noembed text</noembed> after noembed

before textarea <textarea>textarea text</textarea> after textarea

before svg <svg><text>svg text</text></svg> after svg
before math <math><mtext>math text</mtext></math> after math
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': (
                        """before paragraph paragraph text after paragraph """
                        """before template after template """
                        """before iframe after iframe """
                        """before object after object """
                        """before applet after applet """
                        """before audio after audio """
                        """before video after video """
                        """before canvas after canvas """
                        """before noframes after noframes """
                        """before noscript after noscript """
                        """before noembed after noembed """
                        """before textarea after textarea """
                        """before svg after svg """
                        """before math after math"""
                    ),
                },
            },
        })

    def test_xhtml_elems(self):
        """Text in certain HTML tags should not be cached."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        xhtml_file = os.path.join(self.test_dir, 'index.xhtml')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=index.xhtml">
""")
        with open(xhtml_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8"/>
<title>title text</title>
<style>/* style text */</style>
<script>/* script text */</script>
</head>
<body>
before paragraph <p>paragraph text</p> after paragraph

before template <template>template text<div>element</div> more text</template> after template

before iframe <iframe>iframe text</iframe> after iframe

before object <object>object text</object> after object
before applet <applet>applet text</applet> after applet

before audio <audio>audio text</audio> after audio
before video <video>video text</video> after video
before canvas <canvas>canvas text</canvas> after canvas

before noframes <noframes>noframes text</noframes> after noframes
before noscript <noscript>noscript text</noscript> after noscript
before noembed <noembed>noembed text</noembed> after noembed

before textarea <textarea>textarea text</textarea> after textarea

before svg <svg><text>svg text</text></svg> after svg
before math <math><mtext>math text</mtext></math> after math
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'index.xhtml': {
                    'content': (
                        """before paragraph paragraph text after paragraph """
                        """before template after template """
                        """before iframe after iframe """
                        """before object after object """
                        """before applet after applet """
                        """before audio after audio """
                        """before video after video """
                        """before canvas after canvas """
                        """before noframes after noframes """
                        """before noscript after noscript """
                        """before noembed after noembed """
                        """before textarea after textarea """
                        """before svg after svg """
                        """before math after math"""
                    ),
                },
            },
        })

    def test_xhtml_malformed(self):
        """lxml seems to work for malformed XHTML"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        xhtml_file = os.path.join(self.test_dir, 'index.xhtml')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=index.xhtml">
""")
        with open(xhtml_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'index.xhtml': {
                    'content': 'first line second line paragraph',
                },
            },
        })

    def test_html_iframe01(self):
        """Include iframe content in index page"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="iframe.html">Frame label 中文</iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content. 中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Iframe page content. 中文',
                },
            },
        })

    def test_html_iframe02(self):
        """Treat iframe content as another page if specified"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="iframe.html">Frame label 中文</iframe>
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'iframe.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Iframe page content. 中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book, inclusive_frames=False)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'iframe.html': {
                    'content': 'Iframe page content. 中文',
                },
            },
        })

    def test_html_iframe_datauri01(self):
        """Include data URL content"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="data:text/plain;base64,QUJDMTIz5Lit5paH">Frame label 中文</iframe>
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文',
                },
            },
        })

    def test_html_iframe_datauri02(self):
        """Include data URL content, regardless of inclusion mode"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="data:text/plain;base64,QUJDMTIz5Lit5paH">Frame label 中文</iframe>
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文'
                },
            }
        })

    def test_html_iframe_srcdoc01(self):
        """Include srcdoc content"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        linked_file = os.path.join(self.test_dir, 'linked.html')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<iframe src="data:text/plain;base64,QUJDMTIz5Lit5paH" srcdoc="XYZ987<a href=&quot;linked.html&quot;>中文</a>">Frame label 中文</iframe>
</body>
</html>
""")
        with open(linked_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content.
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'XYZ987 中文',
                },
                'linked.html': {
                    'content': 'Linked page content.',
                },
            },
        })

    def test_html_frame01(self):
        """Include frame content in index page"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<frameset cols="*,*">
<frame name="toc" src="frame1.html"></frame>
<frame name="main" src="frame2.html"></frame>
</frameset>
</html>
""")
        with open(os.path.join(self.test_dir, 'frame1.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Frame page content 1.
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'frame2.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Frame page content 1. 中文',
                },
            },
        })

    def test_html_frame02(self):
        """Treat frame content as another page if specified"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<frameset cols="*,*">
<frame name="toc" src="frame1.html"></frame>
<frame name="main" src="frame2.html"></frame>
</frameset>
</html>
""")
        with open(os.path.join(self.test_dir, 'frame1.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Frame page content 1.
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'frame2.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book, inclusive_frames=False)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'frame1.html': {
                    'content': 'Frame page content 1.',
                },
                'frame2.html': {
                    'content': '中文',
                },
            },
        })

    def test_html_frame_datauri01(self):
        """Include data URL content"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<frameset cols="*,*">
<frame name="toc" src="data:text/plain,ABC123%E4%B8%AD%E6%96%87"></frame>
<frame name="main" src="data:text/plain;base64,QUJDMTIz5Lit5paH"></frame>
</frameset>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 ABC123中文',
                },
            },
        })

    def test_html_frame_datauri02(self):
        """Include data URL content, regardless of inclusion mode"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<frameset cols="*,*">
<frame name="toc" src="data:text/plain,ABC123%E4%B8%AD%E6%96%87"></frame>
<frame name="main" src="data:text/plain;base64,QUJDMTIz5Lit5paH"></frame>
</frameset>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 ABC123中文',
                },
            },
        })

    def test_html_refresh01(self):
        """Don't cache content for a page with an instant meta refresh"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
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
        with open(os.path.join(self.test_dir, 'refreshed1.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 1. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed2.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 2. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed3.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 3. 中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'refreshed1.html': {
                    'content': 'Refreshed page content 1. 中文',
                },
                'refreshed2.html': {
                    'content': 'Refreshed page content 2. 中文',
                },
                'refreshed3.html': {
                    'content': 'Refreshed page content 3. 中文',
                },
            },
        })

    def test_html_refresh02(self):
        """Cache content for a page without an instant meta refresh"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
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
        with open(os.path.join(self.test_dir, 'refreshed1.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 1. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed2.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 2. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'refreshed3.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Refreshed page content 3. 中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'Main page content.',
                },
                'refreshed1.html': {
                    'content': 'Refreshed page content 1. 中文',
                },
                'refreshed2.html': {
                    'content': 'Refreshed page content 2. 中文',
                },
                'refreshed3.html': {
                    'content': 'Refreshed page content 3. 中文',
                },
            },
        })

    def test_html_refresh_datauri01(self):
        """Include all refresh target data URL pages, regardless of refresh time"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 ABC123中文',
                },
            },
        })

    def test_html_refresh_datauri02(self):
        """Include all refresh target data URL pages, regardless of refresh time"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 ABC123中文 Main page content.',
                },
            },
        })

    def test_html_link(self):
        """Cache linked pages"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="linked.html">link 中文</a>
<area href="linked2.html">
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content. 中文
</body>
</html>
""")
        with open(os.path.join(self.test_dir, 'linked2.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
Linked page content 2. 中文
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link 中文',
                },
                'linked.html': {
                    'content': 'Linked page content. 中文',
                },
                'linked2.html': {
                    'content': 'Linked page content 2. 中文',
                },
            },
        })

    def test_html_link_datauri(self):
        """Include linked data URL pages"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="data:text/plain,ABC123%E4%B8%AD%E6%96%87">link 中文</a>
<area href="data:text/plain;base64,QUJDMTIz5Lit5paH">
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'ABC123中文 link 中文 ABC123中文',
                },
            },
        })

    def test_text_charset01(self):
        """Detect charset from BOM. (UTF-16-LE)"""
        book = self.init_book(self.test_root, meta=self.general_meta_charset_big5())
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'wb') as fh:
            fh.write(b'\xff\xfe')
            fh.write("""中文""".encode('UTF-16-LE'))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'file.txt': {
                    'content': '中文',
                },
            },
        })

    def test_text_charset02(self):
        """Detect charset from BOM. (UTF-16-BE)"""
        book = self.init_book(self.test_root, meta=self.general_meta_charset_big5())
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'wb') as fh:
            fh.write(b'\xfe\xff')
            fh.write("""中文""".encode('UTF-16-BE'))

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'file.txt': {
                    'content': '中文',
                },
            },
        })

    def test_text_charset03(self):
        """Use item charset if no BOM."""
        book = self.init_book(self.test_root, meta=self.general_meta_charset_big5())
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'w', encoding='big5') as fh:
            fh.write("""\
Text file content
中文
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'file.txt': {
                    'content': 'Text file content 中文',
                },
            },
        })

    def test_text_charset04(self):
        """Fallback to UTF-8 if no BOM or item charset."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'w', encoding='UTF-8') as fh:
            fh.write("""\
Text file content
中文
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'file.txt': {
                    'content': 'Text file content 中文',
                },
            },
        })

    def test_text_charset05(self):
        """Certain charsets of the web page need fix."""
        book = self.init_book(self.test_root, meta=self.general_meta_charset_big5())
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'w', encoding='cp950') as fh:
            fh.write("""碁銹裏墻恒粧嫺""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'file.txt': {
                    'content': '碁銹裏墻恒粧嫺',
                },
            },
        })

    def test_text_charset06(self):
        """Wrong encoding produces gibberish, but won't fail out."""
        book = self.init_book(self.test_root, meta=self.general_meta_charset_big5())
        text_file = os.path.join(self.test_root, '20200101000000000', 'file.txt')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=file.txt">
""")
        with open(text_file, 'w', encoding='UTF-8') as fh:
            fh.write("""Text file content 中文""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
                'file.txt': {
                    'content': 'Text file content 銝剜��',
                },
            },
        })

    def test_binary(self):
        """Don't include binary in cache"""
        book = self.init_book(self.test_root, meta=self.general_meta())
        bin_file = os.path.join(self.test_root, '20200101000000000', 'image.jpg')
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<meta http-equiv="refresh" content="0;url=image.jpg">
""")
        with open(bin_file, 'wb') as fh:
            pass

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': '',
                },
            },
        })

    def test_datauri_html(self):
        """Cache HTML files."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="data:text/html,<b>test</b>">link1</a>
<a href="data:application/xhtml+xml,<b>test</b>">link2</a>
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'test link1 test link2',
                },
            },
        })

    def test_datauri_text(self):
        """Cache text files only."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
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

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
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
                    ),
                },
            },
        })

    def test_datauri_malformed(self):
        """Skip caching data of a malformed data URL."""
        book = self.init_book(self.test_root, meta=self.general_meta())
        with open(self.test_file, 'w', encoding='UTF-8') as fh:
            fh.write("""<!DOCTYPE html>
<html>
<body>
<a href="data:text/html;base64,wtf">link</a>
</body>
</html>
""")

        generator = wsb_cache.FulltextCacheGenerator(book)
        for _info in generator.run():
            pass

        self.assertEqual(book.fulltext, {
            '20200101000000000': {
                'index.html': {
                    'content': 'link',
                },
            },
        })


class TestStaticSiteGenerator(TestCache):
    def test_update01(self):
        """Create nonexisting files"""
        check_files = [
            'icon/toggle.png',
            'icon/search.png',
            'icon/collapse.png',
            'icon/expand.png',
            'icon/external.png',
            'icon/item.png',
            'icon/fclose.png',
            'icon/fopen.png',
            'icon/file.png',
            'icon/note.png',
            'icon/postit.png',
            'index.html',
            'map.html',
            'frame.html',
            'search.html',
        ]

        book = self.init_book(self.test_root)
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        orig_stats = {}
        for path in check_files:
            with self.subTest(path=path):
                file = os.path.normpath(os.path.join(self.test_tree, path))
                self.assertTrue(os.path.exists(file))
                orig_stats[file] = os.stat(file)

        # generate again, all existed files should be unchanged
        book = self.init_book(self.test_root)
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        for path in check_files:
            with self.subTest(path=path):
                file = os.path.normpath(os.path.join(self.test_tree, path))
                self.assertEqual(os.stat(file).st_mtime, orig_stats[file].st_mtime)
                self.assertEqual(os.stat(file).st_size, orig_stats[file].st_size)

    def test_update02(self):
        """Overwrite existing different files"""
        check_files = [
            'icon/toggle.png',
            'icon/search.png',
            'icon/collapse.png',
            'icon/expand.png',
            'icon/external.png',
            'icon/item.png',
            'icon/fclose.png',
            'icon/fopen.png',
            'icon/file.png',
            'icon/note.png',
            'icon/postit.png',
            'index.html',
            'map.html',
            'frame.html',
            'search.html',
        ]

        os.makedirs(os.path.join(self.test_tree, 'icon'))
        orig_stats = {}
        for path in check_files:
            file = os.path.normpath(os.path.join(self.test_tree, path))
            with open(file, 'wb'):
                pass
            os.utime(file, (0, 0))
            orig_stats[file] = os.stat(file)

        book = self.init_book(self.test_root)
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        for path in check_files:
            with self.subTest(path=path):
                file = os.path.normpath(os.path.join(self.test_tree, path))
                self.assertNotEqual(os.stat(file).st_mtime, orig_stats[file].st_mtime)
                self.assertNotEqual(os.stat(file).st_size, orig_stats[file].st_size)

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_config_filepaths(self, mock_func):
        """Check if special chars in the path are correctly handled."""
        book = self.init_book(self.test_root, config="""\
[book ""]
top_dir = #top
data_dir = data%中文
tree_dir = tree 中文
index = tree%20%E4%B8%AD%E6%96%87/my%20index.html?id=1#myfrag
""")
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list[0][0], ('index.html', 'static_index.html'))
        self.assertEqual(mock_func.call_args_list[0][1]['data_dir'], '../data%25%E4%B8%AD%E6%96%87/')

        self.assertEqual(mock_func.call_args_list[1][0], ('map.html', 'static_map.html'))
        self.assertEqual(mock_func.call_args_list[1][1]['data_dir'], '../data%25%E4%B8%AD%E6%96%87/')

        self.assertEqual(mock_func.call_args_list[3][0], ('search.html', 'static_search.html'))
        self.assertEqual(mock_func.call_args_list[3][1]['path'], '../')
        self.assertEqual(mock_func.call_args_list[3][1]['data_dir'], 'data%25%E4%B8%AD%E6%96%87/')
        self.assertEqual(mock_func.call_args_list[3][1]['tree_dir'], 'tree%20%E4%B8%AD%E6%96%87/')
        self.assertEqual(mock_func.call_args_list[3][1]['index'], 'tree%20%E4%B8%AD%E6%96%87/my%20index.html?id=1#myfrag')

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_param_static_index01(self, mock_func):
        """Check if params are passed correctly."""
        book = self.init_book(self.test_root)
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list[0][0], ('index.html', 'static_index.html'))
        self.assertEqual(mock_func.call_args_list[0][1]['filename'], 'index')
        self.assertIsInstance(mock_func.call_args_list[0][1]['static_index'], collections.abc.Generator)

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_param_static_index02(self, mock_func):
        """Check if params are passed correctly."""
        book = self.init_book(self.test_root)
        generator = wsb_cache.StaticSiteGenerator(book, static_index=False)
        for _info in generator.run():
            pass

        for i, call in enumerate(mock_func.call_args_list):
            with self.subTest(i=i, file=call[0][0]):
                self.assertNotEqual(call[0][0], 'index.html')
        self.assertEqual(mock_func.call_args_list[0][0], ('map.html', 'static_map.html'))
        self.assertEqual(mock_func.call_args_list[0][1]['filename'], 'map')
        self.assertIsNone(mock_func.call_args_list[0][1]['static_index'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_param_rss01(self, mock_func):
        """rss should be passed."""
        book = self.init_book(self.test_root)
        generator = wsb_cache.StaticSiteGenerator(book, rss=True)
        for _info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list[0][0], ('map.html', 'static_map.html'))
        self.assertTrue(mock_func.call_args_list[0][1]['rss'])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page')
    def test_param_rss02(self, mock_func):
        """rss should be passed."""
        book = self.init_book(self.test_root)
        generator = wsb_cache.StaticSiteGenerator(book, rss=False)
        for _info in generator.run():
            pass

        self.assertEqual(mock_func.call_args_list[0][0], ('map.html', 'static_map.html'))
        self.assertFalse(mock_func.call_args_list[0][1]['rss'])

    def test_param_locale01(self):
        """locale should be passed."""
        book = self.init_book(self.test_root)
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True, locale='ar')
        for _info in generator.run():
            pass

        self.assertEqual(generator.template_env.globals['i18n'].lang, 'ar')

    def test_param_locale02(self):
        """Take config if locale not specified."""
        book = self.init_book(self.test_root, config="""\
[app]
locale = he
""")
        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(generator.template_env.globals['i18n'].lang, 'he')

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor01(self, mock_gen):
        """Page with index */index.html"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index#1.html',
                    'type': '',
                    'source': 'http://example.com:8888',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000/index%231.html', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000/index%231.html', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor02(self, mock_gen):
        """Page with index *.maff"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000#1.maff',
                    'type': '',
                    'source': 'http://example.com:8888',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000%231.maff', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000%231.maff', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor03(self, mock_gen):
        """Page with index *.html"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000#1.html',
                    'type': '',
                    'source': 'http://example.com:8888',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000%231.html', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000%231.html', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor04(self, mock_gen):
        """Page with empty index"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '',
                    'type': '',
                    'source': 'http://example.com:8888',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor05(self, mock_gen):
        """Page without index"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'source': 'http://example.com:8888',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='http://example.com:8888', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor06(self, mock_gen):
        """Bookmark with source"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': 'bookmark',
                    'source': 'http://example.com:8888/%231',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='bookmark', marked='', title='20200101000000000',
                url='http://example.com:8888/%231', icon='',
                source='http://example.com:8888/%231', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='bookmark', marked='', title='20200101000000000',
                url='http://example.com:8888/%231', icon='',
                source='http://example.com:8888/%231', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor07(self, mock_gen):
        """Bookmark without source and with index"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000#1.htm',
                    'type': 'bookmark',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='bookmark', marked='', title='20200101000000000',
                url='../../20200101000000000%231.htm', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='bookmark', marked='', title='20200101000000000',
                url='../../20200101000000000%231.htm', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor08(self, mock_gen):
        """Bookmark without source and index"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': 'bookmark',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='bookmark', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='bookmark', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_anchor09(self, mock_gen):
        """Folder should not have href anyway"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index#1.html',
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='folder', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='folder', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_icon01(self, mock_gen):
        """Icon with absolute path."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000/index.html',
                    'icon': 'http://example.com/favicon%231.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000/index.html', icon='http://example.com/favicon%231.ico',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000/index.html', icon='http://example.com/favicon%231.ico',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_icon02(self, mock_gen):
        """Icon with index */index.html"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000/index.html',
                    'icon': 'favicon%231.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000/index.html', icon='../../20200101000000000/favicon%231.ico',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000/index.html', icon='../../20200101000000000/favicon%231.ico',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_icon03(self, mock_gen):
        """Icon with index *.maff"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000.maff',
                    'icon': '.wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000.maff',
                icon='../../.wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='../../20200101000000000.maff',
                icon='../../.wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_icon04(self, mock_gen):
        """Icon with no index"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'icon': '.wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='',
                icon='../../.wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='',
                icon='../../.wsb/tree/favicon/0123456789abcdef0123456789abcdef01234567.ico',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_icon05(self, mock_gen):
        """Default icon (empty icon)"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'icon': '',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_icon06(self, mock_gen):
        """Default icon (no icon)"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_title01(self, mock_gen):
        """Item without title (use ID)."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='20200101000000000',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_title02(self, mock_gen):
        """Item with title."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'title': 'My title 中文',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='', marked='', title='My title 中文',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='', marked='', title='My title 中文',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_title03(self, mock_gen):
        """Separator without title."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': 'separator',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='separator', marked='', title='',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='separator', marked='', title='',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])

    @mock.patch('webscrapbook.scrapbook.cache.StaticSiteGenerator._generate_page',
                return_value=iter(()))
    def test_static_index_title04(self, mock_gen):
        """Separator with title."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': 'separator',
                    'title': 'My sep 中文',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        generator = wsb_cache.StaticSiteGenerator(book, static_index=True)
        for _info in generator.run():
            pass

        self.assertEqual(list(mock_gen.call_args_list[0][1]['static_index']), [
            wsb_cache.StaticIndexItem(
                event='start-container', level=0),
            wsb_cache.StaticIndexItem(
                event='start', level=1, id='20200101000000000',
                type='separator', marked='', title='My sep 中文',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end', level=1, id='20200101000000000',
                type='separator', marked='', title='My sep 中文',
                url='', icon='',
                source='', comment=''),
            wsb_cache.StaticIndexItem(
                event='end-container', level=0),
        ])


class TestRssFeedGenerator(TestCache):
    def test_basic(self):
        """A basic test case."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000100000': {
                    'index': '20200101000100000/index.html',
                    'title': 'Title 中文 1',
                    'type': '',
                    'create': '20200101000001000',
                    'modify': '20200101000100000',
                },
                '20200101000200000': {
                    'index': '20200101000200000.htz',
                    'title': 'Title 中文 2',
                    'type': '',
                    'create': '20200101000002000',
                    'modify': '20200101000200000',
                },
                '20200101000300000': {
                    'index': '20200101000300000.maff',
                    'title': 'Title 中文 3',
                    'type': '',
                    'create': '20200101000003000',
                    'modify': '20200101000300000',
                },
                '20200101000400000': {
                    'index': '20200101000400000.html',
                    'title': 'Title 中文 4',
                    'type': '',
                    'create': '20200101000004000',
                    'modify': '20200101000400000',
                },
                '20200101000500000': {
                    'title': 'Title 中文 5',
                    'type': 'bookmark',
                    'create': '20200101000005000',
                    'modify': '20200101000500000',
                    'source': 'http://example.com',
                },
            },
        )

        generator = wsb_cache.RssFeedGenerator(book, rss_root='http://example.com/wsb')
        for _info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'feed.atom'), encoding='UTF-8') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            etree.tostring(tree, encoding='unicode', pretty_print=True),
            """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:webscrapbook:example.com/wsb</id>
  <link rel="self" href="http://example.com/wsb/.wsb/tree/feed.atom"/>
  <link href="http://example.com/wsb/.wsb/tree/map.html"/>
  <title type="text">scrapbook</title>
  <updated>2020-01-01T00:05:00Z</updated>
  <entry>
    <id>urn:webscrapbook:example.com/wsb:20200101000500000</id>
    <link href="http://example.com"/>
    <title type="text">Title 中文 5</title>
    <published>2020-01-01T00:00:05Z</published>
    <updated>2020-01-01T00:05:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com/wsb:20200101000400000</id>
    <link href="http://example.com/wsb/20200101000400000.html"/>
    <title type="text">Title 中文 4</title>
    <published>2020-01-01T00:00:04Z</published>
    <updated>2020-01-01T00:04:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com/wsb:20200101000300000</id>
    <link href="http://example.com/wsb/20200101000300000.maff"/>
    <title type="text">Title 中文 3</title>
    <published>2020-01-01T00:00:03Z</published>
    <updated>2020-01-01T00:03:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com/wsb:20200101000200000</id>
    <link href="http://example.com/wsb/20200101000200000.htz"/>
    <title type="text">Title 中文 2</title>
    <published>2020-01-01T00:00:02Z</published>
    <updated>2020-01-01T00:02:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com/wsb:20200101000100000</id>
    <link href="http://example.com/wsb/20200101000100000/index.html"/>
    <title type="text">Title 中文 1</title>
    <published>2020-01-01T00:00:01Z</published>
    <updated>2020-01-01T00:01:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
</feed>
"""
        )

    def test_same_modify(self):
        """Latter item goes first if same modify time."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000100000': {
                    'index': '20200101000100000/index.html',
                    'title': 'Title 中文 1',
                    'type': '',
                    'create': '20200101000001000',
                    'modify': '20200102000000000',
                },
                '20200101000200000': {
                    'index': '20200101000200000.htz',
                    'title': 'Title 中文 2',
                    'type': '',
                    'create': '20200101000002000',
                    'modify': '20200102000000000',
                },
                '20200101000300000': {
                    'index': '20200101000300000.maff',
                    'title': 'Title 中文 3',
                    'type': '',
                    'create': '20200101000003000',
                    'modify': '20200102000000000',
                },
            },
        )

        generator = wsb_cache.RssFeedGenerator(book, rss_root='http://example.com')
        for _info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'feed.atom'), encoding='UTF-8') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            etree.tostring(tree, encoding='unicode', pretty_print=True),
            """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:webscrapbook:example.com</id>
  <link rel="self" href="http://example.com/.wsb/tree/feed.atom"/>
  <link href="http://example.com/.wsb/tree/map.html"/>
  <title type="text">scrapbook</title>
  <updated>2020-01-02T00:00:00Z</updated>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000300000</id>
    <link href="http://example.com/20200101000300000.maff"/>
    <title type="text">Title 中文 3</title>
    <published>2020-01-01T00:00:03Z</published>
    <updated>2020-01-02T00:00:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000200000</id>
    <link href="http://example.com/20200101000200000.htz"/>
    <title type="text">Title 中文 2</title>
    <published>2020-01-01T00:00:02Z</published>
    <updated>2020-01-02T00:00:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000100000</id>
    <link href="http://example.com/20200101000100000/index.html"/>
    <title type="text">Title 中文 1</title>
    <published>2020-01-01T00:00:01Z</published>
    <updated>2020-01-02T00:00:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
</feed>
"""
        )

    def test_param_item_count(self):
        """Check item_count param."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000100000': {
                    'index': '20200101000100000/index.html',
                    'title': 'Title 中文 1',
                    'type': '',
                    'create': '20200101000001000',
                    'modify': '20200101000100000',
                },
                '20200101000200000': {
                    'index': '20200101000200000.htz',
                    'title': 'Title 中文 2',
                    'type': '',
                    'create': '20200101000002000',
                    'modify': '20200101000200000',
                },
                '20200101000300000': {
                    'index': '20200101000300000.maff',
                    'title': 'Title 中文 3',
                    'type': '',
                    'create': '20200101000003000',
                    'modify': '20200101000300000',
                },
                '20200101000400000': {
                    'index': '20200101000400000.html',
                    'title': 'Title 中文 4',
                    'type': '',
                    'create': '20200101000004000',
                    'modify': '20200101000400000',
                },
                '20200101000500000': {
                    'title': 'Title 中文 5',
                    'type': 'bookmark',
                    'create': '20200101000005000',
                    'modify': '20200101000500000',
                    'source': 'http://example.com',
                },
            },
        )

        generator = wsb_cache.RssFeedGenerator(book, rss_root='http://example.com', item_count=3)
        for _info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'feed.atom'), encoding='UTF-8') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            etree.tostring(tree, encoding='unicode', pretty_print=True),
            """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:webscrapbook:example.com</id>
  <link rel="self" href="http://example.com/.wsb/tree/feed.atom"/>
  <link href="http://example.com/.wsb/tree/map.html"/>
  <title type="text">scrapbook</title>
  <updated>2020-01-01T00:05:00Z</updated>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000500000</id>
    <link href="http://example.com"/>
    <title type="text">Title 中文 5</title>
    <published>2020-01-01T00:00:05Z</published>
    <updated>2020-01-01T00:05:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000400000</id>
    <link href="http://example.com/20200101000400000.html"/>
    <title type="text">Title 中文 4</title>
    <published>2020-01-01T00:00:04Z</published>
    <updated>2020-01-01T00:04:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000300000</id>
    <link href="http://example.com/20200101000300000.maff"/>
    <title type="text">Title 中文 3</title>
    <published>2020-01-01T00:00:03Z</published>
    <updated>2020-01-01T00:03:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
</feed>
"""
        )

    def test_empty(self):
        """Include only items with index or bookmark with source.

        - Empty feed should use current time as update time.
        """
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000100000': {
                    'title': 'Title 中文 1',
                    'type': '',
                    'create': '20200101000001000',
                    'modify': '20200101000100000',
                },
                '20200101000200000': {
                    'index': '20200101000200000.htz',
                    'title': 'Title 中文 2',
                    'type': 'folder',
                    'create': '20200101000002000',
                    'modify': '20200101000200000',
                },
                '20200101000300000': {
                    'index': '20200101000300000.maff',
                    'title': 'Title 中文 3',
                    'type': 'separator',
                    'create': '20200101000003000',
                    'modify': '20200101000300000',
                },
                '20200101000400000': {
                    'index': '20200101000400000.html',
                    'title': 'Title 中文 4',
                    'type': 'bookmark',
                    'create': '20200101000004000',
                    'modify': '20200101000400000',
                },
            },
        )

        generator = wsb_cache.RssFeedGenerator(book, rss_root='http://example.com')
        for _info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'feed.atom'), encoding='UTF-8') as fh:
            tree = etree.parse(fh)

        NS = '{http://www.w3.org/2005/Atom}'  # noqa: N806
        updated = tree.find(f'/{NS}updated').text
        ts = datetime.strptime(updated, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        self.assertAlmostEqual(
            ts.timestamp(),
            datetime.now(timezone.utc).timestamp(),
            delta=3,
        )

        self.assertEqual(
            etree.tostring(tree, encoding='unicode', pretty_print=True),
            f"""\
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:webscrapbook:example.com</id>
  <link rel="self" href="http://example.com/.wsb/tree/feed.atom"/>
  <link href="http://example.com/.wsb/tree/map.html"/>
  <title type="text">scrapbook</title>
  <updated>{updated}</updated>
</feed>
"""
        )

    def test_item_create(self):
        """Item missing create property uses epoch=0"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000100000': {
                    'title': 'Title 中文 1',
                    'type': 'bookmark',
                    'create': '',
                    'modify': '20200101000100000',
                    'source': 'http://example.com',
                },
            },
        )

        generator = wsb_cache.RssFeedGenerator(book, rss_root='http://example.com')
        for _info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'feed.atom'), encoding='UTF-8') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            etree.tostring(tree, encoding='unicode', pretty_print=True),
            """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:webscrapbook:example.com</id>
  <link rel="self" href="http://example.com/.wsb/tree/feed.atom"/>
  <link href="http://example.com/.wsb/tree/map.html"/>
  <title type="text">scrapbook</title>
  <updated>2020-01-01T00:01:00Z</updated>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000100000</id>
    <link href="http://example.com"/>
    <title type="text">Title 中文 1</title>
    <published>1970-01-01T00:00:00Z</published>
    <updated>2020-01-01T00:01:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
</feed>
"""
        )

    def test_item_modify(self):
        """Item missing modify property infers from create and epoch=0"""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000100000': {
                    'title': 'Title 中文 1',
                    'type': 'bookmark',
                    'create': '20200101000100000',
                    'source': 'http://example.com',
                },
                '20200101000200000': {
                    'title': 'Title 中文 2',
                    'type': 'bookmark',
                    'source': 'http://example.com:8000',
                },
            },
        )

        generator = wsb_cache.RssFeedGenerator(book, rss_root='http://example.com')
        for _info in generator.run():
            pass

        with open(os.path.join(self.test_tree, 'feed.atom'), encoding='UTF-8') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            etree.tostring(tree, encoding='unicode', pretty_print=True),
            """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:webscrapbook:example.com</id>
  <link rel="self" href="http://example.com/.wsb/tree/feed.atom"/>
  <link href="http://example.com/.wsb/tree/map.html"/>
  <title type="text">scrapbook</title>
  <updated>2020-01-01T00:01:00Z</updated>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000100000</id>
    <link href="http://example.com"/>
    <title type="text">Title 中文 1</title>
    <published>2020-01-01T00:01:00Z</published>
    <updated>2020-01-01T00:01:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
  <entry>
    <id>urn:webscrapbook:example.com:20200101000200000</id>
    <link href="http://example.com:8000"/>
    <title type="text">Title 中文 2</title>
    <published>1970-01-01T00:00:00Z</published>
    <updated>1970-01-01T00:00:00Z</updated>
    <author>
      <name>Anonymous</name>
    </author>
  </entry>
</feed>
"""
        )


if __name__ == '__main__':
    unittest.main()
