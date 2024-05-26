import os
import tempfile
import unittest
from base64 import b64decode
from datetime import datetime, timezone
from unittest import mock

from webscrapbook import WSB_DIR
from webscrapbook._polyfill import zipfile
from webscrapbook.scrapbook.indexer import (
    FavIconCacher,
    Indexer,
    SingleHtmlConverter,
    UnSingleHtmlConverter,
)

from . import TEMP_DIR, TestBookMixin, glob_files


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='indexer-', dir=TEMP_DIR)
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


class Test(TestBookMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_tree = os.path.join(self.test_root, WSB_DIR, 'tree')
        os.makedirs(self.test_tree)


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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
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
            },
        })

    def test_bad_html(self):
        """No item should be indexed if the HTML file is bad."""
        test_index = os.path.join(self.test_root, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(test_index))
        with open(test_index, 'w', encoding='UTF-8'):
            pass
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {})

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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
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
            },
        })

    def test_item_id_used(self):
        """Skip if id is provided but used."""
        book = self.init_book(
            self.test_root,
            meta={
                'myid': {
                    'title': 'dummy',
                    'type': 'folder',
                },
            },
        )
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

        generator = Indexer(book)
        for _info in generator.run([test_index]):
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {})

    def test_item_id_dirname01(self):
        """Test if dirname corresponds to standard ID format."""
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
            },
        })

    def test_item_id_dirname02(self):
        """Test if dirname (deply) corresponds to standard ID format."""
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': 'subdir/20200101000000000/index.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
            },
        })

    def test_item_id_dirname03(self):
        """Generate new ID if dirname corresponds to standard ID format but used."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'title': 'dummy',
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
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

        generator = Indexer(book)
        for _info in generator.run([test_index]):
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
                'source': 'http://example.com',
            },
        })

    def test_item_id_dirname04(self):
        """Generate new ID if dirname not corresponds to standard ID format."""
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
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
                'source': 'http://example.com',
            },
        })

    def test_item_id_filename01(self):
        """Test if filename corresponds to standard ID format."""
        test_index = os.path.join(self.test_root, '20200101000000000.html')
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
            },
        })

    def test_item_id_filename02(self):
        """Generate new ID if filename corresponds to standard ID format but used."""
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'title': 'dummy',
                    'type': 'folder',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
            },
        )
        test_index = os.path.join(self.test_root, '20200101000000000.html')
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

        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        new_id = list(book.meta.keys())[-1]
        self.assertRegex(new_id, r'^\d{17}$')

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'title': 'dummy',
                'type': 'folder',
            },
            new_id: {
                'index': '20200101000000000.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
            },
        })

    def test_item_id_filename03(self):
        """Generate new ID if filename not corresponds to standard ID format."""
        test_index = os.path.join(self.test_root, 'foo.html')
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        new_id = list(book.meta.keys())[-1]
        self.assertRegex(new_id, r'^\d{17}$')

        self.assertDictEqual(book.meta, {
            new_id: {
                'index': 'foo.html',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'my<span>page</span>中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com/mypage.html',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mypage.html',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com/mypage.html',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mypage.html',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com/mypage.html',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mypage.html',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com/mypage.html',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': '',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': '',
                'type': 'separator',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'source': 'http://example.com',
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
            zh.writestr(
                'favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.htz',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
                'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
            },
        })

    def test_item_icon_link_no_rel(self):
        """No error for link:not([rel])."""
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
<link href="favicon.bmp">
</head>
<body>
page content
</body>
</html>
""")
            zh.writestr(
                'favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.htz',
                'title': 'MyTitle 中文',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200101000000000',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book, handle_ie_meta=True)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'source': 'http://example.com/?a=123#456',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book, handle_ie_meta=False)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
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
""")  # noqa: W291
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = self.init_book(self.test_root)
        generator = Indexer(book, handle_singlefile_meta=True)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101020000000',
                'modify': '20200102030405067',
                'source': 'http://example.com/?a=123#456',
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
""")  # noqa: W291
        ts = datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc).timestamp()
        os.utime(test_index, (ts, ts))

        book = self.init_book(self.test_root)
        generator = Indexer(book, handle_singlefile_meta=False)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book, handle_savepagewe_meta=True)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'MY TITLE',
                'type': '',
                'create': '20200101020000000',
                'modify': '20200102030405067',
                'source': 'http://example.com/?a=123#456',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book, handle_savepagewe_meta=False)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book, handle_maoxian_meta=True)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
                'source': 'http://example.com/?a=123#456',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book, handle_maoxian_meta=False)
        for _info in generator.run([test_index]):
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'index': '20200101000000000/index.html',
                'title': 'mytitle',
                'type': '',
                'create': '20200101000000000',
                'modify': '20200102030405067',
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

        book = self.init_book(self.test_root)
        generator = Indexer(book)
        for _info in generator.run([test_index]):
            pass

        item_id, = book.meta.keys()
        self.assertDictEqual(book.meta, {
            item_id: {
                'index': '20200101000000000/index.txt',
                'title': '',
                'type': 'file',
                'create': mock.ANY,
                'modify': '20200102030405067',
            },
        })


