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

from . import TEMP_DIR, TestBookMixin


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
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_input = os.path.join(self.test_root, 'input')
        self.test_output = os.path.join(self.test_root, 'output')
        self.test_output_tree = os.path.join(self.test_output, WSB_DIR, 'tree')

        os.makedirs(self.test_input, exist_ok=True)
        os.makedirs(self.test_output_tree, exist_ok=True)

    def test_basic01(self):
        """Test importing a common */index.html
        """
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')
            zh.writestr(
                'data/20200101000000001/favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr('data/20200101000000001.htz', buf.getvalue())
            zh.writestr(
                'favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr(
                'favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

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
        """Test importing a common */index.html with cached favicon
        """
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')
            zh.writestr(
                'favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

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

    def test_multi_occurrence(self):
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file2 = os.path.join(self.test_input, '20200401000000002.wsba')
        with zipfile.ZipFile(wsba_file2, 'w') as zh:
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000001',
                'timestamp': '20200401000000002',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            # Normally all occurrences have identical meta.json and data files.
            # Use a different content here to test if the second occurrence is
            # unexpectedly copied.
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
                'icon': 'favicon.bmp',
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

    def test_param_target_id(self):
        """Test for target_id
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

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
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

    def test_param_target_index(self):
        """Test for target_index
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

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200402000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item2',
                'create': '20200102000000002',
                'modify': '20200103000000002',
                'source': 'https://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200402000000000',
                'timestamp': '20200402000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
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

    def test_param_target_filename01(self):
        """For */index.html
        """
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
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
        """For *.maff
        """
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
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.maff',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
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
        """Fail out if target file exists
        """
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
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
        """Test formatters
        """
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
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
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
        """Test time related formatters
        """
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
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.html',
                'title': 'item1',
                'create': '20200102030405067',
                'modify': '20211112131415167',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20220607232425267',
                'timestamp': '20220607232425267',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
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
        """Test for rebuild_folders
        """
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'current item0',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'current item2',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
                '20200101000000000': [
                    '20200101000000002',
                ],
            },
        )

        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000002', 'title': 'item2'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
            '20200101000000000': [
                '20200101000000002',
            ],
            '20200101000000002': [
                '20200101000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_param_rebuild_folders02(self):
        """Generate folders if parent not exist
        """
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000002', 'title': 'item2'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000000': {
                'title': 'item0',
                'type': 'folder',
                'create': '20230101000000000',
                'modify': '20230101000000000',
            },
            '20230101000000001': {
                'title': 'item2',
                'type': 'folder',
                'create': '20230101000000000',
                'modify': '20230101000000000',
            },
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
                '20230101000000000',
            ],
            '20230101000000000': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20200101000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_param_rebuild_folders03(self):
        """Generate folders if parent not exist (partial)
        """
        self.init_book(
            self.test_output,
            meta={
                '20200101000000000': {
                    'type': 'bookmark',
                    'title': 'current item0',
                    'source': 'http://example.com',
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000002', 'title': 'item2'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'title': 'current item0',
                'type': 'bookmark',
                'source': 'http://example.com',
            },
            '20230101000000000': {
                'title': 'item2',
                'type': 'folder',
                'create': '20230101000000000',
                'modify': '20230101000000000',
            },
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
                '20200101000000000',
            ],
            '20200101000000000': [
                '20230101000000000',
            ],
            '20230101000000000': [
                '20200101000000001',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_param_rebuild_folders04(self):
        """Assume path starting from 'root' if no matching id
        """
        wsba_file = os.path.join(self.test_input, '20200401000000000.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000002', 'title': 'item2'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input], rebuild_folders=True):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20230101000000000': {
                'title': 'item0',
                'type': 'folder',
                'create': '20230101000000000',
                'modify': '20230101000000000',
            },
            '20230101000000001': {
                'title': 'item2',
                'type': 'folder',
                'create': '20230101000000000',
                'modify': '20230101000000000',
            },
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
                '20230101000000000',
            ],
            '20230101000000000': [
                '20230101000000001',
            ],
            '20230101000000001': [
                '20200101000000001',
            ],
        })

    def test_param_resolve_id_used_skip01(self):
        """No import if ID exists
        """
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
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
        """Test */index.html
        """
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')
            zh.writestr(
                'data/20200101000000001/favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

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

        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')
        with open(os.path.join(self.test_output, '20200101000000001', 'favicon.bmp'), 'rb') as fh:
            self.assertEqual(
                fh.read(),
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )
        self.assertFalse(os.path.lexists(os.path.join(self.test_output, '20200101000000001', 'favicon.ico')))

    def test_param_resolve_id_used_replace02(self):
        """Test *.htz
        """
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
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
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
                'index': '20200101000000001.htz',
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

        with open(os.path.join(self.test_output, '20200101000000001.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy')

    def test_param_resolve_id_used_replace03(self):
        """Fail if index file extension not match
        """
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
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.htz',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
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

        self.assertTrue(os.path.isfile(os.path.join(self.test_output, '20200101000000001', 'index.html')))
        self.assertFalse(os.path.lexists(os.path.join(self.test_output, '20200101000000001.htz')))

    def test_param_resolve_id_used_replace04(self):
        """Don't match */index.html and *.html
        """
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
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
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

        self.assertTrue(os.path.isfile(os.path.join(self.test_output, '20200101000000001', 'index.html')))
        self.assertFalse(os.path.lexists(os.path.join(self.test_output, '20200101000000001.html')))

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_param_resolve_id_used_new01(self):
        """Test */index.html
        """
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
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file = os.path.join(self.test_input, '20200401000000001.wsba')
        with zipfile.ZipFile(wsba_file, 'w') as zh:
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000001',
                'type': '',
                'index': '20200101000000001/index.html',
                'title': 'item1f',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000000',
                'timestamp': '20200401000000001',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
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

        with open(os.path.join(self.test_output, '20200101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'original page content')
        with open(os.path.join(self.test_output, '20230101000000000', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')

    def test_param_prune(self):
        """Remove successfully imported *.wsba
        """
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
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000001',
                'timestamp': '20200401000000001',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        wsba_file2 = os.path.join(self.test_input, '20200401000000002.wsba')
        with zipfile.ZipFile(wsba_file2, 'w') as zh:
            zh.writestr('meta.json', json.dumps({
                'id': '20200101000000002',
                'type': '',
                'index': '20200101000000002/index.html',
                'title': 'item1',
                'create': '20200202000000000',
                'modify': '20200203000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            }))
            zh.writestr('export.json', json.dumps({
                'version': 1,
                'id': '20200401000000002',
                'timestamp': '20200401000000002',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
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

        self.assertTrue(os.path.isfile(wsba_file))
        self.assertFalse(os.path.lexists(wsba_file2))

    def test_version(self):
        """Unsupported version should be rejected."""
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
            zh.writestr('export.json', json.dumps({
                'version': 2,
                'id': '20200401000000000',
                'timestamp': '20200401000000000',
                'timezone': 28800.0,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            }))
            zh.writestr('data/20200101000000001/index.html', 'page content')

        for _info in wsb_importer.run(self.test_output, [self.test_input]):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertEqual(book.meta, {
            '20200101000000000': {
                'type': 'folder'
            },
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
        })
        self.assertFalse(os.path.lexists(os.path.join(self.test_output, '20200101000000001')))


if __name__ == '__main__':
    unittest.main()
