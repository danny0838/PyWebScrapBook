from unittest import mock
import unittest
import os
import shutil
import zipfile
from datetime import datetime, timezone
from base64 import b64decode

from webscrapbook import WSB_DIR
from webscrapbook.scrapbook.host import Host
from webscrapbook.scrapbook.indexer import Indexer, FavIconCacher

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_scrapbook_indexer')

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

class Test(unittest.TestCase):
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

class TestIndexer(Test):
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        """Infer from source URL if title is empty."""
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
<title></title>
</head>
</html>
""")

        book = Host(self.test_root).books['']
        generator = Indexer(book)
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

    def test_item_title04(self):
        """Infer from source URL if title is blank."""
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
<title> </title>
</head>
</html>
""")

        book = Host(self.test_root).books['']
        generator = Indexer(book)
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

    def test_item_title05(self):
        """Keep empty if nothing to infer."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html>
<html
    data-scrapbook-create="20200101000000000"
    data-scrapbook-modify="20200101000000000">
<head>
<meta charset="UTF-8">
</head>
</html>
""")

        book = Host(self.test_root).books['']
        generator = Indexer(book)
        for info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': '',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '',
                'source': '',
                'comment': '',
                },
            })

    def test_item_title06(self):
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
        generator = Indexer(book)
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
        generator = Indexer(book)
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
        generator = Indexer(book, handle_ie_meta=True)
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
        generator = Indexer(book, handle_ie_meta=False)
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
        generator = Indexer(book, handle_singlefile_meta=True)
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
        generator = Indexer(book, handle_singlefile_meta=False)
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
        generator = Indexer(book, handle_savepagewe_meta=True)
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
        generator = Indexer(book, handle_savepagewe_meta=False)
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
        generator = Indexer(book, handle_maoxian_meta=True)
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
        generator = Indexer(book, handle_maoxian_meta=False)
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

    def test_other_file(self):
        """Test for a normal file."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.txt')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8') as fh:
            fh.write('ABC 中文')
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = Host(self.test_root).books['']
        generator = Indexer(book)
        for info in generator.run([test_index]):
            pass

        item_id, = book.meta.keys()
        self.assertDictEqual(book.meta, {
            item_id: {
                'index': '20200101000000000/index.txt',
                'title': '',
                'type': 'file',
                'create': mock.ANY,
                'modify': '20200102030405067',
                'icon': '',
                'source': '',
                'comment': '',
                },
            })

class TestFavIconCacher(Test):
    def test_cache_absolute_url01(self):
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
        generator = FavIconCacher(book)
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

    def test_cache_absolute_url02(self):
        """Cache absolute URL off.
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
        generator = FavIconCacher(book, cache_url=False)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': 'data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA',
                },
            })

    def test_cache_absolute_url03(self):
        """Test Image with MIME = application/octet-stream
        """
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "icon": "data:application/octet-stream;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA"
  }
})""")

        book = Host(self.test_root).books['']
        generator = FavIconCacher(book)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '../.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd',
                },
            })

    def test_cache_absolute_url04(self):
        """Test Image with an invalid MIME should not be cached
        """
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "create": "20200101000000000",
    "modify": "20200101000000000",
    "icon": "data:text/plain;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA"
  }
})""")

        book = Host(self.test_root).books['']
        generator = FavIconCacher(book)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': 'data:text/plain;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA',
                },
            })

    def test_cache_archive01(self):
        """Cache in-ZIP path
        """
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "",
    "index": "20200101000000001.htz",
    "icon": "favicon.bmp"
  },
  "20200101000000002": {
    "type": "",
    "index": "20200101000000002.maff",
    "icon": "favicon.bmp"
  }
})""")

        with zipfile.ZipFile(os.path.join(self.test_root, '20200101000000001.htz'), 'w') as zh:
            zh.writestr('index.html', 'dummy')
            zh.writestr('favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        with zipfile.ZipFile(os.path.join(self.test_root, '20200101000000002.maff'), 'w') as zh:
            zh.writestr('20200101000000000/index.html', 'dummy')
            zh.writestr('20200101000000000/favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        book = Host(self.test_root).books['']
        generator = FavIconCacher(book, cache_archive=True)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001.htz',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002.maff',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                },
            })

    def test_cache_archive02(self):
        """Cache in-ZIP path off
        """
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "",
    "index": "20200101000000001.htz",
    "icon": "favicon.bmp"
  },
  "20200101000000002": {
    "type": "",
    "index": "20200101000000002.maff",
    "icon": "favicon.bmp"
  }
})""")

        with zipfile.ZipFile(os.path.join(self.test_root, '20200101000000001.htz'), 'w') as zh:
            zh.writestr('index.html', 'dummy')
            zh.writestr('favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        with zipfile.ZipFile(os.path.join(self.test_root, '20200101000000002.maff'), 'w') as zh:
            zh.writestr('20200101000000000/index.html', 'dummy')
            zh.writestr('20200101000000000/favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        book = Host(self.test_root).books['']
        generator = FavIconCacher(book, cache_archive=False)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000001': {
                'type': '',
                'index': '20200101000000001.htz',
                'icon': 'favicon.bmp',
                },
            '20200101000000002': {
                'type': '',
                'index': '20200101000000002.maff',
                'icon': 'favicon.bmp',
                },
            })

    def test_cache_file01(self):
        """Cache relative path
        """
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "favicon.bmp"
  }
})""")

        index_dir = os.path.join(self.test_root, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')
        with open(os.path.join(index_dir, 'favicon.bmp'), 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        book = Host(self.test_root).books['']
        generator = FavIconCacher(book, cache_file=True)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': '../.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
                },
            })

    def test_cache_file02(self):
        """Cache relative path off
        """
        with open(os.path.join(self.test_tree, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "",
    "index": "20200101000000000/index.html",
    "icon": "favicon.bmp"
  }
})""")

        index_dir = os.path.join(self.test_root, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')
        with open(os.path.join(index_dir, 'favicon.bmp'), 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        book = Host(self.test_root).books['']
        generator = FavIconCacher(book, cache_file=False)
        for info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.bmp',
                },
            })

if __name__ == '__main__':
    unittest.main()
