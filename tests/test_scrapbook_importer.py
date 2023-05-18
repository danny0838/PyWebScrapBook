import io
import json
import os
import tempfile
import unittest
from base64 import b64decode
from unittest import mock

from webscrapbook import WSB_DIR
from webscrapbook._polyfill import zipfile
from webscrapbook.scrapbook import importer as wsb_importer
from webscrapbook.scrapbook.host import Host

from . import TEMP_DIR, TestBookMixin, glob_files


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='importer-', dir=TEMP_DIR)
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


class TestImporter(TestBookMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder"""
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_input = os.path.join(self.test_root, 'input')
        self.test_output = os.path.join(self.test_root, 'output')
        self.test_output_tree = os.path.join(self.test_output, WSB_DIR, 'tree')

        os.makedirs(self.test_input, exist_ok=True)
        os.makedirs(self.test_output_tree, exist_ok=True)

    def general_config_new_at_top(self):
        return """\
[book ""]
new_at_top = true
"""

    def test_basic01(self):
        """Test importing a common */index.html"""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')
            zh.writestr('data/20200101000000001/favicon.bmp',
                        b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')
        with open(os.path.join(self.test_output, '20200101000000001', 'favicon.bmp'), 'rb') as fh:
            self.assertEqual(fh.read(), b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

    def test_basic02(self):
        """Test importing a common *.htz

        - Favicon should be imported and icon property should be consistent with the book.
        """
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zh:
            zh.writestr('index.html', 'page content')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '../tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            }))
            zh.writestr('data/20200101000000001.htz', buf.getvalue())
            zh.writestr('favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                        b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })
        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000001.htz')) as zh:
            self.assertEqual(zh.read('index.html').decode('UTF-8'), 'page content')
        with open(os.path.join(self.test_output_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'), 'rb') as fh:
            self.assertEqual(fh.read(), b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

    def test_basic03(self):
        """Test importing a common no-index item.

        - Favicon should be imported and icon property should be consistent with the book.
        """
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': 'bookmark',
                'index': '',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '../tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            }))
            zh.writestr('favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                        b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': 'bookmark',
                'index': '',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })
        with open(os.path.join(self.test_output_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'), 'rb') as fh:
            self.assertEqual(fh.read(), b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

    def test_basic04(self):
        """Test importing */index.html with cached favicon"""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '../../tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')
            zh.writestr('favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                        b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '../.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')
        with open(os.path.join(self.test_output_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'), 'rb') as fh:
            self.assertEqual(fh.read(), b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

    def test_param_target_id01(self):
        """Test normal target_id"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200101000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_id='20200101000000000'):
            pass

        book = Host(self.test_output).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
            '20200101000000000': [
                '20200101000000001',
                '20200101000000002',
            ],
        })

    def test_param_target_id02(self):
        """Insert to root if target_id not exist"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200101000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_id='20230101000000000'):
            pass

        book = Host(self.test_output).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
            ],
        })

    def test_param_target_index01(self):
        """Test normal target_index"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200101000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_index=0):
            pass

        book = Host(self.test_output).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
                '20200101000000002',
                '20200101000000000',
            ],
        })

    def test_param_target_index02(self):
        """Insert to last if target_index is too large"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200101000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_index=10):
            pass

        book = Host(self.test_output).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
            ],
        })

    def test_param_target_index03(self):
        """Treat as None if target_index < 0"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200101000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_index=-1):
            pass

        book = Host(self.test_output).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
                '20200101000000001',
                '20200101000000002',
            ],
        })

    def test_param_target_index04(self):
        """new_at_top=True, target_index=None"""
        self.init_book(
            self.test_output,
            config=self.general_config_new_at_top(),
            meta={
                'item1': {
                    'type': 'folder',
                },
                'item2': {
                    'type': 'separator',
                },
            },
            toc={
                'root': [
                    'item1',
                    'item2',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200101000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000002',
                '20200101000000001',
                'item1',
                'item2',
            ],
        })

    def test_param_target_index05(self):
        """new_at_top=True, target_index=1"""
        self.init_book(
            self.test_output,
            config=self.general_config_new_at_top(),
            meta={
                'item1': {
                    'type': 'folder',
                },
                'item2': {
                    'type': 'separator',
                },
            },
            toc={
                'root': [
                    'item1',
                    'item2',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200101000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_index=1):
            pass

        book = Host(self.test_output).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                'item1',
                '20200101000000002',
                '20200101000000001',
                'item2',
            ],
        })

    def test_param_target_filename01(self):
        """For */index.html"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': '',
                    'title': 'item0',
                    'index': '20200101000000000.html',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_filename='test'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'title': 'item0',
            },
            '20200101000000001': {
                'type': '',
                'index': 'test/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            },
        })
        self.assertTrue(os.path.isfile(os.path.join(self.test_output, 'test', 'index.html')))

    def test_param_target_filename02(self):
        """For *.maff"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': '',
                    'title': 'item0',
                    'index': '20200101000000000.html',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.maff',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001.maff', b'dummy')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_filename='test'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'title': 'item0',
            },
            '20200101000000001': {
                'type': '',
                'index': 'test.maff',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            },
        })
        self.assertTrue(os.path.isfile(os.path.join(self.test_output, 'test.maff')))

    def test_param_target_filename03(self):
        """Fail out if target file exists"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': '',
                    'title': 'item0',
                    'index': '20200101000000000.html',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        with open(os.path.join(self.test_output, '20200101000000000.html'), 'w', encoding='UTF-8') as fh:
            fh.write('some page content')

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            }))
            zh.writestr('data/20200101000000001.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], target_filename='20200101000000000'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'title': 'item0',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })
        with open(os.path.join(self.test_output, '20200101000000000.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'some page content')

    def test_param_target_filename04(self):
        """Test formatters"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': '',
                    'title': 'item0',
                    'index': '20200101000000000.html',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001.htz', b'dummy')

        for _info in wsb_importer.run(
            self.test_output, [self.test_input],
            target_filename='%EID%/%CREATE%-%MODIFY%-%unknown%%%/%TITLE%',
        ):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'title': 'item0',
            },
            '20200101000000001': {
                'type': '',
                'index': '20200401000000001/20200102000000000-20200103000000000-%/item1.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            },
        })
        self.assertTrue(os.path.isfile(os.path.join(
            self.test_output,
            '20200401000000001', '20200102000000000-20200103000000000-%', 'item1.htz',
        )))

    def test_param_target_filename05(self):
        """Test time related formatters"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': '',
                    'title': 'item0',
                    'index': '20200101000000000.html',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20220607232425267.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20220607232425267',
                'timestamp': '20220607232425267',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.html',
                'title': 'item1',
                'create': '20200102030405067',
                'modify': '20211112131415167',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001.html', 'dummy')

        for _info in wsb_importer.run(
            self.test_output, [self.test_input],
            target_filename='%CREATE:UTC_DATE%=%CREATE:UTC_TIME%+'
            '%CREATE:UTC_YEAR%=%CREATE:UTC_MONTH%=%CREATE:UTC_DAY%+'
            '%CREATE:UTC_HOURS%=%CREATE:UTC_MINUTES%=%CREATE:UTC_SECONDS%_'
            '%MODIFY:UTC_DATE%=%MODIFY:UTC_TIME%+'
            '%MODIFY:UTC_YEAR%=%MODIFY:UTC_MONTH%=%MODIFY:UTC_DAY%+'
            '%MODIFY:UTC_HOURS%=%MODIFY:UTC_MINUTES%=%MODIFY:UTC_SECONDS%_'
            '%EXPORT:UTC_DATE%=%EXPORT:UTC_TIME%+'
            '%EXPORT:UTC_YEAR%=%EXPORT:UTC_MONTH%=%EXPORT:UTC_DAY%+'
            '%EXPORT:UTC_HOURS%=%EXPORT:UTC_MINUTES%=%EXPORT:UTC_SECONDS%'
        ):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'title': 'item0',
            },
            '20200101000000001': {
                'type': '',
                'index': (
                    '2020-01-02=03-04-05+2020=01=02+03=04=05_'
                    '2021-11-12=13-14-15+2021=11=12+13=14=15_'
                    '2022-06-07=23-24-25+2022=06=07+23=24=25'
                    '.html'),
                'title': 'item1',
                'create': '20200102030405067',
                'modify': '20211112131415167',
                'source': 'http://example.com',
            },
        })
        self.assertTrue(os.path.isfile(os.path.join(self.test_output, (
            '2020-01-02=03-04-05+2020=01=02+03=04=05_'
            '2021-11-12=13-14-15+2021=11=12+13=14=15_'
            '2022-06-07=23-24-25+2022=06=07+23=24=25'
            '.html'
        ))))

    def test_param_rebuild_folders01(self):
        """Insert under parent if it exists."""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'Folder 1 current',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'Folder 2 current',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'Folder 3 current',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
                '20200101000000001': [
                    '20200101000000002',
                ],
                '20200101000000002': [
                    '20200101000000003',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'title': 'Folder 1 current',
                'type': 'folder',
            },
            '20200101000000002': {
                'title': 'Folder 2 current',
                'type': 'folder',
            },
            '20200101000000003': {
                'title': 'Folder 3 current',
                'type': 'folder',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
            '20200101000000001': [
                '20200101000000002',
            ],
            '20200101000000002': [
                '20200101000000003',
                '20200201000000001',
                '20200201000000002',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders02(self):
        """Generate missing parent folders.

        - Imported items should be put under the same generated parent folder
          for the same original ID.
        """
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20230101000000002',
            ],
            '20230101000000002': [
                '20200201000000001',
                '20200201000000002',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders03(self):
        """Generate partly missing parent folders."""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': 'bookmark',
                    'title': 'Folder 1 current',
                    'source': 'http://example.com',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'title': 'Folder 1 current',
                'type': 'bookmark',
                'source': 'http://example.com',
            },
            '20230101000000001': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
            '20200101000000001': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20200201000000001',
                '20200201000000002',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders04(self):
        """Insert generated parent folders under root if path not connected."""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20230101000000002',
            ],
            '20230101000000002': [
                '20200201000000001',
                '20200201000000002',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders05(self):
        """Share same generated folders. (item2.path under item1.path)"""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20200201000000001',
                '20230101000000002',
            ],
            '20230101000000002': [
                '20200201000000002',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders06(self):
        """Share same generated folders. (item1.path under item2.path)"""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20230101000000002',
                '20200201000000002',
            ],
            '20230101000000002': [
                '20200201000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders07(self):
        """Reuse same generated folders if path contains duplicated ancestors."""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20230101000000002',
            ],
            '20230101000000002': [
                '20230101000000001',
                '20200201000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders08(self):
        """Insert a generated folder under its parent which is circularly its descendant."""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20230101000000002',
                '20200201000000001',
            ],
            '20230101000000002': [
                '20230101000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders09(self):
        """Don't insert a generated folder under its parent duplicately."""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20230101000000002',
                '20200201000000001',
            ],
            '20230101000000002': [
                '20230101000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders10(self):
        """Take care if path contains self. (The one before self is not direct parent)"""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200201000000001', 'title': 'Item 1'},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200201000000001',
            ],
            '20200201000000001': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20200201000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders11(self):
        """Take care if path contains self. (The one before self is direct parent)"""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200201000000001', 'title': 'Item 1'},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20200201000000001',
            ],
            '20200201000000001': [
                '20230101000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders12(self):
        """Handle X/Y => Z/X"""
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200201000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200201000000002',
                'modify': '20200201000000002',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200201000000003', 'title': 'Folder 3'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200201000000001',
                'modify': '20200201000000001',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content 1')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200201000000002',
                'modify': '20200201000000002',
            },
            '20230101000000001': {
                'title': 'Folder 3',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200201000000001',
                'modify': '20200201000000001',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200201000000001',
                '20230101000000001',
            ],
            '20230101000000001': [
                '20200201000000001',
            ],
            '20200201000000001': [
                '20200201000000002',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders13(self):
        """Insert imported items at top if new_at_top=True."""
        self.init_book(
            self.test_output,
            config=self.general_config_new_at_top(),
            meta={
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'Folder 1 current',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'Folder 2 current',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
                '20200101000000001': [
                    '20200101000000002',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'title': 'Folder 1 current',
                'type': 'folder',
            },
            '20200101000000002': {
                'title': 'Folder 2 current',
                'type': 'folder',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
            '20200101000000001': [
                '20200201000000002',
                '20200201000000001',
                '20200101000000002',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders14(self):
        """Insert generated parent folders at top if new_at_top=True."""
        self.init_book(
            self.test_output,
            config=self.general_config_new_at_top(),
            meta={
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'Folder 1 current',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'Folder 2 current',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
                '20200101000000001': [
                    '20200101000000002',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000003', 'title': 'Folder 3'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000004', 'title': 'Folder 4'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'title': 'Folder 1 current',
                'type': 'folder',
            },
            '20200101000000002': {
                'title': 'Folder 2 current',
                'type': 'folder',
            },
            '20230101000000001': {
                'title': 'Folder 3',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 4',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20230101000000002',
                '20200101000000001',
            ],
            '20200101000000001': [
                '20230101000000001',
                '20200101000000002',
            ],
            '20230101000000001': [
                '20200201000000001',
            ],
            '20230101000000002': [
                '20200201000000002',
            ],
        })

    def test_param_rebuild_folders15(self):
        """Ignore target_index if target_id is not specified."""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'Folder 1 current',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'Folder 2 current',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'Folder 3 current',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
                '20200101000000001': [
                    '20200101000000002',
                ],
                '20200101000000002': [
                    '20200101000000003',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True,
                                      target_index=0):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'title': 'Folder 1 current',
                'type': 'folder',
            },
            '20200101000000002': {
                'title': 'Folder 2 current',
                'type': 'folder',
            },
            '20200101000000003': {
                'title': 'Folder 3 current',
                'type': 'folder',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
            '20200101000000001': [
                '20200101000000002',
            ],
            '20200101000000002': [
                '20200101000000003',
                '20200201000000001',
                '20200201000000002',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders16(self):
        """If target_id is specified, insert under it and generate intermediate
        folders even if they exists.
        """
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'Folder 1 current',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'Folder 2 current',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'Folder 3 current',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
                '20200101000000001': [
                    '20200101000000002',
                ],
                '20200101000000002': [
                    '20200101000000003',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        wsba_file = os.path.join(self.test_input, '20200403000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200403000000000',
                'timestamp': '20200403000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000003',
                'type': '',
                'index': '20200201000000003/index.html',
                'title': 'Item 3',
                'create': '20200202000000003',
                'modify': '20200203000000003',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000003/index.html', 'page content 3')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True,
                                      target_id='20200101000000003'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'title': 'Folder 1 current',
                'type': 'folder',
            },
            '20200101000000002': {
                'title': 'Folder 2 current',
                'type': 'folder',
            },
            '20200101000000003': {
                'title': 'Folder 3 current',
                'type': 'folder',
            },
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
            '20200201000000003': {
                'type': '',
                'index': '20200201000000003/index.html',
                'title': 'Item 3',
                'create': '20200202000000003',
                'modify': '20200203000000003',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
            '20200101000000001': [
                '20200101000000002',
            ],
            '20200101000000002': [
                '20200101000000003',
            ],
            '20200101000000003': [
                '20200201000000001',
                '20230101000000001',
            ],
            '20230101000000001': [
                '20230101000000002',
            ],
            '20230101000000002': [
                '20200201000000002',
                '20200201000000003',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders17(self):
        """If target_id and target_index are specified, insert under that position."""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'Folder 1 current',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'Folder 2 current',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
                '20200101000000001': [
                    '20200101000000002',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000001',
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200201000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        wsba_file = os.path.join(self.test_input, '20200403000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200403000000000',
                'timestamp': '20200403000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000003',
                'type': '',
                'index': '20200201000000003/index.html',
                'title': 'Item 3',
                'create': '20200202000000003',
                'modify': '20200203000000003',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000003/index.html', 'page content 3')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True,
                                      target_id='20200101000000001', target_index=0):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'title': 'Folder 1 current',
                'type': 'folder',
            },
            '20200101000000002': {
                'title': 'Folder 2 current',
                'type': 'folder',
            },
            '20200201000000001': {
                'type': '',
                'index': '20200201000000001/index.html',
                'title': 'Item 1',
                'create': '20200202000000001',
                'modify': '20200203000000001',
                'source': 'http://example.com',
            },
            '20230101000000001': {
                'title': 'Folder 1',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20230101000000002': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
            '20200201000000003': {
                'type': '',
                'index': '20200201000000003/index.html',
                'title': 'Item 3',
                'create': '20200202000000003',
                'modify': '20200203000000003',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
            '20200101000000001': [
                '20200201000000001',
                '20230101000000001',
                '20200101000000002',
            ],
            '20230101000000001': [
                '20230101000000002',
            ],
            '20230101000000002': [
                '20200201000000002',
                '20200201000000003',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000001')
    def test_param_rebuild_folders18(self):
        """Insert under previously imported items."""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'Folder 0',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': 'folder',
                'title': 'Item 1',
                'create': '20200102000000001',
                'modify': '20200103000000001',
            }))

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000002',
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000002/index.html', 'page content 2')

        wsba_file = os.path.join(self.test_input, '20200403000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200403000000000',
                'timestamp': '20200403000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'Folder 1'},
                    {'id': '20200101000000002', 'title': 'Folder 2'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200201000000003',
                'type': '',
                'index': '20200201000000003/index.html',
                'title': 'Item 3',
                'create': '20200202000000003',
                'modify': '20200203000000003',
                'source': 'https://example.com',
            }))
            zh.writestr('data/20200201000000003/index.html', 'page content 3')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True,
                                      target_id='root', target_index=0):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'type': 'folder',
                'title': 'Folder 0',
            },
            '20200101000000001': {
                'type': 'folder',
                'title': 'Item 1',
                'create': '20200102000000001',
                'modify': '20200103000000001',
            },
            '20230101000000001': {
                'title': 'Folder 2',
                'type': 'folder',
                'create': '20230101000000001',
                'modify': '20230101000000001',
            },
            '20200201000000002': {
                'type': '',
                'index': '20200201000000002/index.html',
                'title': 'Item 2',
                'create': '20200202000000002',
                'modify': '20200203000000002',
                'source': 'https://example.com',
            },
            '20200201000000003': {
                'type': '',
                'index': '20200201000000003/index.html',
                'title': 'Item 3',
                'create': '20200202000000003',
                'modify': '20200203000000003',
                'source': 'https://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
                '20200101000000000',
            ],
            '20200101000000001': [
                '20200201000000002',
                '20230101000000001',
            ],
            '20230101000000001': [
                '20200201000000003',
            ],
        })

    def test_param_resolve_id_used_skip01(self):
        """No import if ID exists"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='skip'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': 'folder'
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })

    def test_param_resolve_id_used_replace01(self):
        """Test */index.html"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': '',
                    'index': '20200101000000001/index.html',
                    'title': 'original title',
                    'create': '20200201000000000',
                    'modify': '20200301000000000',
                    'source': 'http://example.com/original',
                    'icon': 'favicon.ico',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )
        os.makedirs(os.path.join(self.test_output, '20200101000000001'))
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('original page content')
        with open(os.path.join(self.test_output, '20200101000000001', 'favicon.ico'), 'wb') as fh:
            fh.write(b'dummy')

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')
            zh.writestr('data/20200101000000001/favicon.bmp',
                        b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='replace'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001'),
            os.path.join(self.test_output, '20200101000000001', 'index.html'),
            os.path.join(self.test_output, '20200101000000001', 'favicon.bmp'),
        })
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')
        with open(os.path.join(self.test_output, '20200101000000001', 'favicon.bmp'), 'rb') as fh:
            self.assertEqual(
                fh.read(),
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

    def test_param_resolve_id_used_replace02(self):
        """Test *.htz"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': '',
                    'index': '20200101000000001.htz',
                    'title': 'original title',
                    'create': '20200201000000000',
                    'modify': '20200301000000000',
                    'source': 'http://example.com/original',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )
        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000001.htz'), 'w') as zh:
            zh.writestr('index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '../tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            }))
            zh.writestr('data/20200101000000001.htz', b'dummy')
            zh.writestr('favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                        b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='replace'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001.htz'),
        })
        self.assertCountEqual(glob_files(os.path.join(self.test_output, '.wsb', 'tree', 'favicon')), {
            os.path.join(self.test_output, '.wsb', 'tree', 'favicon', ''),
            os.path.join(self.test_output, '.wsb', 'tree', 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'),
        })
        with open(os.path.join(self.test_output, '20200101000000001.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy')

    def test_param_resolve_id_used_replace03(self):
        """Fail if index file extension not match"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': '',
                    'index': '20200101000000001/index.html',
                    'title': 'original title',
                    'create': '20200201000000000',
                    'modify': '20200301000000000',
                    'source': 'http://example.com/original',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )
        os.makedirs(os.path.join(self.test_output, '20200101000000001'))
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('original page content')

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001.htz', b'dummy')

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='replace'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'original title',
                'create': '20200201000000000',
                'modify': '20200301000000000',
                'source': 'http://example.com/original',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001'),
            os.path.join(self.test_output, '20200101000000001', 'index.html'),
        })

    def test_param_resolve_id_used_replace04(self):
        """Don't match */index.html and *.html"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': '',
                    'index': '20200101000000001/index.html',
                    'title': 'original title',
                    'create': '20200201000000000',
                    'modify': '20200301000000000',
                    'source': 'http://example.com/original',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )
        os.makedirs(os.path.join(self.test_output, '20200101000000001'))
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('original page content')

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001.html', 'dummy')

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='replace'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'original title',
                'create': '20200201000000000',
                'modify': '20200301000000000',
                'source': 'http://example.com/original',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001'),
            os.path.join(self.test_output, '20200101000000001', 'index.html'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_param_resolve_id_used_new01(self):
        """Test */index.html"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': '',
                    'index': '20200101000000001/index.html',
                    'title': 'original title',
                    'create': '20200201000000000',
                    'modify': '20200301000000000',
                    'source': 'http://example.com/original',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )
        os.makedirs(os.path.join(self.test_output, '20200101000000001'))
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('original page content')

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1f',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content f')

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='new'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'original title',
                'create': '20200201000000000',
                'modify': '20200301000000000',
                'source': 'http://example.com/original',
            },
            '20230101000000000': {
                'type': '',
                'index': '20230101000000000/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
                '20230101000000000',
            ],
        })
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000001'),
            os.path.join(self.test_output, '20200101000000001', 'index.html'),
            os.path.join(self.test_output, '20230101000000000'),
            os.path.join(self.test_output, '20230101000000000', 'index.html'),
        })
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'original page content')
        with open(os.path.join(self.test_output, '20230101000000000', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')

    def test_param_prune(self):
        """Remove successfully imported *.wsba"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file2 = os.path.join(self.test_input, '20200401000000002.wsba')
        with zipfile.ZipFile(wsba_file2, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000002',
                'timestamp': '20200401000000002',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 1,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item1',
                'create': '20200202000000000',
                'modify': '20200203000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000002/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='skip', prune=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
                '20200101000000002',
            ],
        })
        self.assertCountEqual(glob_files(self.test_input), {
            os.path.join(self.test_input, ''),
            wsba_file,
        })

    def test_multi_occurrence01(self):
        """Skip multi-occurred item (same export id) if not rebuild_folders."""
        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200401000000002.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000002',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            # Normally all occurrences have identical meta.json and data files.
            # Use a different content here to test if the second occurrence is
            # unexpectedly taken.
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item2',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })

        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')

    def test_multi_occurrence02(self):
        """For a multi-occurrent item (same export id), import only TOC for
        following ones.
        """
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200401000000002.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000002',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            # Use a different content for testing.
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item2',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'type': 'folder'
            },
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
                '20200101000000001',
            ],
            '20200101000000000': [
                '20200101000000001',
            ],
        })

        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')

    def test_multi_occurrence03(self):
        """Multi-occurred item under a multi-occurred parent."""
        self.init_book(
            self.test_output,
            meta={
                '20220101000000001': {
                    'type': 'folder',
                },
                '20220101000000002': {
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20220101000000001',
                    '20220101000000002',
                ],
                '20220101000000001': [
                    '20220101000000002',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20220101000000001', 'title': 'folder1'},
                    {'id': '20220101000000002', 'title': 'folder2'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200401000000002.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000002',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20220101000000001', 'title': 'folder1'},
                    {'id': '20220101000000002', 'title': 'folder2'},
                ],
                'index': 1,
            }))
            # Use a different content for testing.
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item2',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 2')

        wsba_file = os.path.join(self.test_input, '20200401000000003.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000003',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20220101000000002', 'title': 'folder2'},
                ],
                'index': 0,
            }))
            # Use a different content for testing.
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item3',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 3')

        wsba_file = os.path.join(self.test_input, '20200401000000004.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000004',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20220101000000002', 'title': 'folder2'},
                ],
                'index': 1,
            }))
            # Use a different content for testing.
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item4',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 4')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20220101000000001': {
                'type': 'folder',
            },
            '20220101000000002': {
                'type': 'folder',
            },
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20220101000000001',
                '20220101000000002',
            ],
            '20220101000000001': [
                '20220101000000002',
            ],
            '20220101000000002': [
                '20200101000000001',
                '20200101000000001',
            ],
        })

        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')

    def test_multi_occurrence04(self):
        """A replaced item should be imported only once and never inserted. (rebuild_folders=False)"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': '',
                    'index': '20200101000000001/index.html',
                    'title': 'original title',
                    'create': '20200201000000000',
                    'modify': '20200301000000000',
                    'source': 'http://example.com/original',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )
        os.makedirs(os.path.join(self.test_output, '20200101000000001'))
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('original page content')

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            # Use a different content for testing.
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item2',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='replace'):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })

        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')

    def test_multi_occurrence05(self):
        """A replaced item should be imported only once and never inserted. (rebuild_folders=True)"""
        self.init_book(
            self.test_output,
            meta={
                '20200101000000001': {
                    'type': '',
                    'index': '20200101000000001/index.html',
                    'title': 'original title',
                    'create': '20200201000000000',
                    'modify': '20200301000000000',
                    'source': 'http://example.com/original',
                },
            },
            toc={
                'root': [
                    '20200101000000001',
                ],
            },
        )
        os.makedirs(os.path.join(self.test_output, '20200101000000001'))
        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('original page content')

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
                'index': 1,
            }))
            # Use a different content for testing.
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item2',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 2')

        for _info in wsb_importer.run(self.test_output, [self.test_input], resolve_id_used='replace',
                                      rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000001',
            ],
        })

        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')

    def test_bad_version01(self):
        """Unsupported version should be rejected."""
        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'Item 1',
                'create': '20200101000000001',
                'modify': '20200101000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 1')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
        })

    def test_bad_version02(self):
        """Unsupported version should be rejected."""
        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 3,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'Item 1',
                'create': '20200101000000001',
                'modify': '20200101000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 1')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
        })

    def test_bad_export_info01(self):
        """Missing export.json"""
        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'Item 1',
                'create': '20200101000000001',
                'modify': '20200101000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 1')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
        })

    def test_bad_export_info02(self):
        """Malformed JSON for export.json"""
        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }) + 'abc')
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'Item 1',
                'create': '20200101000000001',
                'modify': '20200101000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 1')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
        })

    def test_bad_export_info03(self):
        """Malformed JSON scheme for export.json"""
        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': '28800',
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'Item 1',
                'create': '20200101000000001',
                'modify': '20200101000000001',
                'source': 'http://example.com',
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 1')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
        })

    def test_bad_meta01(self):
        """Missing meta.json"""
        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content 1')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
        })

    def test_bad_meta02(self):
        """Malformed JSON for meta.json"""
        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
                'index': 0,
            }))
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'Item 1',
                'create': '20200101000000001',
                'modify': '20200101000000001',
                'source': 'http://example.com',
            }) + 'abc')
            zh.writestr('data/20200101000000001/index.html', 'page content 1')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
        })


if __name__ == '__main__':
    unittest.main()
