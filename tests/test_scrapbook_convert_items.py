import os
import tempfile
import unittest
from base64 import b64decode
from email.utils import format_datetime
from unittest import mock

from webscrapbook import WSB_DIR, util
from webscrapbook._polyfill import zipfile
from webscrapbook.scrapbook.convert import items as conv_items
from webscrapbook.scrapbook.host import Host

from . import TEMP_DIR, TestBookMixin, glob_files


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='items-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)

    # mock out user config
    global mockings
    mockings = (
        mock.patch('webscrapbook.Config.user_config_dir', return_value=os.devnull),
        mock.patch('webscrapbook.Config.user_config', return_value=os.devnull),
    )
    for mocking in mockings:
        mocking.start()


def tearDownModule():
    # cleanup the temp directory
    _tmpdir.cleanup()

    # stop mock
    for mocking in mockings:
        mocking.stop()


class TestRun(TestBookMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_input = os.path.join(self.test_root, 'input')
        self.test_input_tree = os.path.join(self.test_input, WSB_DIR, 'tree')
        self.test_output = os.path.join(self.test_root, 'output')

        os.makedirs(self.test_input_tree, exist_ok=True)

    def test_param_type(self):
        """Check type filter
        """
        types = ['', 'site', 'image', 'file', 'combine', 'note', 'postit', 'bookmark', 'folder', 'separator']
        for type in types:
            with self.subTest(type=type):
                self.setUp()
                try:
                    self.init_book(self.test_input, meta={
                        '20200101000000000': {
                            'type': type,
                            'index': '20200101000000000/index.html',
                        },
                    })

                    index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
                    os.makedirs(os.path.dirname(index_file), exist_ok=True)
                    with open(index_file, 'w', encoding='UTF-8') as fh:
                        fh.write("""dummy""")

                    for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=[type]):
                        pass

                    self.assertEqual(glob_files(self.test_output), {
                        os.path.join(self.test_output, '20200101000000000.htz'),
                    })
                finally:
                    self.tearDown()

                self.setUp()
                try:
                    self.init_book(self.test_input, meta={
                        '20200101000000000': {
                            'type': type,
                            'index': '20200101000000000/index.html',
                        },
                    })

                    index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
                    os.makedirs(os.path.dirname(index_file), exist_ok=True)
                    with open(index_file, 'w', encoding='UTF-8') as fh:
                        fh.write("""dummy""")

                    for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=[]):
                        pass

                    self.assertEqual(glob_files(self.test_output), {
                        os.path.join(self.test_output, '20200101000000000'),
                        os.path.join(self.test_output, '20200101000000000', 'index.html'),
                    })
                finally:
                    self.tearDown()

    def _test_param_format_sample(self):
        """Generate sample files for test_param_format_*
        """
        self.init_book(self.test_input, meta={
            '20200101000000001': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000001/index.html',
            },
            '20200101000000002': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000002.htz',
            },
            '20200101000000003': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000003.maff',
            },
            '20200101000000004': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000004.html',
            },
            '20200101000000005': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000005.txt',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000001')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
<img src="resource.bmp">
my page content
""")
        with open(os.path.join(index_dir, 'resource.bmp'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """\
<img src="resource.bmp">
my page content
""")
            zh.writestr('resource.bmp', b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000003/index.html', """\
