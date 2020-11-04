from unittest import mock
import unittest
import os
import shutil
import glob
import time

from lxml import etree

from webscrapbook import WSB_DIR
from webscrapbook import util
from webscrapbook.scrapbook.host import Host
from webscrapbook.scrapbook.convert import file2wsb

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_scrapbook_convert')

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

class TestRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192
        cls.test_input = os.path.join(test_root, 'input')
        cls.test_output = os.path.join(test_root, 'output')
        cls.test_output_tree = os.path.join(cls.test_output, 'tree')
        cls.test_output_meta = os.path.join(cls.test_output_tree, 'meta.js')
        cls.test_output_toc = os.path.join(cls.test_output_tree, 'toc.js')

    def setUp(self):
        """Set up a general temp test folder
        """
        os.makedirs(self.test_input, exist_ok=True)
        os.makedirs(self.test_output, exist_ok=True)

    def tearDown(self):
        """Remove general temp test folder
        """
        try:
            shutil.rmtree(self.test_input)
        except NotADirectoryError:
            os.remove(self.test_input)
        except FileNotFoundError:
            pass

        try:
            shutil.rmtree(self.test_output)
        except NotADirectoryError:
            os.remove(self.test_output)
        except FileNotFoundError:
            pass

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

        for info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        ids = list(book.meta.keys())
        id_folder1 = ids[0]
        id_folder2 = ids[1]
        id_item = ids[2]
        self.assertDictEqual(book.meta, {
            id_folder1: {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': id_folder1,
                'modify': id_folder1,
                },
            id_folder2: {
                'title': 'folder2',
                'type': 'folder',
                'create': id_folder2,
                'modify': id_folder2,
                },
            id_item: {
                'title': 'MyTitle 中文',
                'type': '',
                'index': f'{id_item}/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
                },
            })
        self.assertDictEqual(book.toc, {
            'root': [
                id_folder1,
                ],
            id_folder1: [
                id_folder2,
                ],
            id_folder2: [
                id_item,
                ],
            })
        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, id_item),
            os.path.join(self.test_output, id_item, 'index.html'),
            })

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

        for info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        ids = list(book.meta.keys())
        id_folder1 = ids[0]
        id_folder2 = ids[1]
        id_item = ids[2]
        self.assertDictEqual(book.meta, {
            id_folder1: {
                'title': 'folder1#中文',
                'type': 'folder',
                'create': id_folder1,
                'modify': id_folder1,
                },
            id_folder2: {
                'title': 'folder2',
                'type': 'folder',
                'create': id_folder2,
                'modify': id_folder2,
                },
            id_item: {
                'title': 'MyTitle 中文',
                'type': '',
                'index': f'{id_item}.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
                },
            })
        self.assertDictEqual(book.toc, {
            'root': [
                id_folder1,
                ],
            id_folder1: [
                id_folder2,
                ],
            id_folder2: [
                id_item,
                ],
            })
        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, f'{id_item}.html'),
            })

    def test_path03(self):
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

        for info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        ids = list(book.meta.keys())
        id_item = ids[0]
        self.assertDictEqual(book.meta, {
            id_item: {
                'title': 'MyTitle 中文',
                'type': '',
                'index': f'{id_item}.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
                },
            })
        self.assertDictEqual(book.toc, {
            'root': [
                id_item,
                ],
            })
        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, f'{id_item}.html'),
            })

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

        for info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        ids = list(book.meta.keys())
        id_item = ids[0]
        self.assertDictEqual(book.meta, {
            id_item: {
                'title': 'MyTitle 中文',
                'type': '',
                'index': f'{id_item}/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
                },
            })
        self.assertDictEqual(book.toc, {
            'root': [
                id_item,
                ],
            })
        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, id_item),
            os.path.join(self.test_output, id_item, 'index.html'),
            os.path.join(self.test_output, id_item, 'mypage.html'),
            os.path.join(self.test_output, id_item, 'mypage.files'),
            os.path.join(self.test_output, id_item, 'mypage.files', 'picture.bmp'),
            })

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

        for info in file2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()
        book.load_toc_files()

        ids = list(book.meta.keys())
        id_item = ids[0]
        self.assertDictEqual(book.meta, {
            id_item: {
                'title': 'MyTitle 中文',
                'type': '',
                'index': f'{id_item}/index.html',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
                'icon': '',
                'comment': '',
                },
            })
        self.assertDictEqual(book.toc, {
            'root': [
                id_item,
                ],
            })
        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, id_item),
            os.path.join(self.test_output, id_item, 'index.html'),
            os.path.join(self.test_output, id_item, 'mypage.html'),
            os.path.join(self.test_output, id_item, 'mypage_files'),
            os.path.join(self.test_output, id_item, 'mypage_files', 'picture.bmp'),
            })

if __name__ == '__main__':
    unittest.main()