class TestFavIconCacher(Test):
    def test_cache_absolute_url01(self):
        """Cache absolute URL.

        Test using data URL. Should also work for a remote URL.
        """
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'icon': 'data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA',
                },
            },
        )

        generator = FavIconCacher(book)
        for _info in generator.run():
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

        with open(os.path.join(self.test_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'), 'rb') as fh:
            self.assertEqual(
                fh.read(),
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

    def test_cache_absolute_url02(self):
        """Cache absolute URL off.
        """
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'icon': 'data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA',
                },
            },
        )

        generator = FavIconCacher(book, cache_url=False)
        for _info in generator.run():
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
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'icon': 'data:application/octet-stream;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA',
                },
            },
        )

        generator = FavIconCacher(book)
        for _info in generator.run():
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

        with open(os.path.join(self.test_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd'), 'rb') as fh:
            self.assertEqual(
                fh.read(),
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

    def test_cache_absolute_url04(self):
        """Test Image with an invalid MIME should not be cached
        """
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'type': '',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                    'icon': 'data:text/plain;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA',
                },
            },
        )

        generator = FavIconCacher(book)
        for _info in generator.run():
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
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000001': {
                    'type': '',
                    'index': '20200101000000001.htz',
                    'icon': 'favicon.bmp',
                },
                '20200101000000002': {
                    'type': '',
                    'index': '20200101000000002.maff',
                    'icon': 'favicon.bmp',
                }
            },
        )

        with zipfile.ZipFile(os.path.join(self.test_root, '20200101000000001.htz'), 'w') as zh:
            zh.writestr('index.html', 'dummy')
            zh.writestr(
                'favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

        with zipfile.ZipFile(os.path.join(self.test_root, '20200101000000002.maff'), 'w') as zh:
            zh.writestr('20200101000000000/index.html', 'dummy')
            zh.writestr(
                '20200101000000000/favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

        generator = FavIconCacher(book, cache_archive=True)
        for _info in generator.run():
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
        book = self.init_book(
            self.test_root,
            meta={
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
            },
        )

        with zipfile.ZipFile(os.path.join(self.test_root, '20200101000000001.htz'), 'w') as zh:
            zh.writestr('index.html', 'dummy')
            zh.writestr(
                'favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

        with zipfile.ZipFile(os.path.join(self.test_root, '20200101000000002.maff'), 'w') as zh:
            zh.writestr('20200101000000000/index.html', 'dummy')
            zh.writestr(
                '20200101000000000/favicon.bmp',
                b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'),
            )

        generator = FavIconCacher(book, cache_archive=False)
        for _info in generator.run():
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
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000/index.html',
                    'icon': 'favicon.bmp',
                },
            },
        )

        index_dir = os.path.join(self.test_root, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')
        with open(os.path.join(index_dir, 'favicon.bmp'), 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        generator = FavIconCacher(book, cache_file=True)
        for _info in generator.run():
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
        book = self.init_book(
            self.test_root,
            meta={
                '20200101000000000': {
                    'type': '',
                    'index': '20200101000000000/index.html',
                    'icon': 'favicon.bmp',
                },
            },
        )

        index_dir = os.path.join(self.test_root, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')
        with open(os.path.join(index_dir, 'favicon.bmp'), 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        generator = FavIconCacher(book, cache_file=False)
        for _info in generator.run():
            pass

        self.assertDictEqual(book.meta, {
            '20200101000000000': {
                'type': '',
                'index': '20200101000000000/index.html',
                'icon': 'favicon.bmp',
            },
        })


class TestSingleHtmlConverter(Test):
    def test_rewrite_basic(self):
        """Test basic resources embedding
        """
        input = """\
<img src="./img1.bmp" srcset="./img2.bmp 2x, ./img3.bmp 3x">
<input type="image" src="./input_image.bmp">
<audio src="./audio.oga"></audio>
<audio controls>
  <source src="./audio_source.oga" type="audio/ogg">
  <source src="./audio_source.mp3" type="audio/mpeg">
  <track kind="captions" label="English captions" src="./audio_track_en.vtt" srclang="en" default></track>
  <track kind="captions" label="中文標題" src="./audio_track_zh.vtt" srclang="zh"></track>
  Your browser does not support HTML5 audio.
</audio>
<video src="./video.mp4" poster="./poster.png"></video>
<video controls>
  <source src="./video_source.webm" type="video/webm">
  <source src="./video_source.mp4" type="video/mp4">
  <track kind="subtitles" label="English subtitles" src="./video_track_en.vtt" srclang="en" default></track>
  <track kind="subtitles" label="中文字幕" src="./video_track_zh.vtt" srclang="zh"></track>
  Your browser does not support HTML5 video.
</video>
<embed src="./embed.swf">
<applet code="./applet.class" archive="./applet.jar">
<a href="a.html"></a>
<area href="area.html"></area>
"""

        expected = """\
<img src="data:image/bmp;base64,aW1nMS5ibXA=" srcset="data:image/bmp;base64,aW1nMi5ibXA= 2x, data:image/bmp;base64,aW1nMy5ibXA= 3x">
<input type="image" src="data:image/bmp;base64,aW5wdXRfaW1hZ2UuYm1w">
<audio src="data:audio/ogg;base64,YXVkaW8ub2dh"></audio>
<audio controls>
  <source src="data:audio/ogg;base64,YXVkaW9fc291cmNlLm9nYQ==" type="audio/ogg">
  <source src="data:audio/mpeg;base64,YXVkaW9fc291cmNlLm1wMw==" type="audio/mpeg">
  <track kind="captions" label="English captions" src="data:text/vtt,audio_track_en.vtt" srclang="en" default></track>
  <track kind="captions" label="中文標題" src="data:text/vtt,audio_track_zh.vtt" srclang="zh"></track>
  Your browser does not support HTML5 audio.
</audio>
<video src="data:video/mp4;base64,dmlkZW8ubXA0" poster="data:image/png;base64,cG9zdGVyLnBuZw=="></video>
<video controls>
  <source src="data:video/webm;base64,dmlkZW9fc291cmNlLndlYm0=" type="video/webm">
  <source src="data:video/mp4;base64,dmlkZW9fc291cmNlLm1wNA==" type="video/mp4">
  <track kind="subtitles" label="English subtitles" src="data:text/vtt,video_track_en.vtt" srclang="en" default></track>
  <track kind="subtitles" label="中文字幕" src="data:text/vtt,video_track_zh.vtt" srclang="zh"></track>
  Your browser does not support HTML5 video.
</video>
<embed src="data:application/x-shockwave-flash;base64,ZW1iZWQuc3dm">
<applet code="data:application/java-vm;base64,YXBwbGV0LmNsYXNz" archive="data:application/java-archive;base64,YXBwbGV0Lmphcg==">
<a href="data:text/html,a.html"></a>
<area href="data:text/html,area.html"></area>
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        resources = [
            'img1.bmp',
            'img2.bmp',
            'img3.bmp',
            'input_image.bmp',
            'audio.oga',
            'audio_source.oga',
            'audio_source.mp3',
            'audio_track_en.vtt',
            'audio_track_zh.vtt',
            'video.mp4',
            'poster.png',
            'video_source.webm',
            'video_source.mp4',
            'video_track_en.vtt',
            'video_track_zh.vtt',
            'embed.swf',
            'applet.class',
            'applet.jar',
            'a.html',
            'area.html',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_css(self):
        """Test recursive rewriting for CSS
        """
        input = """\
<head>
<meta charset="UTF-8">
<link rel="stylesheet" href="link/link.css">
<style>#style { background: url(./style.bmp); }</style>
</head>
<body>
<div style="#div { background: url(./attr_style.bmp); }"></div>
</body>
"""
        expected = """\
<head>
<meta charset="UTF-8">
<link rel="stylesheet" href="data:text/css,%40import%20%22data%3Atext/css%2C%2540import%2520%2522urn%253Ascrapbook%253Aconvert%253Acircular%253Aurl%253A../link/link.css%2522%253B%250A%22%3B%0A%40font-face%20%7B%20font-family%3A%20myFont%3B%20src%3A%20url%28%22data%3Afont/woff%3Bbase64%2CbGluay9mb250LndvZmY%3D%22%29%3B%20%7D%0A%23link%20%7B%20background%3A%20url%28%22data%3Aimage/bmp%3Bbase64%2CbGluay9pbWcuYm1w%22%29%3B%20%7D%0A">
<style>#style { background: url("data:image/bmp;base64,c3R5bGUuYm1w"); }</style>
</head>
<body>
<div style="#div { background: url(&quot;data:image/bmp;base64,YXR0cl9zdHlsZS5ibXA=&quot;); }"></div>
</body>
"""  # noqa: E501

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        os.makedirs(os.path.join(self.test_root, 'link'), exist_ok=True)
        with open(os.path.join(self.test_root, 'link', 'link.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""\
@import "../import/import.css";
@font-face { font-family: myFont; src: url("./font.woff"); }
#link { background: url("./img.bmp"); }
""")

        os.makedirs(os.path.join(self.test_root, 'import'), exist_ok=True)
        with open(os.path.join(self.test_root, 'import', 'import.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""\
@import "../link/link.css";
""")

        resources = [
            'link/font.woff',
            'link/img.bmp',
            'style.bmp',
            'attr_style.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_css_link(self):
        """Check CSS rewriting for <link>.
        """
        input = """\
<link rel="stylesheet" href="css_link.css">
"""
        expected = """\
<link rel="stylesheet" href="data:text/css,%3Cstyle%3E%40import%20%22data%3Atext/css%2C%2540import%2520url%2528%2522data%253Atext/css%252C.bg-link-import-import%252520%25257B%252520background-image%25253A%252520url%252528%252522data%25253Aimage/bmp%25253Bbase64%25252CQk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAA/wAAAAAA%252522%252529%25253B%252520%25257D%25250A%2522%2529%253B%250A%2540font-face%2520%257B%2520font-family%253A%2520font-link-import%253B%2520src%253A%2520url%2528%2522data%253Afont/woff%253Bbase64%252CQk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA%2522%2529%253B%2520%257D%250A.bg-link-import%2520%257B%2520background-image%253A%2520url%2528%2522data%253Aimage/bmp%253Bbase64%252CQk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA%2522%2529%253B%2520%257D%250A%22%3B%3C/style%3E%0A%3Cstyle%3E%40font-face%20%7B%20font-family%3A%20font-link%3B%20src%3A%20url%28%22data%3Afont/woff%3Bbase64%2CQk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA%22%29%3B%20%7D%3C/style%3E%0A%3Cstyle%3E.bg-link%20%7B%20background-image%3A%20url%28%22data%3Aimage/bmp%3Bbase64%2CQk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA%22%29%3B%20%7D%3C/style%3E%0A">
"""  # noqa: E501

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        with open(os.path.join(self.test_root, 'css_link.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""\
<style>@import "css_link_import.css";</style>
<style>@font-face { font-family: font-link; src: url(./font_link.woff); }</style>
<style>.bg-link { background-image: url(./img_link.bmp); }</style>
""")

        with open(os.path.join(self.test_root, 'css_link_import.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""\
@import url(./css_link_import_import.css);
@font-face { font-family: font-link-import; src: url(./font_link_import.woff); }
.bg-link-import { background-image: url(./img_link_import.bmp); }
""")

        with open(os.path.join(self.test_root, 'css_link_import_import.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(""".bg-link-import-import { background-image: url(./img_link_import_import.bmp); }
""")

        with open(os.path.join(self.test_root, 'font_link.woff'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA'))
        with open(os.path.join(self.test_root, 'font_link_import.woff'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        with open(os.path.join(self.test_root, 'img_link.bmp'), 'wb') as fh:
            # red
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA'))
        with open(os.path.join(self.test_root, 'img_link_import.bmp'), 'wb') as fh:
            # green
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))
        with open(os.path.join(self.test_root, 'img_link_import_import.bmp'), 'wb') as fh:
            # blue
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAA/wAAAAAA'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_css_style(self):
        """Check CSS rewriting for <style>.
        """
        input = """\
<style>@import "css_style_import.css";</style>
<style>@font-face { font-family: font-style; src: url(./font_style.woff); }</style>
<style>.bg-style { background-image: url(./img_style.bmp); }</style>
"""
        expected = """\
<style>@import "data:text/css,%40import%20url%28%22data%3Atext/css%2C.bg-style-import-import%2520%257B%2520background-image%253A%2520url%2528%2522data%253Aimage/bmp%253Bbase64%252CQk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAA/wAAAAAA%2522%2529%253B%2520%257D%250A%22%29%3B%0A%40font-face%20%7B%20font-family%3A%20font-style-import%3B%20src%3A%20url%28%22data%3Afont/woff%3Bbase64%2CQk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA%22%29%3B%20%7D%0A.bg-style-import%20%7B%20background-image%3A%20url%28%22data%3Aimage/bmp%3Bbase64%2CQk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA%22%29%3B%20%7D%0A";</style>
<style>@font-face { font-family: font-style; src: url("data:font/woff;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA"); }</style>
<style>.bg-style { background-image: url("data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA"); }</style>
"""  # noqa: E501

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        with open(os.path.join(self.test_root, 'css_style_import.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""\
@import url(./css_style_import_import.css);
@font-face { font-family: font-style-import; src: url(./font_style_import.woff); }
.bg-style-import { background-image: url(./img_style_import.bmp); }
""")

        with open(os.path.join(self.test_root, 'css_style_import_import.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(""".bg-style-import-import { background-image: url(./img_style_import_import.bmp); }
""")

        with open(os.path.join(self.test_root, 'font_style.woff'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA'))
        with open(os.path.join(self.test_root, 'font_style_import.woff'), 'wb') as fh:
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        with open(os.path.join(self.test_root, 'img_style.bmp'), 'wb') as fh:
            # red
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA'))
        with open(os.path.join(self.test_root, 'img_style_import.bmp'), 'wb') as fh:
            # green
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))
        with open(os.path.join(self.test_root, 'img_style_import_import.bmp'), 'wb') as fh:
            # blue
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAA/wAAAAAA'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_css_inline(self):
        """Check CSS rewriting for inline.
        """
        input = """<div style="background-image: url(./img_internal.bmp);"></div>"""
        expected = """<div style="background-image: url(&quot;data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA&quot;);"></div>"""  # noqa: E501

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        with open(os.path.join(self.test_root, 'img_internal.bmp'), 'wb') as fh:
            # red
            fh.write(b64decode(b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAAD/AAAA'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_css_circular(self):
        """Check CSS rewriting with circular reference.
        """
        input = """<style>@import "import1.css";</style>"""
        expected = """<style>@import "data:text/css,%40import%20%22data%3Atext/css%2C%2540import%2520%2522data%253Atext/css%252C%252540import%252520%252522urn%25253Ascrapbook%25253Aconvert%25253Acircular%25253Aurl%25253Aimport1.css%252522%25253B%2522%253B%22%3B";</style>"""  # noqa: E501

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        with open(os.path.join(self.test_root, 'import1.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""@import "import2.css";""")

        with open(os.path.join(self.test_root, 'import2.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""@import "import3.css";""")

        with open(os.path.join(self.test_root, 'import3.css'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""@import "import1.css";""")

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_frame(self):
        """Test recursive rewriting for frame
        """
        input = """<frame src="frame/frame.html">"""
        expected = """<frame src="data:text/html,%3Cimg%20src%3D%22data%3Aimage/bmp%3Bbase64%2CZnJhbWUvaW1nLmJtcA%3D%3D%22%3E%0A%3Cframe%20src%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%0A%3Ciframe%20src%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%3C/iframe%3E%0A%3Cobject%20data%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%3C/object%3E%0A">"""  # noqa: E501

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        os.makedirs(os.path.join(self.test_root, 'frame'), exist_ok=True)
        with open(os.path.join(self.test_root, 'frame', 'frame.html'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""\
<img src="./img.bmp">
<frame src="../index.html">
<iframe src="../index.html"></iframe>
<object data="../index.html"></object>
""")

        resources = [
            'frame/img.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_iframe_src(self):
        """Test recursive rewriting for iframe (src)
        """
        input = """<iframe src="iframe/iframe.html"></iframe>"""
        expected = """<iframe srcdoc="&lt;img src=&quot;data:image/bmp;base64,aWZyYW1lL2ltZy5ibXA=&quot;&gt;
&lt;frame src=&quot;urn:scrapbook:convert:circular:url:../index.html&quot;&gt;
&lt;iframe src=&quot;urn:scrapbook:convert:circular:url:../index.html&quot;&gt;&lt;/iframe&gt;
&lt;object data=&quot;urn:scrapbook:convert:circular:url:../index.html&quot;&gt;&lt;/object&gt;
"></iframe>"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        os.makedirs(os.path.join(self.test_root, 'iframe'), exist_ok=True)
        with open(os.path.join(self.test_root, 'iframe', 'iframe.html'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""\
<img src="./img.bmp">
<frame src="../index.html">
<iframe src="../index.html"></iframe>
<object data="../index.html"></object>
""")

        resources = [
            'iframe/img.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_iframe_srcdoc(self):
        """Test recursive rewriting for iframe (srcdoc)
        """
        input = """<iframe srcdoc="
<img src=iframe/img.bmp>
<img src=nonexist.bmp>
<iframe src=../index.html></iframe>
<iframe src=nonexist.html></iframe>
" src="iframe/src.html"></iframe>"""
        expected = """<iframe srcdoc="
&lt;img src=&quot;data:image/bmp;base64,aWZyYW1lL2ltZy5ibXA=&quot;&gt;
&lt;img src=&quot;urn:scrapbook:converter:error:url:nonexist.bmp&quot;&gt;
&lt;iframe src=&quot;urn:scrapbook:convert:error:url:../index.html&quot;&gt;&lt;/iframe&gt;
&lt;iframe src=&quot;urn:scrapbook:convert:error:url:nonexist.html&quot;&gt;&lt;/iframe&gt;
"></iframe>"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        os.makedirs(os.path.join(self.test_root, 'iframe'), exist_ok=True)

        resources = [
            'iframe/src.html',
            'iframe/img.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_object(self):
        """Test recursive rewriting for object
        """
        input = """<object data="object/object.html"></object>"""
        expected = """<object data="data:text/html,%3Cimg%20src%3D%22data%3Aimage/bmp%3Bbase64%2Cb2JqZWN0L2ltZy5ibXA%3D%22%3E%0A%3Cframe%20src%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%0A%3Ciframe%20src%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%3C/iframe%3E%0A%3Cobject%20data%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%3C/object%3E%0A"></object>"""  # noqa: E501

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        os.makedirs(os.path.join(self.test_root, 'object'), exist_ok=True)
        with open(os.path.join(self.test_root, 'object', 'object.html'), 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write("""\
<img src="./img.bmp">
<frame src="../index.html">
<iframe src="../index.html"></iframe>
<object data="../index.html"></object>
""")

        resources = [
            'object/img.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_shadowdom(self):
        """Test recursive rewriting for shadow DOM attribute
        """
        input = """\
<div data-scrapbook-shadowdom="
<div data-scrapbook-shadowdom=&quot;
<div>div3</div>
<img src=&amp;quot;div3.bmp&amp;quot;>
&quot;>div2</div>
<img src=&quot;div2.bmp&quot;>
">div1</div>"""
        expected = """\
<div data-scrapbook-shadowdom="
&lt;div data-scrapbook-shadowdom=&quot;
&amp;lt;div&amp;gt;div3&amp;lt;/div&amp;gt;
&amp;lt;img src=&amp;quot;data:image/bmp;base64,ZGl2My5ibXA=&amp;quot;&amp;gt;
&quot;&gt;div2&lt;/div&gt;
&lt;img src=&quot;data:image/bmp;base64,ZGl2Mi5ibXA=&quot;&gt;
">div1</div>"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        resources = [
            'div2.bmp',
            'div3.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_meta(self):
        """Test handling of meta refresh
        """
        input = """\
<meta http-equiv="refresh" content="0; url=./meta.html">
<meta http-equiv="refresh" content="0; url=http://example.com">
"""
        expected = """\
<meta http-equiv="refresh" content="0; url=urn:scrapbook:convert:skip:url:./meta.html">
<meta http-equiv="refresh" content="0; url=http://example.com">
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        resources = [
            'div2.bmp',
            'div3.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_base01(self):
        """Test handling of base URL
        """
        input = """\
<head>
<base href="./resources/">
</head>
<body>
<img src="img.bmp">
</body>
"""
        expected = """\
<head>
<base href="./resources/">
</head>
<body>
<img src="data:image/bmp;base64,cmVzb3VyY2VzL2ltZy5ibXA=">
</body>
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        os.makedirs(os.path.join(self.test_root, 'resources'), exist_ok=True)

        resources = [
            'resources/img.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_base02(self):
        """Test handling of base URL (absolute)
        """
        input = """\
<head>
<base href="http://example.com">
</head>
<body>
<img src="img.bmp">
</body>
"""
        expected = """\
<head>
<base href="http://example.com">
</head>
<body>
<img src="img.bmp">
</body>
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_svg(self):
        """Test handling of embedded SVG
        """
        input = """\
<!DOCTYPE html>
<body>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <script href="./script.js"></script>
  <script xlink:href="./scriptx.js"></script>
  <a href="./a.bmp">
    <image href="./image.bmp"/>
  </a>
  <a xlink:href="./ax.bmp">
    <image xlink:href="./imagex.bmp"/>
  </a>
</svg>
</body>
"""
        expected = """\
<!DOCTYPE html>
<body>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <script href="data:text/javascript,script.js"></script>
  <script xlink:href="data:text/javascript,scriptx.js"></script>
  <a href="data:image/bmp;base64,YS5ibXA=">
    <image href="data:image/bmp;base64,aW1hZ2UuYm1w" />
  </a>
  <a xlink:href="data:image/bmp;base64,YXguYm1w">
    <image xlink:href="data:image/bmp;base64,aW1hZ2V4LmJtcA==" />
  </a>
</svg>
</body>
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        resources = [
            'script.js',
            'scriptx.js',
            'a.bmp',
            'ax.bmp',
            'image.bmp',
            'imagex.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

    def test_rewrite_svg_file(self):
        """Test handling of SVG file
        """
        input = """\
<?xml version="1.0"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <script href="./script.js"></script>
  <script xlink:href="./scriptx.js"></script>
  <a href="./a.bmp">
    <image href="./image.bmp"/>
  </a>
  <a xlink:href="./ax.bmp">
    <image xlink:href="./imagex.bmp"/>
  </a>
</svg>
"""
        expected = """\
<?xml version="1.0"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <script href="data:text/javascript,script.js"></script>
  <script xlink:href="data:text/javascript,scriptx.js"></script>
  <a href="data:image/bmp;base64,YS5ibXA=">
    <image href="data:image/bmp;base64,aW1hZ2UuYm1w" />
  </a>
  <a xlink:href="data:image/bmp;base64,YXguYm1w">
    <image xlink:href="data:image/bmp;base64,aW1hZ2V4LmJtcA==" />
  </a>
</svg>
"""

        test_index = os.path.join(self.test_root, 'index.svg')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        resources = [
            'script.js',
            'scriptx.js',
            'a.bmp',
            'ax.bmp',
            'image.bmp',
            'imagex.bmp',
        ]
        for resource in resources:
            with open(os.path.normpath(os.path.join(self.test_root, resource)), 'wb') as fh:
                fh.write(resource.encode('UTF-8'))

        conv = SingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)


class TestUnSingleHtmlConverter(Test):
    def test_rewrite_basic(self):
        """Test basic resources rewriting
        """
        input = """\
<img src="data:image/bmp;base64,aW1nMS5ibXA=" srcset="data:image/bmp;base64,aW1nMi5ibXA= 2x, data:image/bmp;base64,aW1nMy5ibXA= 3x">
<input type="image" src="data:image/bmp;base64,aW5wdXRfaW1hZ2UuYm1w">
<audio src="data:audio/ogg;base64,YXVkaW8ub2dh"></audio>
<audio controls>
  <source src="data:audio/ogg;base64,YXVkaW9fc291cmNlLm9nYQ==" type="audio/ogg">
  <source src="data:audio/mpeg;base64,YXVkaW9fc291cmNlLm1wMw==" type="audio/mpeg">
  <track kind="captions" label="English captions" src="data:text/vtt,audio_track_en.vtt" srclang="en" default></track>
  <track kind="captions" label="中文標題" src="data:text/vtt,audio_track_zh.vtt" srclang="zh"></track>
  Your browser does not support HTML5 audio.
</audio>
<video src="data:video/mp4;base64,dmlkZW8ubXA0" poster="data:image/png;base64,cG9zdGVyLnBuZw=="></video>
<video controls>
  <source src="data:video/webm;base64,dmlkZW9fc291cmNlLndlYm0=" type="video/webm">
  <source src="data:video/mp4;base64,dmlkZW9fc291cmNlLm1wNA==" type="video/mp4">
  <track kind="subtitles" label="English subtitles" src="data:text/vtt,video_track_en.vtt" srclang="en" default></track>
  <track kind="subtitles" label="中文字幕" src="data:text/vtt,video_track_zh.vtt" srclang="zh"></track>
  Your browser does not support HTML5 video.
</video>
<embed src="data:application/x-shockwave-flash;base64,ZW1iZWQuc3dm">
<applet code="data:application/java-vm;base64,YXBwbGV0LmNsYXNz" archive="data:application/java-archive;base64,YXBwbGV0Lmphcg==">
<a href="data:text/html,a.html"></a>
<area href="data:text/html,area.html"></area>
"""
        expected = """\
<img src="8d02fbc24fb22ff07cb5aace1337e45688a66f8f.bmp" srcset="b35de104c054d48359faf058507011a6cf356533.bmp 2x, 6e13e94ab612ecf6a9f7eda5fa68329d0f6051e3.bmp 3x">
<input type="image" src="1153878a46574b0073d7d51ec17647732f38d8b3.bmp">
<audio src="6bf085eb1ffeca507fc9a25379269435bc4b8574.oga"></audio>
<audio controls>
  <source src="02f9d3d32e9303c9f429db3586bf479f407ac1af.oga" type="audio/ogg">
  <source src="3ecac4e5a137f9fc2d67bdb819f30bcb2fc5f943.mp3" type="audio/mpeg">
  <track kind="captions" label="English captions" src="069feea47c7eb48d0e8c315468d6b685ad3a212a.vtt" srclang="en" default></track>
  <track kind="captions" label="中文標題" src="000ff57d214e6a4efcdd29dd3888bc2fffd0c67b.vtt" srclang="zh"></track>
  Your browser does not support HTML5 audio.
</audio>
<video src="dfa3308d9864c1ba6f4c011c907087a25f81ae6c.mp4" poster="abbfd5130cb3233114f3a3cfd59f1b5c3fe9e5cd.png"></video>
<video controls>
  <source src="380d94891cbfdccc64a1520382013659d084218d.webm" type="video/webm">
  <source src="74398c4f931543e3eaa71c3c52ae5184acab7371.mp4" type="video/mp4">
  <track kind="subtitles" label="English subtitles" src="88d7d81553295729275133e849b7bb9c88f720e2.vtt" srclang="en" default></track>
  <track kind="subtitles" label="中文字幕" src="6105fd67f3bf7df4a8f464fe16ad1faba4f6f27f.vtt" srclang="zh"></track>
  Your browser does not support HTML5 video.
</video>
<embed src="524e068f955500fe81e11c06f364fc81ab084e43.swf">
<applet code="04ce553b2fa0778130a19c8b942eecb184e6d758.class" archive="31a55a9fa0d9b16b5910f1e223fb027c19f00abb.jar">
<a href="25e7e8960b03ecb19189f36b8ef611389397c95c.html"></a>
<area href="b9fcd0fe2499bdd4b8a4d193e1f09ec4b3676db3.html"></area>
"""  # noqa: E501

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, '8d02fbc24fb22ff07cb5aace1337e45688a66f8f.bmp'),
            os.path.join(self.test_root, 'b35de104c054d48359faf058507011a6cf356533.bmp'),
            os.path.join(self.test_root, '6e13e94ab612ecf6a9f7eda5fa68329d0f6051e3.bmp'),
            os.path.join(self.test_root, '1153878a46574b0073d7d51ec17647732f38d8b3.bmp'),
            os.path.join(self.test_root, '6bf085eb1ffeca507fc9a25379269435bc4b8574.oga'),
            os.path.join(self.test_root, '02f9d3d32e9303c9f429db3586bf479f407ac1af.oga'),
            os.path.join(self.test_root, '3ecac4e5a137f9fc2d67bdb819f30bcb2fc5f943.mp3'),
            os.path.join(self.test_root, '069feea47c7eb48d0e8c315468d6b685ad3a212a.vtt'),
            os.path.join(self.test_root, '000ff57d214e6a4efcdd29dd3888bc2fffd0c67b.vtt'),
            os.path.join(self.test_root, 'dfa3308d9864c1ba6f4c011c907087a25f81ae6c.mp4'),
            os.path.join(self.test_root, 'abbfd5130cb3233114f3a3cfd59f1b5c3fe9e5cd.png'),
            os.path.join(self.test_root, '380d94891cbfdccc64a1520382013659d084218d.webm'),
            os.path.join(self.test_root, '74398c4f931543e3eaa71c3c52ae5184acab7371.mp4'),
            os.path.join(self.test_root, '88d7d81553295729275133e849b7bb9c88f720e2.vtt'),
            os.path.join(self.test_root, '6105fd67f3bf7df4a8f464fe16ad1faba4f6f27f.vtt'),
            os.path.join(self.test_root, '524e068f955500fe81e11c06f364fc81ab084e43.swf'),
            os.path.join(self.test_root, '04ce553b2fa0778130a19c8b942eecb184e6d758.class'),
            os.path.join(self.test_root, '31a55a9fa0d9b16b5910f1e223fb027c19f00abb.jar'),
            os.path.join(self.test_root, '25e7e8960b03ecb19189f36b8ef611389397c95c.html'),
            os.path.join(self.test_root, 'b9fcd0fe2499bdd4b8a4d193e1f09ec4b3676db3.html'),
        })

    def test_rewrite_css(self):
        """Test recursive rewriting for CSS
        """
        input = """\
<head>
<meta charset="UTF-8">
<link rel="stylesheet" href="data:text/css,%40import%20%22data%3Atext/css%2C%2540import%2520%2522urn%253Ascrapbook%253Aconvert%253Acircular%253Aurl%253A../link/link.css%2522%253B%250A%22%3B%0A%40font-face%20%7B%20font-family%3A%20myFont%3B%20src%3A%20url%28%22data%3Afont/woff%3Bbase64%2CbGluay9mb250LndvZmY%3D%22%29%3B%20%7D%0A%23link%20%7B%20background%3A%20url%28%22data%3Aimage/bmp%3Bbase64%2CbGluay9pbWcuYm1w%22%29%3B%20%7D%0A">
<style>#style { background: url("data:image/bmp;base64,c3R5bGUuYm1w"); }</style>
</head>
<body>
<div style="#div { background: url(&quot;data:image/bmp;base64,YXR0cl9zdHlsZS5ibXA=&quot;); }"></div>
</body>
"""  # noqa: E501
        expected = """\
<head>
<meta charset="UTF-8">
<link rel="stylesheet" href="b7830ea17e3dbf1162c30f2f6339cf4f2c8a6f35.css">
<style>#style { background: url("aaf5db17e4f43f40d52f22b4deae8e7d8c17c381.bmp"); }</style>
</head>
<body>
<div style="#div { background: url(&quot;3f701cd5ed48448cc6a2eefd001ce8cea17d5031.bmp&quot;); }"></div>
</body>
"""
        expected_css1 = """\
@import "f35361f3ed8c3110eb15e3864ca3ff15ad000874.css";
@font-face { font-family: myFont; src: url("c120be27e3204138e1cd4586d24b28cf39b1fc9b.woff"); }
#link { background: url("bd0e8f24d36976c181bd17d1c9f6da74bb4e368f.bmp"); }
"""
        expected_css2 = """\
@import "urn:scrapbook:convert:circular:url:../link/link.css";
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)
        with open(os.path.join(self.test_root, 'b7830ea17e3dbf1162c30f2f6339cf4f2c8a6f35.css'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), expected_css1)
        with open(os.path.join(self.test_root, 'f35361f3ed8c3110eb15e3864ca3ff15ad000874.css'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), expected_css2)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, 'b7830ea17e3dbf1162c30f2f6339cf4f2c8a6f35.css'),
            os.path.join(self.test_root, 'aaf5db17e4f43f40d52f22b4deae8e7d8c17c381.bmp'),
            os.path.join(self.test_root, 'f35361f3ed8c3110eb15e3864ca3ff15ad000874.css'),
            os.path.join(self.test_root, 'c120be27e3204138e1cd4586d24b28cf39b1fc9b.woff'),
            os.path.join(self.test_root, 'bd0e8f24d36976c181bd17d1c9f6da74bb4e368f.bmp'),
            os.path.join(self.test_root, '3f701cd5ed48448cc6a2eefd001ce8cea17d5031.bmp'),
        })

    def test_rewrite_frame(self):
        """Test recursive rewriting for frame
        """
        input = """<frame src="data:text/html,%3Cimg%20src%3D%22data%3Aimage/bmp%3Bbase64%2CZnJhbWUvaW1nLmJtcA%3D%3D%22%3E%0A%3Cframe%20src%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%0A%3Ciframe%20src%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%3C/iframe%3E%0A%3Cobject%20data%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%3C/object%3E%0A">"""  # noqa: E501
        expected = """<frame src="46f5e95733b31bc905de15e6bd80c903e6b2096f.html">"""
        expected_html1 = """\
<img src="3e751297f65228db45665d2589b00482a7c5a8b9.bmp">
<frame src="urn:scrapbook:convert:circular:url:../index.html">
<iframe src="urn:scrapbook:convert:circular:url:../index.html"></iframe>
<object data="urn:scrapbook:convert:circular:url:../index.html"></object>
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)
        with open(os.path.join(self.test_root, '46f5e95733b31bc905de15e6bd80c903e6b2096f.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), expected_html1)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, '46f5e95733b31bc905de15e6bd80c903e6b2096f.html'),
            os.path.join(self.test_root, '3e751297f65228db45665d2589b00482a7c5a8b9.bmp'),
        })

    def test_rewrite_iframe_src(self):
        """Test recursive rewriting for iframe (src)
        """
        input = """<iframe src="data:text/html,%3Cimg%20src%3D%22data%3Aimage/bmp%3Bbase64%2CZnJhbWUvaW1nLmJtcA%3D%3D%22%3E"></iframe>"""
        expected = """<iframe src="7db93a89332a48e75c089d989ae159643507e322.html"></iframe>"""
        expected_html1 = """<img src="3e751297f65228db45665d2589b00482a7c5a8b9.bmp">"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)
        with open(os.path.join(self.test_root, '7db93a89332a48e75c089d989ae159643507e322.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), expected_html1)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, '7db93a89332a48e75c089d989ae159643507e322.html'),
            os.path.join(self.test_root, '3e751297f65228db45665d2589b00482a7c5a8b9.bmp'),
        })

    def test_rewrite_iframe_srcdoc(self):
        """Test recursive rewriting for iframe (srcdoc)
        """
        input = """<iframe srcdoc="
&lt;img src=&quot;data:image/bmp;base64,aWZyYW1lL2ltZy5ibXA=&quot;&gt;
&lt;img src=&quot;urn:scrapbook:converter:error:url:nonexist.bmp&quot;&gt;
&lt;iframe src=&quot;urn:scrapbook:convert:error:url:../index.html&quot;&gt;&lt;/iframe&gt;
&lt;iframe src=&quot;urn:scrapbook:convert:error:url:nonexist.html&quot;&gt;&lt;/iframe&gt;
" src="data:text/html,%3Cimg%20src%3D%22data%3Aimage/bmp%3Bbase64%2CZnJhbWUvaW1nLmJtcA%3D%3D%22%3E"></iframe>"""
        expected = """<iframe src="924243d4c3b4637e7e2e5c06c23821f57b3b8d18.html"></iframe>"""
        expected_html1 = """
<img src="d9d80b91e142919d0d38021d1d6d1fe99e312937.bmp">
<img src="urn:scrapbook:converter:error:url:nonexist.bmp">
<iframe src="urn:scrapbook:convert:error:url:../index.html"></iframe>
<iframe src="urn:scrapbook:convert:error:url:nonexist.html"></iframe>
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)
        with open(os.path.join(self.test_root, '924243d4c3b4637e7e2e5c06c23821f57b3b8d18.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), expected_html1)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, '924243d4c3b4637e7e2e5c06c23821f57b3b8d18.html'),
            os.path.join(self.test_root, 'd9d80b91e142919d0d38021d1d6d1fe99e312937.bmp'),
        })

    def test_rewrite_object(self):
        """Test recursive rewriting for object
        """
        input = """<object data="data:text/html,%3Cimg%20src%3D%22data%3Aimage/bmp%3Bbase64%2Cb2JqZWN0L2ltZy5ibXA%3D%22%3E%0A%3Cframe%20src%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%0A%3Ciframe%20src%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%3C/iframe%3E%0A%3Cobject%20data%3D%22urn%3Ascrapbook%3Aconvert%3Acircular%3Aurl%3A../index.html%22%3E%3C/object%3E%0A"></object>"""  # noqa: E501
        expected = """<object data="5ef62168ce3226f71e06187764b98e93827b7a1b.html"></object>"""
        expected_html1 = """\
<img src="95d08126f2ba74a8ad580df901dbe6960b4d0e37.bmp">
<frame src="urn:scrapbook:convert:circular:url:../index.html">
<iframe src="urn:scrapbook:convert:circular:url:../index.html"></iframe>
<object data="urn:scrapbook:convert:circular:url:../index.html"></object>
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)
        with open(os.path.join(self.test_root, '5ef62168ce3226f71e06187764b98e93827b7a1b.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), expected_html1)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, '5ef62168ce3226f71e06187764b98e93827b7a1b.html'),
            os.path.join(self.test_root, '95d08126f2ba74a8ad580df901dbe6960b4d0e37.bmp'),
        })

    def test_rewrite_shadowdom(self):
        """Test recursive rewriting for shadow DOM attribute
        """
        input = """\
<div data-scrapbook-shadowdom="
&lt;div data-scrapbook-shadowdom=&quot;
&amp;lt;div&amp;gt;div3&amp;lt;/div&amp;gt;
&amp;lt;img src=&amp;quot;data:image/bmp;base64,ZGl2My5ibXA=&amp;quot;&amp;gt;
&quot;&gt;div2&lt;/div&gt;
&lt;img src=&quot;data:image/bmp;base64,ZGl2Mi5ibXA=&quot;&gt;
">div1</div>"""
        expected = """\
<div data-scrapbook-shadowdom="
&lt;div data-scrapbook-shadowdom=&quot;
&amp;lt;div&amp;gt;div3&amp;lt;/div&amp;gt;
&amp;lt;img src=&amp;quot;e41c1a658ec99284dce1fa1231c473860e8534a4.bmp&amp;quot;&amp;gt;
&quot;&gt;div2&lt;/div&gt;
&lt;img src=&quot;a498468482a6c5bed10bfa03020e42fe4f9bd2f3.bmp&quot;&gt;
">div1</div>"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, 'e41c1a658ec99284dce1fa1231c473860e8534a4.bmp'),
            os.path.join(self.test_root, 'a498468482a6c5bed10bfa03020e42fe4f9bd2f3.bmp'),
        })

    def test_rewrite_meta(self):
        """Test handling of meta refresh
        """
        input = """\
<meta http-equiv="refresh" content="0; url=data:text/html;charset=utf-8,page%20%E4%B8%AD%E6%96%87">
<meta http-equiv="refresh" content="0; url=http://example.com">
"""
        expected = """\
<meta http-equiv="refresh" content="0; url=fdd362b3a207d77938171f188e32aeb39d04aa26.html">
<meta http-equiv="refresh" content="0; url=http://example.com">
"""
        expected_html1 = """page 中文"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)
        with open(os.path.join(self.test_root, 'fdd362b3a207d77938171f188e32aeb39d04aa26.html'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), expected_html1)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, 'fdd362b3a207d77938171f188e32aeb39d04aa26.html'),
        })

    def test_rewrite_svg(self):
        """Test handling of embedded SVG
        """
        input = """\
<!DOCTYPE html>
<body>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <script href="data:text/javascript,script.js"></script>
  <script xlink:href="data:text/javascript,scriptx.js"></script>
  <a href="data:image/bmp;base64,YS5ibXA=">
    <image href="data:image/bmp;base64,aW1hZ2UuYm1w" />
  </a>
  <a xlink:href="data:image/bmp;base64,YXguYm1w">
    <image xlink:href="data:image/bmp;base64,aW1hZ2V4LmJtcA==" />
  </a>
</svg>
</body>
"""
        expected = """\
<!DOCTYPE html>
<body>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <script href="313d6864fa48b411d082f7692efd0c0892788fc4.js"></script>
  <script xlink:href="e80aab679ecb628f86e4f35e3d40328e201f0461.js"></script>
  <a href="dded18f017da72c34a4a1dc94624acfa2ac96c6d.bmp">
    <image href="1104016c2d6f8ec4990888943e4cba557cc13216.bmp" />
  </a>
  <a xlink:href="4202d0fdd043f27d5c2e190ac3101fe78d376164.bmp">
    <image xlink:href="c3eb10541390f68d3da1700b70f0c7a795e2b265.bmp" />
  </a>
</svg>
</body>
"""

        test_index = os.path.join(self.test_root, 'index.html')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.html'),
            os.path.join(self.test_root, '313d6864fa48b411d082f7692efd0c0892788fc4.js'),
            os.path.join(self.test_root, 'e80aab679ecb628f86e4f35e3d40328e201f0461.js'),
            os.path.join(self.test_root, 'dded18f017da72c34a4a1dc94624acfa2ac96c6d.bmp'),
            os.path.join(self.test_root, '1104016c2d6f8ec4990888943e4cba557cc13216.bmp'),
            os.path.join(self.test_root, '4202d0fdd043f27d5c2e190ac3101fe78d376164.bmp'),
            os.path.join(self.test_root, 'c3eb10541390f68d3da1700b70f0c7a795e2b265.bmp'),
        })

    def test_rewrite_svg_file(self):
        """Test handling of SVG file
        """
        input = """\
<?xml version="1.0"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <script href="data:text/javascript,script.js"></script>
  <script xlink:href="data:text/javascript,scriptx.js"></script>
  <a href="data:image/bmp;base64,YS5ibXA=">
    <image href="data:image/bmp;base64,aW1hZ2UuYm1w" />
  </a>
  <a xlink:href="data:image/bmp;base64,YXguYm1w">
    <image xlink:href="data:image/bmp;base64,aW1hZ2V4LmJtcA==" />
  </a>
</svg>
"""
        expected = """\
<?xml version="1.0"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <script href="313d6864fa48b411d082f7692efd0c0892788fc4.js"></script>
  <script xlink:href="e80aab679ecb628f86e4f35e3d40328e201f0461.js"></script>
  <a href="dded18f017da72c34a4a1dc94624acfa2ac96c6d.bmp">
    <image href="1104016c2d6f8ec4990888943e4cba557cc13216.bmp" />
  </a>
  <a xlink:href="4202d0fdd043f27d5c2e190ac3101fe78d376164.bmp">
    <image xlink:href="c3eb10541390f68d3da1700b70f0c7a795e2b265.bmp" />
  </a>
</svg>
"""

        test_index = os.path.join(self.test_root, 'index.svg')
        with open(test_index, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(input)

        conv = UnSingleHtmlConverter(test_index)
        rewritten = conv.run()
        self.assertEqual(rewritten, expected)

        self.assertEqual(glob_files(self.test_root), {
            os.path.join(self.test_root, 'index.svg'),
            os.path.join(self.test_root, '313d6864fa48b411d082f7692efd0c0892788fc4.js'),
            os.path.join(self.test_root, 'e80aab679ecb628f86e4f35e3d40328e201f0461.js'),
            os.path.join(self.test_root, 'dded18f017da72c34a4a1dc94624acfa2ac96c6d.bmp'),
            os.path.join(self.test_root, '1104016c2d6f8ec4990888943e4cba557cc13216.bmp'),
            os.path.join(self.test_root, '4202d0fdd043f27d5c2e190ac3101fe78d376164.bmp'),
            os.path.join(self.test_root, 'c3eb10541390f68d3da1700b70f0c7a795e2b265.bmp'),
        })


if __name__ == '__main__':
    unittest.main()