<img src="resource.bmp">
my page content
""")
            zh.writestr('20200101000000003/index.rdf', """dummy""")
            zh.writestr('20200101000000003/resource.bmp', b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        index_file = os.path.join(self.test_input, '20200101000000004.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<img src="data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA">
my page content
""")

        index_file = os.path.join(self.test_input, '20200101000000005.txt')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

    def test_param_format_folder_basic(self):
        """Test format "folder"

        - Folder converted from MAFF should not contain index.rdf
        """
        self._test_param_format_sample()

        for _info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000001'),
            os.path.join(self.test_output, '20200101000000001', 'index.html'),
            os.path.join(self.test_output, '20200101000000001', 'resource.bmp'),
            os.path.join(self.test_output, '20200101000000002'),
            os.path.join(self.test_output, '20200101000000002', 'index.html'),
            os.path.join(self.test_output, '20200101000000002', 'resource.bmp'),
            os.path.join(self.test_output, '20200101000000003'),
            os.path.join(self.test_output, '20200101000000003', 'index.html'),
            os.path.join(self.test_output, '20200101000000003', 'resource.bmp'),
            os.path.join(self.test_output, '20200101000000004'),
            os.path.join(self.test_output, '20200101000000004', 'index.html'),
            os.path.join(self.test_output, '20200101000000004', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'),
            os.path.join(self.test_output, '20200101000000005'),
            os.path.join(self.test_output, '20200101000000005', 'index.html'),
            os.path.join(self.test_output, '20200101000000005', '20200101000000005.txt'),
        })

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000001', 'index.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000001', 'index.html')).st_mtime,
        )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000002.htz')) as zh:
            self.assertEqual(
                util.fs.zip_timestamp(zh.getinfo('index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000002', 'index.html')).st_mtime,
            )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000003.maff')) as zh:
            self.assertEqual(
                util.fs.zip_timestamp(zh.getinfo('20200101000000003/index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000003', 'index.html')).st_mtime,
            )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000004.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000004', 'index.html')).st_mtime,
        )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000005.txt')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000005', 'index.html')).st_mtime,
        )

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000001/index.html',
            },
            '20200101000000002': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000002/index.html',
            },
            '20200101000000003': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000003/index.html',
            },
            '20200101000000004': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000004/index.html',
            },
            '20200101000000005': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000005/index.html',
            },
        })

    def test_param_format_folder_icon_from_htz(self):
        """Check if icon path is correctly handled for htz => folder.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.htz',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000'),
            os.path.join(self.test_output, '20200101000000000', 'index.html'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': '../.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_folder_icon_from_maff(self):
        """Check if icon path is correctly handled for maff => folder.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """my page content""")
            zh.writestr('20200101000000000/index.rdf', """dummy""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000'),
            os.path.join(self.test_output, '20200101000000000', 'index.html'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': '../.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_folder_icon_from_sf(self):
        """Check if icon path is correctly handled for single_file => folder.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000'),
            os.path.join(self.test_output, '20200101000000000', 'index.html'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': '../.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_htz_basic(self):
        """Test format "htz"

        - HTZ converted from MAFF should not contain index.rdf
        """
        self._test_param_format_sample()

        for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000001.htz'),
            os.path.join(self.test_output, '20200101000000002.htz'),
            os.path.join(self.test_output, '20200101000000003.htz'),
            os.path.join(self.test_output, '20200101000000004.htz'),
            os.path.join(self.test_output, '20200101000000005.htz'),
        })

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000001.htz')) as zh:
            self.assertEqual(set(zh.namelist()), {'index.html', 'resource.bmp'})

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000003.htz')) as zh:
            self.assertEqual(set(zh.namelist()), {'index.html', 'resource.bmp'})

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000004.htz')) as zh:
            self.assertEqual(set(zh.namelist()), {'index.html', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'})

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000005.htz')) as zh:
            self.assertEqual(set(zh.namelist()), {'index.html', '20200101000000005.txt'})

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000001', 'index.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000001.htz')).st_mtime,
        )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000002.htz')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000002.htz')).st_mtime,
        )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000003.maff')) as zh:
            self.assertEqual(
                util.fs.zip_timestamp(zh.getinfo('20200101000000003/index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000003.htz')).st_mtime,
            )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000004.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000004.htz')).st_mtime,
        )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000005.txt')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000005.htz')).st_mtime,
        )

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000001.htz',
            },
            '20200101000000002': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000002.htz',
            },
            '20200101000000003': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000003.htz',
            },
            '20200101000000004': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000004.htz',
            },
            '20200101000000005': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000005.htz',
            },
        })

    def test_param_format_htz_icon_from_folder(self):
        """Check if icon path is correctly handled for folder => htz.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.ico',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.htz'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.htz',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.ico',
            },
        })

    def test_param_format_htz_icon_from_maff(self):
        """Check if icon path is correctly handled for maff => htz.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """my page content""")
            zh.writestr('20200101000000000/index.rdf', """dummy""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.htz'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.htz',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_htz_icon_from_sf(self):
        """Check if icon path is correctly handled for single_file => htz.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_maff_basic(self):
        """Test format "maff"

        - MAFF converted from other format should contain a valid index.rdf
        """
        self._test_param_format_sample()

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000001.maff'),
            os.path.join(self.test_output, '20200101000000002.maff'),
            os.path.join(self.test_output, '20200101000000003.maff'),
            os.path.join(self.test_output, '20200101000000004.maff'),
            os.path.join(self.test_output, '20200101000000005.maff'),
        })

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000001.maff')) as zh:
            self.assertEqual(set(zh.namelist()), {
                '20200101000000001/',
                '20200101000000001/index.html',
                '20200101000000001/index.rdf',
                '20200101000000001/resource.bmp',
            })
            with zh.open('20200101000000001/index.rdf') as fh:
                dt = util.id_to_datetime('20200101000000000').astimezone()
                self.assertEqual(
                    util.parse_maff_index_rdf(fh),
                    ('', '', format_datetime(dt), 'index.html', 'UTF-8'),
                )

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000002.maff')) as zh:
            self.assertEqual(set(zh.namelist()), {
                '20200101000000002/',
                '20200101000000002/index.html',
                '20200101000000002/index.rdf',
                '20200101000000002/resource.bmp',
            })
            with zh.open('20200101000000002/index.rdf') as fh:
                dt = util.id_to_datetime('20200101000000000').astimezone()
                self.assertEqual(
                    util.parse_maff_index_rdf(fh),
                    ('', '', format_datetime(dt), 'index.html', 'UTF-8'),
                )

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000004.maff')) as zh:
            self.assertEqual(set(zh.namelist()), {
                '20200101000000004/',
                '20200101000000004/index.html',
                '20200101000000004/index.rdf',
                '20200101000000004/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            })
            with zh.open('20200101000000004/index.rdf') as fh:
                dt = util.id_to_datetime('20200101000000000').astimezone()
                self.assertEqual(
                    util.parse_maff_index_rdf(fh),
                    ('', '', format_datetime(dt), 'index.html', 'UTF-8'),
                )

        with zipfile.ZipFile(os.path.join(self.test_output, '20200101000000005.maff')) as zh:
            self.assertEqual(set(zh.namelist()), {
                '20200101000000005/',
                '20200101000000005/index.html',
                '20200101000000005/index.rdf',
                '20200101000000005/20200101000000005.txt',
            })
            with zh.open('20200101000000005/index.rdf') as fh:
                dt = util.id_to_datetime('20200101000000000').astimezone()
                self.assertEqual(
                    util.parse_maff_index_rdf(fh),
                    ('', '', format_datetime(dt), 'index.html', 'UTF-8'),
                )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000001', 'index.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000001.maff')).st_mtime,
        )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000002.htz')) as zh:
            self.assertEqual(
                util.fs.zip_timestamp(zh.getinfo('index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000002.maff')).st_mtime,
            )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000003.maff')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000003.maff')).st_mtime,
        )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000004.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000004.maff')).st_mtime,
        )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000005.txt')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000005.maff')).st_mtime,
        )

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001.maff',
                'create': '20200101000000000',
            },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002.maff',
                'create': '20200101000000000',
            },
            '20200101000000003': {
                'type': '',
                'index': '20200101000000003.maff',
                'create': '20200101000000000',
            },
            '20200101000000004': {
                'type': '',
                'index': '20200101000000004.maff',
                'create': '20200101000000000',
            },
            '20200101000000005': {
                'type': '',
                'index': '20200101000000005.maff',
                'create': '20200101000000000',
            },
        })

    def test_param_format_maff_fail_existing_index_rdf(self):
        """Fail if index.rdf already exists
        """
        self.init_book(self.test_input, meta={
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
            },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002.htz',
            },
            '20200101000000003': {
                'type': '',
                'index': '20200101000000003.maff',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000001')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'index.rdf'), 'w', encoding='UTF-8') as fh:
            fh.write("""dummy""")
        with open(os.path.join(index_dir, 'resource.txt'), 'w', encoding='UTF-8') as fh:
            fh.write("""dummy""")

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")
            zh.writestr('index.rdf', """dummy""")
            zh.writestr('resource.txt', """dummy""")

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000003/index.html', """my page content""")
            zh.writestr('20200101000000003/index.rdf', """dummy""")
            zh.writestr('20200101000000003/resource.txt', """dummy""")

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000001'),
            os.path.join(self.test_output, '20200101000000001', 'index.html'),
            os.path.join(self.test_output, '20200101000000001', 'index.rdf'),
            os.path.join(self.test_output, '20200101000000001', 'resource.txt'),
            os.path.join(self.test_output, '20200101000000002.htz'),
            os.path.join(self.test_output, '20200101000000003.maff'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001/index.html',
            },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002.htz',
            },
            '20200101000000003': {
                'type': '',
                'index': '20200101000000003.maff',
            },
        })

    def test_param_format_maff_icon_from_folder(self):
        """Check if icon path is correctly handled for folder => maff.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.ico',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.maff'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.ico',
            },
        })

    def test_param_format_maff_icon_from_htz(self):
        """Check if icon path is correctly handled for htz => maff.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.htz',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.maff'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_maff_icon_from_sf(self):
        """Check if icon path is correctly handled for single_file => maff.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.maff'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_single_file_basic(self):
        """Test format "single_file"
        """
        self._test_param_format_sample()

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000001.html'),
            os.path.join(self.test_output, '20200101000000002.html'),
            os.path.join(self.test_output, '20200101000000003.html'),
            os.path.join(self.test_output, '20200101000000004.html'),
            os.path.join(self.test_output, '20200101000000005.txt'),
        })

        with open(os.path.join(self.test_output, '20200101000000001.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """\
