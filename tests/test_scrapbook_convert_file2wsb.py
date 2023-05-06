import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from webscrapbook._polyfill import zipfile
from webscrapbook.scrapbook.convert import file2wsb
from webscrapbook.scrapbook.host import Host

from . import TEMP_DIR, glob_files


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='file2wsb-', dir=TEMP_DIR)
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


class TestRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_input = os.path.join(self.test_root, 'input')
        self.test_output = os.path.join(self.test_root, 'output')
        self.test_output_tree = os.path.join(self.test_output, 'tree')
        self.test_output_meta = os.path.join(self.test_output_tree, 'meta.js')
        self.test_output_toc = os.path.join(self.test_output_tree, 'toc.js')

        os.makedirs(self.test_input, exist_ok=True)

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_path01(self):
        """Test hierarchical folders for */index.html
        """
        index_file = os.path.join(self.test_input, 'folder1#中文', 'folder2', 'folder_data', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
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

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000002': {
                'title': 'folder2',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000003': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000003/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
            '20220101000000001': [
                '20220101000000002',
            ],
            '20220101000000002': [
                '20220101000000003',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000003'),
            os.path.join(self.test_output, '20220101000000003', 'index.html'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_path02(self):
        """Test hierarchical folders for *.html
        """
        index_file = os.path.join(self.test_input, 'folder1#中文', 'folder2', 'mypage.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
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

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000002': {
                'title': 'folder2',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000003': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000003/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
            '20220101000000001': [
                '20220101000000002',
            ],
            '20220101000000002': [
                '20220101000000003',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000003'),
            os.path.join(self.test_output, '20220101000000003', 'index.html'),
            os.path.join(self.test_output, '20220101000000003', 'mypage.html'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_path03(self):
        """Test hierarchical folders for *.html (preserve_filename=False)
        """
        index_file = os.path.join(self.test_input, 'folder1#中文', 'folder2', 'mypage.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
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

        for _info in file2wsb.run(self.test_input, self.test_output, preserve_filename=False):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000002': {
                'title': 'folder2',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000003': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000003.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
            '20220101000000001': [
                '20220101000000002',
            ],
            '20220101000000002': [
                '20220101000000003',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000003.html'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_path04(self):
        """<input dir>/index.html should be indexed as single html page
        """
        index_file = os.path.join(self.test_input, 'index.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
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

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000001/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000001'),
            os.path.join(self.test_output, '20220101000000001', 'index.html'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_path05(self):
        """<input dir>/index.html should be indexed as single html page (preserve_filename=False)
        """
        index_file = os.path.join(self.test_input, 'index.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
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

        for _info in file2wsb.run(self.test_input, self.test_output, preserve_filename=False):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000001.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000001.html'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_supporting_folder01(self):
        """Test for supporting folder *.files
        """
        index_file = os.path.join(self.test_input, 'mypage.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
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
<img src="mypage.files/picture.bmp">
</body>
</html>
""")
        img_file = os.path.join(self.test_input, 'mypage.files', 'picture.bmp')
        os.makedirs(os.path.dirname(img_file), exist_ok=True)
        with open(img_file, 'wb') as fh:
            fh.write(b'dummy')

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000001/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000001'),
            os.path.join(self.test_output, '20220101000000001', 'index.html'),
            os.path.join(self.test_output, '20220101000000001', 'mypage.html'),
            os.path.join(self.test_output, '20220101000000001', 'mypage.files'),
            os.path.join(self.test_output, '20220101000000001', 'mypage.files', 'picture.bmp'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_supporting_folder02(self):
        """Test for supporting folder *_files
        """
        index_file = os.path.join(self.test_input, 'mypage.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
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
<img src="mypage_files/picture.bmp">
</body>
</html>
""")
        img_file = os.path.join(self.test_input, 'mypage_files', 'picture.bmp')
        os.makedirs(os.path.dirname(img_file), exist_ok=True)
        with open(img_file, 'wb') as fh:
            fh.write(b'dummy')

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000001/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000001'),
            os.path.join(self.test_output, '20220101000000001', 'index.html'),
            os.path.join(self.test_output, '20220101000000001', 'mypage.html'),
            os.path.join(self.test_output, '20220101000000001', 'mypage_files'),
            os.path.join(self.test_output, '20220101000000001', 'mypage_files', 'picture.bmp'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_supporting_folder03(self):
        """Test for index.html + index.files
        """
        content = """\
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
<img src="index.files/picture.bmp">
</body>
</html>
"""
        index_file = os.path.join(self.test_input, 'index.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write(content)
        img_file = os.path.join(self.test_input, 'index.files', 'picture.bmp')
        os.makedirs(os.path.dirname(img_file), exist_ok=True)
        with open(img_file, 'wb') as fh:
            fh.write(b'dummy')

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000001/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000001'),
            os.path.join(self.test_output, '20220101000000001', 'index.html'),
            os.path.join(self.test_output, '20220101000000001', 'index.files'),
            os.path.join(self.test_output, '20220101000000001', 'index.files', 'picture.bmp'),
        })
        with open(os.path.join(self.test_output, '20220101000000001', 'index.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), content)

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_supporting_folder04(self):
        """Test for custom supporting folder (data_folder_suffixes set)
        """
        index_file = os.path.join(self.test_input, 'mypage.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
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
<img src="mypage_archive/picture.bmp">
</body>
</html>
""")
        img_file = os.path.join(self.test_input, 'mypage_archive', 'picture.bmp')
        os.makedirs(os.path.dirname(img_file), exist_ok=True)
        with open(img_file, 'wb') as fh:
            fh.write(b'dummy')

        for _info in file2wsb.run(self.test_input, self.test_output, data_folder_suffixes=['_archive']):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000001/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000001'),
            os.path.join(self.test_output, '20220101000000001', 'index.html'),
            os.path.join(self.test_output, '20220101000000001', 'mypage.html'),
            os.path.join(self.test_output, '20220101000000001', 'mypage_archive'),
            os.path.join(self.test_output, '20220101000000001', 'mypage_archive', 'picture.bmp'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_supporting_folder05(self):
        """Test for custom supporting folder (data_folder_suffixes not set)
        """
        index_file = os.path.join(self.test_input, 'mypage.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
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
<img src="mypage_archive/picture.bmp">
</body>
</html>
""")
        img_file = os.path.join(self.test_input, 'mypage_archive', 'picture.bmp')
        os.makedirs(os.path.dirname(img_file), exist_ok=True)
        with open(img_file, 'wb') as fh:
            fh.write(b'dummy')
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(img_file, (ts, ts))

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000001/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
            '20220101000000002': {
                'title': 'mypage_archive',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000003': {
                'title': 'picture.bmp',
                'type': 'file',
                'index': '20220101000000003/index.html',
                'create': '20220101000000003',
                'modify': '20200102030405067',
                'source': '',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
                '20220101000000002',
            ],
            '20220101000000002': [
                '20220101000000003',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000001'),
            os.path.join(self.test_output, '20220101000000001', 'index.html'),
            os.path.join(self.test_output, '20220101000000001', 'mypage.html'),
            os.path.join(self.test_output, '20220101000000003'),
            os.path.join(self.test_output, '20220101000000003', 'index.html'),
            os.path.join(self.test_output, '20220101000000003', 'picture.bmp'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_htz(self):
        """Test hierarchical folders for *.htz
        """
        index_file = os.path.join(self.test_input, 'folder1#中文', 'mypage.htz')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', """\
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

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000002': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000002.htz',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
            '20220101000000001': [
                '20220101000000002',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000002.htz'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_maff(self):
        """Test hierarchical folders for *.maff
        """
        index_file = os.path.join(self.test_input, 'folder1#中文', 'mypage.maff')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('20200101000000000/index.html', """\
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

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000002': {
                'title': 'MyTitle 中文',
                'type': '',
                'index': '20220101000000002.maff',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
            '20220101000000001': [
                '20220101000000002',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000002.maff'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_other01(self):
        """Test hierarchical folders for normal file
        """
        index_file = os.path.join(self.test_input, 'folder1#中文', 'mypage.txt')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('ABC 中文')
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(index_file, (ts, ts))

        for _info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000002': {
                'title': 'mypage.txt',
                'type': 'file',
                'index': '20220101000000002/index.html',
                'create': '20220101000000002',
                'modify': '20200102030405067',
                'source': '',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
            '20220101000000001': [
                '20220101000000002',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000002'),
            os.path.join(self.test_output, '20220101000000002', 'index.html'),
            os.path.join(self.test_output, '20220101000000002', 'mypage.txt'),
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20220101000000001')
    def test_other02(self):
        """Test hierarchical folders for normal file (preserve_filename=False)
        """
        index_file = os.path.join(self.test_input, 'folder1#中文', 'mypage.txt')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('ABC 中文')
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(index_file, (ts, ts))

        for _info in file2wsb.run(self.test_input, self.test_output, preserve_filename=False):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        self.assertDictEqual(book.meta, {
            '20220101000000001': {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': '20220101000000001',
                'modify': '20220101000000001',
            },
            '20220101000000002': {
                'title': 'mypage.txt',
                'type': 'file',
                'index': '20220101000000002.txt',
                'create': '20220101000000002',
                'modify': '20200102030405067',
                'source': '',
                'icon': '',
                'comment': '',
            },
        })
        self.assertDictEqual(book.toc, {
            'root': [
                '20220101000000001',
            ],
            '20220101000000001': [
                '20220101000000002',
            ],
        })
        self.assertEqual(glob_files(self.test_output), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '20220101000000002.txt'),
        })

    @mock.patch('webscrapbook.scrapbook.convert.file2wsb.Indexer', side_effect=SystemExit)
    def test_ignore_meta(self, mock_obj):
        """Test ignore_*_meta params"""
        index_file = os.path.join(self.test_input, 'mypage.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
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

        try:
            for _info in file2wsb.run(
                self.test_input, self.test_output,
                handle_ie_meta=False,
                handle_singlefile_meta=False,
                handle_savepagewe_meta=False,
                handle_maoxian_meta=False,
            ):
                pass
        except SystemExit:
            pass

        mock_obj.assert_called_with(
            mock.ANY,
            handle_ie_meta=False,
            handle_singlefile_meta=False,
            handle_savepagewe_meta=False,
            handle_maoxian_meta=False,
        )


if __name__ == '__main__':
    unittest.main()
