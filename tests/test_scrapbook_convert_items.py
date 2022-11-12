import glob
import os
import tempfile
import unittest
import zipfile
from base64 import b64decode
from email.utils import format_datetime
from unittest import mock

from webscrapbook import WSB_DIR, util
from webscrapbook.scrapbook.convert import items as conv_items
from webscrapbook.scrapbook.host import Host

from . import TEMP_DIR


def setUpModule():
    """Set up a temp directory for testing."""
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='items-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)

    # mock out user config
    global mockings
    mockings = [
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(tmpdir, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_DIR', os.path.join(tmpdir, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_CONFIG', tmpdir),
    ]
    for mocking in mockings:
        mocking.start()


def tearDownModule():
    """Cleanup the temp directory."""
    _tmpdir.cleanup()

    # stop mock
    for mocking in mockings:
        mocking.stop()


class TestRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_input = os.path.join(self.test_root, 'input')
        self.test_input_config = os.path.join(self.test_input, WSB_DIR, 'config.ini')
        self.test_input_tree = os.path.join(self.test_input, WSB_DIR, 'tree')
        self.test_input_meta = os.path.join(self.test_input_tree, 'meta.js')
        self.test_input_toc = os.path.join(self.test_input_tree, 'toc.js')
        self.test_output = os.path.join(self.test_root, 'output')
        self.test_output_tree = os.path.join(self.test_output, WSB_DIR, 'tree')
        self.test_output_meta = os.path.join(self.test_output_tree, 'meta.js')
        self.test_output_toc = os.path.join(self.test_output_tree, 'toc.js')

        os.makedirs(self.test_input_tree, exist_ok=True)
        os.makedirs(self.test_output, exist_ok=True)

    def test_param_type(self):
        """Check type filter
        """
        types = ['', 'site', 'image', 'file', 'combine', 'note', 'postit', 'bookmark', 'folder', 'separator']
        for type in types:
            with self.subTest(type=type):
                self.setUp()
                try:
                    with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
                        fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "%s",
    "index": "20200101000000000/index.html"
  }
})""" % type)

                    index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
                    os.makedirs(os.path.dirname(index_file), exist_ok=True)
                    with open(index_file, 'w', encoding='UTF-8') as fh:
                        fh.write("""dummy""")

                    for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=[type]):
                        pass

                    self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
                        os.path.join(self.test_output, ''),
                        os.path.join(self.test_output, '20200101000000000.htz'),
                    })
                finally:
                    self.tearDown()

                self.setUp()
                try:
                    with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
                        fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "%s",
    "index": "20200101000000000/index.html"
  }
})""" % type)

                    index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
                    os.makedirs(os.path.dirname(index_file), exist_ok=True)
                    with open(index_file, 'w', encoding='UTF-8') as fh:
                        fh.write("""dummy""")

                    for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=[]):
                        pass

                    self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
                        os.path.join(self.test_output, ''),
                        os.path.join(self.test_output, '20200101000000000'),
                        os.path.join(self.test_output, '20200101000000000', 'index.html'),
                    })
                finally:
                    self.tearDown()

    def _test_param_format_sample(self):
        """Generate sample files for test_param_format_*
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000001/index.html"
  },
  "20200101000000002": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000002.htz"
  },
  "20200101000000003": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000003.maff"
  },
  "20200101000000004": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000004.html"
  },
  "20200101000000005": {
    "type": "",
    "create": "20200101000000000",
    "index": "20200101000000005.txt"
  }
})""")

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

    def test_param_format_folder01(self):
        """Test format "folder"

        - Folder converted from MAFF should not contain index.rdf
        """
        self._test_param_format_sample()

        for _info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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
                util.zip_timestamp(zh.getinfo('index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000002', 'index.html')).st_mtime,
            )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000003.maff')) as zh:
            self.assertEqual(
                util.zip_timestamp(zh.getinfo('20200101000000003/index.html')),
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

    def test_param_format_folder02(self):
        """Check if icon path is correctly handled for htz => folder.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.htz",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000'),
            os.path.join(self.test_output, '20200101000000000', 'index.html'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_folder03(self):
        """Check if icon path is correctly handled for maff => folder.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.maff",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

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

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000'),
            os.path.join(self.test_output, '20200101000000000', 'index.html'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_folder04(self):
        """Check if icon path is correctly handled for single_file => folder.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.html",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='folder', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000'),
            os.path.join(self.test_output, '20200101000000000', 'index.html'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_htz01(self):
        """Test format "htz"

        - HTZ converted from MAFF should not contain index.rdf
        """
        self._test_param_format_sample()

        for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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
                util.zip_timestamp(zh.getinfo('20200101000000003/index.html')),
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

    def test_param_format_htz02(self):
        """Check if icon path is correctly handled for folder => htz.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "favicon.ico"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='htz', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.htz'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_htz03(self):
        """Check if icon path is correctly handled for maff => htz.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.maff",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

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

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.htz'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_htz04(self):
        """Check if icon path is correctly handled for single_file => htz.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.html",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_maff01(self):
        """Test format "maff"

        - MAFF converted from other format should contain a valid index.rdf
        """
        self._test_param_format_sample()

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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
                util.zip_timestamp(zh.getinfo('index.html')),
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

    def test_param_format_maff02(self):
        """Fail if index.rdf already exists
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "",
    "index": "20200101000000001/index.html"
  },
  "20200101000000002": {
    "type": "",
    "index": "20200101000000002.htz"
  },
  "20200101000000003": {
    "type": "",
    "index": "20200101000000003.maff"
  }
})""")

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

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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

    def test_param_format_maff03(self):
        """Check if icon path is correctly handled for folder => maff.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "favicon.ico"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.maff'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_maff04(self):
        """Check if icon path is correctly handled for htz => maff.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.htz",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.maff'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_maff05(self):
        """Check if icon path is correctly handled for single_file => maff.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.html",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='maff', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.maff'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_single_file01(self):
        """Test format "single_file"
        """
        self._test_param_format_sample()

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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
                util.zip_timestamp(zh.getinfo('index.html')),
                os.stat(os.path.join(self.test_output, '20200101000000002.html')).st_mtime,
            )

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000003.maff')) as zh:
            self.assertEqual(
                util.zip_timestamp(zh.getinfo('20200101000000003/index.html')),
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

    def test_param_format_single_file02(self):
        """Check if icon path is correctly handled for folder => single_file.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "favicon.ico"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""my page content""")
        with open(os.path.join(index_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_single_file03(self):
        """Check if icon path is correctly handled for htz => single_file.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.htz",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """my page content""")

        favicon_dir = os.path.join(self.test_input_tree, 'favicon')
        os.makedirs(favicon_dir, exist_ok=True)
        with open(os.path.join(favicon_dir, 'favicon.ico'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_single_file04(self):
        """Check if icon path is correctly handled for maff => single_file.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000.maff",
    "icon": ".wsb/tree/favicon/favicon.ico"
  }
})""")

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

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20200101000000000.html'),
        })

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', '**'), recursive=True)), {
            os.path.join(self.test_output, WSB_DIR, 'tree', 'favicon', ''),
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

    def test_param_format_single_file05(self):
        """Check if meta refresh is resolved recursively.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html"
  }
})""")

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

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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

    def test_param_format_single_file06(self):
        """Check if meta refresh target is non-HTML, and SVG rewriting.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html"
  }
})""")

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

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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

    def test_param_format_single_file07(self):
        """Check that a deleyed meta refresh should not be resolved.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)

        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<meta http-equiv="refresh" content="1; url=./target.html">""")

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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

    def test_param_format_single_file08(self):
        """Check that a meta refresh to an absolute URL should not be resolved.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html"
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)

        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write("""<meta http-equiv="refresh" content="0; url=http://example.com">""")

        for _info in conv_items.run(self.test_input, self.test_output, format='single_file', types=['']):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
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