<img src="data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA">
my page content
""")

        with open(os.path.join(self.test_output, '20200101000000002.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """\
<img src="data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA">
my page content
""")

        with open(os.path.join(self.test_output, '20200101000000003.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """\
<img src="data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA">
my page content
""")

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000001', 'index.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000001.html')).st_mtime,
        )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000002.htz')) as zh:
            self.assertEqual(
                util.fs.zip_timestamp(zh.getinfo('index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000002.html')).st_mtime,
            )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000003.maff')) as zh:
            self.assertEqual(
                util.fs.zip_timestamp(zh.getinfo('20200101000000003/index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000003.html')).st_mtime,
            )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000004.html')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000004.html')).st_mtime,
        )

        self.assertEqual(
            os.stat(os.path.join(self.test_input, '20200101000000005.txt')).st_mtime,
            os.stat(os.path.join(self.test_output, '20200101000000005.txt')).st_mtime,
        )

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000001.html',
            },
            '20200101000000002': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000002.html',
            },
            '20200101000000003': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000003.html',
            },
            '20200101000000004': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000004.html',
            },
            '20200101000000005': {
                'type': '',
                'create': '20200101000000000',
                'index': '20200101000000005.txt',
            },
        })

    def test_param_format_single_file_icon_from_folder(self):
        """Check if icon path is correctly handled for folder => single_file.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.ico',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.ico',
            },
        })

    def test_param_format_single_file_icon_from_htz(self):
        """Check if icon path is correctly handled for htz => single_file.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.htz',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_single_file_icon_from_maff(self):
        """Check if icon path is correctly handled for maff => single_file.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.maff',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

        index_file = os.path.join(self.test_input, '20200101000000000.maff')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """my page content""")
            zh.writestr('20200101000000000/index.rdf', """dummy""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        self.assertEqual(glob_files(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon')), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', 'favicon.ico'),
        })

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
                'icon': '.wsb/tree/favicon/favicon.ico',
            },
        })

    def test_param_format_single_file_meta_refresh(self):
        """Check if meta refresh is resolved recursively.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)

        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<meta http-equiv="refresh" content="0; url=./refresh1.html">""")

        with open(os.path.join(index_dir, 'refresh1.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<meta http-equiv="refresh" content="0; url=./refresh2.html">""")

        with open(os.path.join(index_dir, 'refresh2.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""page content""")

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        with open(os.path.join(self.test_output, '20200101000000000.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """page content""")

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
            },
        })

    def test_param_format_single_file_meta_refresh_svg(self):
        """Check if meta refresh target is non-HTML, and SVG rewriting.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)

        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<meta http-equiv="refresh" content="0; url=./target.svg">""")

        with open(os.path.join(index_dir, 'target.svg'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg">
  <image href="./image.bmp"/>
</svg>
""")

        with open(os.path.join(index_dir, 'image.bmp'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.svg'),
        })

        with open(os.path.join(self.test_output, '20200101000000000.svg'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """\
<?xml version="1.0"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg">
  <image href="data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA" />
</svg>
""")

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.svg',
            },
        })

    def test_param_format_single_file_meta_refresh_delayed(self):
        """Check that a deleyed meta refresh should not be resolved.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)

        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<meta http-equiv="refresh" content="1; url=./target.html">""")

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        with open(os.path.join(self.test_output, '20200101000000000.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """<meta http-equiv="refresh" content="1; url=urn:scrapbook:convert:skip:url:./target.html">""")

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
            },
        })

    def test_param_format_single_file_meta_refresh_absolute(self):
        """Check that a meta refresh to an absolute URL should not be resolved.
        """
        self.init_book(self.test_input, meta={
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
            },
        })

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)

        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<meta http-equiv="refresh" content="0; url=http://example.com">""")

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        with open(os.path.join(self.test_output, '20200101000000000.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), """<meta http-equiv="refresh" content="0; url=http://example.com">""")

        book = Host(self.test_output).books['']
        book.load_meta_files()
        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000.html',
            },
        })


if __name__ == '__main__':
    unittest.main()
