import json
import os
import tempfile
import unittest
from base64 import b64decode
from datetime import datetime
from unittest import mock

from webscrapbook import WSB_DIR
from webscrapbook._polyfill import zipfile
from webscrapbook.scrapbook import exporter as wsb_exporter

from . import TEMP_DIR, TestBookMixin, glob_files


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='exporter-', dir=TEMP_DIR)
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


class TestExporter(TestBookMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder"""
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_input = os.path.join(self.test_root, 'input')
        self.test_input_tree = os.path.join(self.test_input, WSB_DIR, 'tree')
        self.test_output = os.path.join(self.test_root, 'output')

        os.makedirs(self.test_input_tree, exist_ok=True)

    @staticmethod
    def read_exported_archive(file):
        export_info = None
        meta = None
        index_data = None
        favicon_data = None

        with zipfile.ZipFile(file) as zh:
            with zh.open('export.json') as fh:
                export_info = json.load(fh)
            with zh.open('meta.json') as fh:
                meta = json.load(fh)
            for zinfo in zh.infolist():
                if zinfo.filename.startswith('data/'):
                    if zinfo.filename.endswith('/index.html'):
                        with zh.open(zinfo) as fh:
                            index_data = fh.read().decode('UTF-8')
                    elif zinfo.filename.endswith('.htz'):
                        with zh.open(zinfo) as fh:
                            with zipfile.ZipFile(fh) as zh2:
                                with zh2.open('index.html') as fh2:
                                    index_data = fh2.read().decode('UTF-8')
                    continue

                if zinfo.filename.startswith('favicon/'):
                    with zh.open(zinfo) as fh:
                        favicon_data = fh.read()
                    continue

        return {
            'export_info': export_info,
            'meta': meta,
            'index_data': index_data,
            'favicon_data': favicon_data,
        }

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_basic01(self):
        """Test exporting a common */index.html"""
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': '',
                    'title': 'item0',
                    'index': '20200101000000000/index.html',
                    'create': '20200102000000000',
                    'modify': '20200103000000000',
                    'source': 'http://example.com',
                    'icon': 'favicon.bmp',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(index_file))
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('ABC123')

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': datetime.now().astimezone().utcoffset().total_seconds(),
                'path': [{'id': 'root', 'title': ''}],
            },
            'meta': {
                'id': '20200101000000000',
                'type': '',
                'title': 'item0',
                'index': '20200101000000000/index.html',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': 'favicon.bmp',
            },
            'index_data': 'ABC123',
            'favicon_data': None,
        })

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_basic02(self):
        """Test exporting a common *.htz"""
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': '',
                    'title': 'item0',
                    'index': '20200101000000000.htz',
                    'create': '20200102000000000',
                    'modify': '20200103000000000',
                    'source': 'http://example.com',
                    'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', 'ABC123')
        favicon_file = os.path.join(self.test_input_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp')
        os.makedirs(os.path.dirname(favicon_file))
        with open(favicon_file, 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': datetime.now().astimezone().utcoffset().total_seconds(),
                'path': [{'id': 'root', 'title': ''}],
            },
            'meta': {
                'id': '20200101000000000',
                'type': '',
                'title': 'item0',
                'index': '20200101000000000.htz',
                'create': '20200102000000000',
                'modify': '20200103000000000',
                'source': 'http://example.com',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            },
            'index_data': 'ABC123',
            'favicon_data': b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
        })

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_toc01(self):
        """Export all if item_ids not set

        - Include hidden (at last).
        - Exclude recycle.
        """
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'item0',
                },
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'item1',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'item2',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'item3',
                },
                '20200101000000004': {
                    'type': 'folder',
                    'title': 'item4',
                },
                '20200101000000005': {
                    'type': 'folder',
                    'title': 'item5',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200101000000001',
                ],
                '20200101000000000': [
                    '20200101000000002',
                ],
                'hidden': [
                    '20200101000000003',
                ],
                'recycle': [
                    '20200101000000004',
                ],
                '20200101000000004': [
                    '20200101000000005',
                ],
            },
        )

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
            os.path.join(self.test_output, '20230101000000001-item2.wsba'),
            os.path.join(self.test_output, '20230101000000002-item1.wsba'),
            os.path.join(self.test_output, '20230101000000003-item3.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000001-item2.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000001',
                'timestamp': '20230101000000001',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            },
            'meta': {
                'id': '20200101000000002',
                'type': 'folder',
                'title': 'item2',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000002-item1.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000002',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000001',
                'type': 'folder',
                'title': 'item1',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000003-item3.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000003',
                'timestamp': '20230101000000003',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'hidden', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000003',
                'type': 'folder',
                'title': 'item3',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_toc02(self):
        """Export only those specified by item_ids

        - Can include recycle.
        """
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'item0',
                },
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'item1',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'item2',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'item3',
                },
                '20200101000000004': {
                    'type': 'folder',
                    'title': 'item4',
                },
                '20200101000000005': {
                    'type': 'folder',
                    'title': 'item5',
                },
                '20200101000000006': {
                    'type': 'folder',
                    'title': 'item6',
                },
                '20200101000000007': {
                    'type': 'folder',
                    'title': 'item7',
                },
                '20200101000000008': {
                    'type': 'folder',
                    'title': 'item8',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200101000000001',
                ],
                '20200101000000000': [
                    '20200101000000002',
                ],
                'hidden': [
                    '20200101000000003',
                    '20200101000000004',
                ],
                '20200101000000003': [
                    '20200101000000005',
                ],
                'recycle': [
                    '20200101000000006',
                    '20200101000000007',
                ],
                '20200101000000006': [
                    '20200101000000008',
                ],
            },
        )

        for _info in wsb_exporter.run(
            self.test_input, self.test_output,
            item_ids=['20200101000000000', '20200101000000003', '20200101000000006'],
        ):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
            os.path.join(self.test_output, '20230101000000001-item3.wsba'),
            os.path.join(self.test_output, '20230101000000002-item6.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000001-item3.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000001',
                'timestamp': '20230101000000001',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'hidden', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000003',
                'type': 'folder',
                'title': 'item3',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000002-item6.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000002',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'recycle', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000006',
                'type': 'folder',
                'title': 'item6',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_toc03(self):
        """Export descendants if recursive"""
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'item0',
                },
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'item1',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'item2',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'item3',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200101000000001',
                ],
                '20200101000000000': [
                    '20200101000000002',
                ],
                '20200101000000002': [
                    '20200101000000003',
                ],
            },
        )

        for _info in wsb_exporter.run(
            self.test_input, self.test_output,
            item_ids=['20200101000000000'], recursive=True,
        ):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
            os.path.join(self.test_output, '20230101000000001-item2.wsba'),
            os.path.join(self.test_output, '20230101000000002-item3.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000001-item2.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000001',
                'timestamp': '20230101000000001',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            },
            'meta': {
                'id': '20200101000000002',
                'type': 'folder',
                'title': 'item2',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000002-item3.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000002',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000002', 'title': 'item2'},
                ],
            },
            'meta': {
                'id': '20200101000000003',
                'type': 'folder',
                'title': 'item3',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_toc04(self):
        """Export all occurrences

        - Occurrences of the same item should share same export id.
        """
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'item0',
                },
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'item1',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'item2',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'item3',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200101000000000',
                    '20200101000000001',
                    '20200101000000002',
                ],
                '20200101000000001': [
                    '20200101000000000',
                ],
                '20200101000000002': [
                    '20200101000000003',
                ],
                '20200101000000003': [
                    '20200101000000000',
                ],
            },
        )

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
            os.path.join(self.test_output, '20230101000000001-item0.wsba'),
            os.path.join(self.test_output, '20230101000000002-item1.wsba'),
            os.path.join(self.test_output, '20230101000000003-item0.wsba'),
            os.path.join(self.test_output, '20230101000000004-item2.wsba'),
            os.path.join(self.test_output, '20230101000000005-item3.wsba'),
            os.path.join(self.test_output, '20230101000000006-item0.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000001-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000001',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000002-item1.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000002',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000001',
                'type': 'folder',
                'title': 'item1',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000003-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000003',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'item1'},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000004-item2.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000004',
                'timestamp': '20230101000000004',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000002',
                'type': 'folder',
                'title': 'item2',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000005-item3.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000005',
                'timestamp': '20230101000000005',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000002', 'title': 'item2'},
                ],
            },
            'meta': {
                'id': '20200101000000003',
                'type': 'folder',
                'title': 'item3',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000006-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000006',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000002', 'title': 'item2'},
                    {'id': '20200101000000003', 'title': 'item3'},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_toc05(self):
        """Export first occurrence if singleton"""
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'item0',
                },
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'item1',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'item2',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'item3',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200101000000000',
                    '20200101000000001',
                    '20200101000000002',
                ],
                '20200101000000001': [
                    '20200101000000000',
                ],
                '20200101000000002': [
                    '20200101000000003',
                ],
                '20200101000000003': [
                    '20200101000000000',
                ],
            },
        )

        for _info in wsb_exporter.run(self.test_input, self.test_output, singleton=True):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
            os.path.join(self.test_output, '20230101000000001-item1.wsba'),
            os.path.join(self.test_output, '20230101000000002-item2.wsba'),
            os.path.join(self.test_output, '20230101000000003-item3.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000001-item1.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000001',
                'timestamp': '20230101000000001',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000001',
                'type': 'folder',
                'title': 'item1',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000002-item2.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000002',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000002',
                'type': 'folder',
                'title': 'item2',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000003-item3.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000003',
                'timestamp': '20230101000000003',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000002', 'title': 'item2'},
                ],
            },
            'meta': {
                'id': '20200101000000003',
                'type': 'folder',
                'title': 'item3',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_toc06(self):
        """Export circular item but no children"""
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'item0',
                },
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'item1',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
                '20200101000000000': [
                    '20200101000000001',
                ],
                '20200101000000001': [
                    '20200101000000000',
                ],
            },
        )

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
            os.path.join(self.test_output, '20230101000000001-item1.wsba'),
            os.path.join(self.test_output, '20230101000000002-item0.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000001-item1.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000001',
                'timestamp': '20230101000000001',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            },
            'meta': {
                'id': '20200101000000001',
                'type': 'folder',
                'title': 'item1',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000002-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000002',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000001', 'title': 'item1'},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

    @mock.patch('webscrapbook.scrapbook.exporter._id_now', lambda: '20230101000000000')
    def test_toc07(self):
        """Test multi-referenced parent"""
        self.init_book(
            self.test_input,
            meta={
                '20200101000000000': {
                    'type': 'folder',
                    'title': 'item0',
                },
                '20200101000000001': {
                    'type': 'folder',
                    'title': 'item1',
                },
                '20200101000000002': {
                    'type': 'folder',
                    'title': 'item2',
                },
                '20200101000000003': {
                    'type': 'folder',
                    'title': 'item3',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200101000000001',
                ],
                '20200101000000000': [
                    '20200101000000001',
                ],
                '20200101000000001': [
                    '20200101000000002',
                    '20200101000000003',
                    '20200101000000002',
                ],
            },
        )

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        self.assertCountEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20230101000000000-item0.wsba'),
            os.path.join(self.test_output, '20230101000000001-item1.wsba'),
            os.path.join(self.test_output, '20230101000000002-item2.wsba'),
            os.path.join(self.test_output, '20230101000000003-item3.wsba'),
            os.path.join(self.test_output, '20230101000000004-item2.wsba'),
            os.path.join(self.test_output, '20230101000000005-item1.wsba'),
            os.path.join(self.test_output, '20230101000000006-item2.wsba'),
            os.path.join(self.test_output, '20230101000000007-item3.wsba'),
            os.path.join(self.test_output, '20230101000000008-item2.wsba'),
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000000-item0.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000000',
                'timestamp': '20230101000000000',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000000',
                'type': 'folder',
                'title': 'item0',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000001-item1.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000001',
                'timestamp': '20230101000000001',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                ],
            },
            'meta': {
                'id': '20200101000000001',
                'type': 'folder',
                'title': 'item1',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000002-item2.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000002',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000001', 'title': 'item1'},
                ],
            },
            'meta': {
                'id': '20200101000000002',
                'type': 'folder',
                'title': 'item2',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000003-item3.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000003',
                'timestamp': '20230101000000003',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000001', 'title': 'item1'},
                ],
            },
            'meta': {
                'id': '20200101000000003',
                'type': 'folder',
                'title': 'item3',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000004-item2.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000004',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000000', 'title': 'item0'},
                    {'id': '20200101000000001', 'title': 'item1'},
                ],
            },
            'meta': {
                'id': '20200101000000002',
                'type': 'folder',
                'title': 'item2',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000005-item1.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000001',
                'timestamp': '20230101000000005',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                ],
            },
            'meta': {
                'id': '20200101000000001',
                'type': 'folder',
                'title': 'item1',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000006-item2.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000006',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'item1'},
                ],
            },
            'meta': {
                'id': '20200101000000002',
                'type': 'folder',
                'title': 'item2',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000007-item3.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000003',
                'timestamp': '20230101000000007',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'item1'},
                ],
            },
            'meta': {
                'id': '20200101000000003',
                'type': 'folder',
                'title': 'item3',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })

        self.assertEqual(self.read_exported_archive(os.path.join(self.test_output, '20230101000000008-item2.wsba')), {
            'export_info': {
                'version': 1,
                'id': '20230101000000002',
                'timestamp': '20230101000000008',
                'timezone': mock.ANY,
                'path': [
                    {'id': 'root', 'title': ''},
                    {'id': '20200101000000001', 'title': 'item1'},
                ],
            },
            'meta': {
                'id': '20200101000000002',
                'type': 'folder',
                'title': 'item2',
            },
            'index_data': mock.ANY,
            'favicon_data': mock.ANY,
        })


if __name__ == '__main__':
    unittest.main()
