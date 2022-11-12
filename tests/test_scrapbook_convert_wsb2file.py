import glob
import os
import tempfile
import unittest
from unittest import mock

from webscrapbook import WSB_DIR
from webscrapbook.scrapbook.convert import wsb2file

from . import TEMP_DIR


def setUpModule():
    """Set up a temp directory for testing."""
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='wsb2file-', dir=TEMP_DIR)
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

        os.makedirs(self.test_input_tree, exist_ok=True)
        os.makedirs(self.test_output, exist_ok=True)

    def test_basic01(self):
        """Check for typical WebScrapBook items. (prefix=True)"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "index": "20200101000000001/index.html",
    "type": "",
    "title": "Page item - folder"
  },
  "20200101000000002": {
    "index": "20200101000000002.htz",
    "type": "",
    "title": "Page item - htz"
  },
  "20200101000000003": {
    "index": "20200101000000003.maff",
    "type": "",
    "title": "Page item - maff"
  },
  "20200101000000004": {
    "index": "20200101000000004.html",
    "type": "",
    "title": "Page item - single html"
  },
  "20200101000000005": {
    "type": "bookmark",
    "title": "Bookmark item",
    "source": "http://example.com/mypath?a=123&b=456"
  },
  "20200101000000006": {
    "type": "folder",
    "title": "Folder item"
  },
  "20200101000000007": {
    "type": "separator",
    "title": "Separator item"
  },
  "20200101000000008": {
    "type": "separator"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000001",
    "20200101000000002",
    "20200101000000003",
    "20200101000000004",
    "20200101000000005",
    "20200101000000006",
    "20200101000000007",
    "20200101000000008"
  ]
})""")

        index_file = os.path.join(self.test_input, '20200101000000001', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with open(index_file, 'wb') as fh:
            fh.write(b'dummy htz')

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with open(index_file, 'wb') as fh:
            fh.write(b'dummy maff')

        index_file = os.path.join(self.test_input, '20200101000000004.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('single file content')

        for _info in wsb2file.run(self.test_input, self.test_output):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '1-Page item - folder.htd'),
            os.path.join(self.test_output, '1-Page item - folder.htd', 'index.html'),
            os.path.join(self.test_output, '2-Page item - htz.htz'),
            os.path.join(self.test_output, '3-Page item - maff.maff'),
            os.path.join(self.test_output, '4-Page item - single html.html'),
            os.path.join(self.test_output, '5-Bookmark item.htm'),
            os.path.join(self.test_output, '6-Folder item'),
            os.path.join(self.test_output, '7-Separator item.-'),
            os.path.join(self.test_output, '8-----.-'),
        })
        with open(os.path.join(self.test_output, '1-Page item - folder.htd', 'index.html'), 'r', encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')
        with open(os.path.join(self.test_output, '2-Page item - htz.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy htz')
        with open(os.path.join(self.test_output, '3-Page item - maff.maff'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy maff')
        with open(os.path.join(self.test_output, '4-Page item - single html.html'), 'r', encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'single file content')
        with open(os.path.join(self.test_output, '5-Bookmark item.htm'), 'r', encoding='UTF-8') as fh:
            self.assertEqual(
                fh.read(),
                '<!DOCTYPE html>'
                '<meta charset="UTF-8">'
                '<meta http-equiv="refresh" content="0; url=http://example.com/mypath?a=123&amp;b=456">',
            )
        self.assertTrue(os.path.isdir(os.path.join(self.test_output, '6-Folder item')))
        with open(os.path.join(self.test_output, '7-Separator item.-'), 'rb') as fh:
            self.assertEqual(fh.read(), b'')
        with open(os.path.join(self.test_output, '8-----.-'), 'rb') as fh:
            self.assertEqual(fh.read(), b'')

    def test_basic02(self):
        """Check for typical WebScrapBook items. (prefix=False)"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "index": "20200101000000001/index.html",
    "type": "",
    "title": "Page item - folder"
  },
  "20200101000000002": {
    "index": "20200101000000002.htz",
    "type": "",
    "title": "Page item - htz"
  },
  "20200101000000003": {
    "index": "20200101000000003.maff",
    "type": "",
    "title": "Page item - maff"
  },
  "20200101000000004": {
    "index": "20200101000000004.html",
    "type": "",
    "title": "Page item - single html"
  },
  "20200101000000005": {
    "type": "bookmark",
    "title": "Bookmark item",
    "source": "http://example.com/mypath?a=123&b=456"
  },
  "20200101000000006": {
    "type": "folder",
    "title": "Folder item"
  },
  "20200101000000007": {
    "type": "separator",
    "title": "Separator item"
  },
  "20200101000000008": {
    "type": "separator"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000001",
    "20200101000000002",
    "20200101000000003",
    "20200101000000004",
    "20200101000000005",
    "20200101000000006",
    "20200101000000007",
    "20200101000000008"
  ]
})""")

        index_file = os.path.join(self.test_input, '20200101000000001', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with open(index_file, 'wb') as fh:
            fh.write(b'dummy htz')

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with open(index_file, 'wb') as fh:
            fh.write(b'dummy maff')

        index_file = os.path.join(self.test_input, '20200101000000004.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('single file content')

        for _info in wsb2file.run(self.test_input, self.test_output, prefix=False):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, 'Page item - folder.htd'),
            os.path.join(self.test_output, 'Page item - folder.htd', 'index.html'),
            os.path.join(self.test_output, 'Page item - htz.htz'),
            os.path.join(self.test_output, 'Page item - maff.maff'),
            os.path.join(self.test_output, 'Page item - single html.html'),
            os.path.join(self.test_output, 'Bookmark item.htm'),
            os.path.join(self.test_output, 'Folder item'),
        })
        with open(os.path.join(self.test_output, 'Page item - folder.htd', 'index.html'), 'r', encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'page content')
        with open(os.path.join(self.test_output, 'Page item - htz.htz'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy htz')
        with open(os.path.join(self.test_output, 'Page item - maff.maff'), 'rb') as fh:
            self.assertEqual(fh.read(), b'dummy maff')
        with open(os.path.join(self.test_output, 'Page item - single html.html'), 'r', encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'single file content')
        with open(os.path.join(self.test_output, 'Bookmark item.htm'), 'r', encoding='UTF-8') as fh:
            self.assertEqual(
                fh.read(),
                '<!DOCTYPE html>'
                '<meta charset="UTF-8">'
                '<meta http-equiv="refresh" content="0; url=http://example.com/mypath?a=123&amp;b=456">',
            )
        self.assertTrue(os.path.isdir(os.path.join(self.test_output, 'Folder item')))

    def test_path01(self):
        """Check hierarchical filename. (prefix=True)

        - An item with data and descendants is transformed into <title>/ and <title>.htd/
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "folder",
    "title": "Folder1"
  },
  "20200101000000002": {
    "index": "20200101000000002/index.html",
    "type": "",
    "title": "Folder1 sub"
  },
  "20200101000000003": {
    "index": "20200101000000003/index.html",
    "type": "",
    "title": "Folder2"
  },
  "20200101000000004": {
    "index": "20200101000000004/index.html",
    "type": "",
    "title": "Folder2 sub"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000001",
    "20200101000000003"
  ],
  "20200101000000001": [
    "20200101000000002"
  ],
  "20200101000000003": [
    "20200101000000004"
  ]
})""")

        index_file = os.path.join(self.test_input, '20200101000000002', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        index_file = os.path.join(self.test_input, '20200101000000003', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        index_file = os.path.join(self.test_input, '20200101000000004', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        for _info in wsb2file.run(self.test_input, self.test_output):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '1-Folder1'),
            os.path.join(self.test_output, '1-Folder1', '1-Folder1 sub.htd'),
            os.path.join(self.test_output, '1-Folder1', '1-Folder1 sub.htd', 'index.html'),
            os.path.join(self.test_output, '2-Folder2'),
            os.path.join(self.test_output, '2-Folder2', '1-Folder2 sub.htd'),
            os.path.join(self.test_output, '2-Folder2', '1-Folder2 sub.htd', 'index.html'),
            os.path.join(self.test_output, '2-Folder2.htd'),
            os.path.join(self.test_output, '2-Folder2.htd', 'index.html'),
        })

    def test_path02(self):
        """Check hierarchical filename. (prefix=False)

        - An item with data and descendants is transformed into <title>/ and <title>.htd/
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "folder",
    "title": "Folder1"
  },
  "20200101000000002": {
    "index": "20200101000000002/index.html",
    "type": "",
    "title": "Folder1 sub"
  },
  "20200101000000003": {
    "index": "20200101000000003/index.html",
    "type": "",
    "title": "Folder2"
  },
  "20200101000000004": {
    "index": "20200101000000004/index.html",
    "type": "",
    "title": "Folder2 sub"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000001",
    "20200101000000003"
  ],
  "20200101000000001": [
    "20200101000000002"
  ],
  "20200101000000003": [
    "20200101000000004"
  ]
})""")

        index_file = os.path.join(self.test_input, '20200101000000002', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        index_file = os.path.join(self.test_input, '20200101000000003', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        index_file = os.path.join(self.test_input, '20200101000000004', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        for _info in wsb2file.run(self.test_input, self.test_output, prefix=False):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, 'Folder1'),
            os.path.join(self.test_output, 'Folder1', 'Folder1 sub.htd'),
            os.path.join(self.test_output, 'Folder1', 'Folder1 sub.htd', 'index.html'),
            os.path.join(self.test_output, 'Folder2'),
            os.path.join(self.test_output, 'Folder2', 'Folder2 sub.htd'),
            os.path.join(self.test_output, 'Folder2', 'Folder2 sub.htd', 'index.html'),
            os.path.join(self.test_output, 'Folder2.htd'),
            os.path.join(self.test_output, 'Folder2.htd', 'index.html'),
        })

    def test_filename(self):
        """Check file extension handling.

        - An item index file without extension is transformed to <filename>._
          to prevent conflict with folder name.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "index": "20200101000000001",
    "type": "file",
    "title": "File1"
  },
  "20200101000000002": {
    "type": "bookmark",
    "title": "Bookmark1",
    "source": "http://example.com"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000001"
  ],
  "20200101000000001": [
    "20200101000000002"
  ]
})""")

        index_file = os.path.join(self.test_input, '20200101000000001')
        with open(index_file, 'wb') as fh:
            fh.write(b'dummy')

        for _info in wsb2file.run(self.test_input, self.test_output):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '1-File1'),
            os.path.join(self.test_output, '1-File1', '1-Bookmark1.htm'),
            os.path.join(self.test_output, '1-File1._'),
        })

    def test_numbering(self):
        """Check filename prefix is correctly zero-padded. (prefix=True)"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "folder",
    "title": "Folder1"
  },
  "20200101000000002": {
    "type": "folder",
    "title": "Folder2"
  },
  "20200101000000003": {
    "type": "folder",
    "title": "Folder3"
  },
  "20200101000000004": {
    "type": "folder",
    "title": "Folder4"
  },
  "20200101000000005": {
    "type": "folder",
    "title": "Folder5"
  },
  "20200101000000006": {
    "type": "folder",
    "title": "Folder6"
  },
  "20200101000000007": {
    "type": "folder",
    "title": "Folder7"
  },
  "20200101000000008": {
    "type": "folder",
    "title": "Folder8"
  },
  "20200101000000009": {
    "type": "folder",
    "title": "Folder9"
  },
  "20200101000000010": {
    "type": "folder",
    "title": "Folder10"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000001",
    "20200101000000002",
    "20200101000000003",
    "20200101000000004",
    "20200101000000005",
    "20200101000000006",
    "20200101000000007",
    "20200101000000008",
    "20200101000000009",
    "20200101000000010"
  ]
})""")

        for _info in wsb2file.run(self.test_input, self.test_output):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '01-Folder1'),
            os.path.join(self.test_output, '02-Folder2'),
            os.path.join(self.test_output, '03-Folder3'),
            os.path.join(self.test_output, '04-Folder4'),
            os.path.join(self.test_output, '05-Folder5'),
            os.path.join(self.test_output, '06-Folder6'),
            os.path.join(self.test_output, '07-Folder7'),
            os.path.join(self.test_output, '08-Folder8'),
            os.path.join(self.test_output, '09-Folder9'),
            os.path.join(self.test_output, '10-Folder10'),
        })

    def test_deduplicate(self):
        """Check duplicated title handling. (prefix=False)

        - Deduplicate even if extension is different.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "index": "20200101000000001/index.html",
    "type": "",
    "title": "myitem"
  },
  "20200101000000002": {
    "index": "20200101000000002.htz",
    "type": "",
    "title": "myitem"
  },
  "20200101000000003": {
    "index": "20200101000000003.maff",
    "type": "",
    "title": "myitem"
  },
  "20200101000000004": {
    "index": "20200101000000004.html",
    "type": "",
    "title": "myitem"
  },
  "20200101000000005": {
    "type": "bookmark",
    "title": "myitem",
    "source": "http://example.com/mypath?a=123&b=456"
  },
  "20200101000000006": {
    "type": "folder",
    "title": "myitem"
  },
  "20200101000000007": {
    "type": "separator",
    "title": "myitem"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000001",
    "20200101000000002",
    "20200101000000003",
    "20200101000000004",
    "20200101000000005",
    "20200101000000006",
    "20200101000000007"
  ]
})""")

        index_file = os.path.join(self.test_input, '20200101000000001', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        index_file = os.path.join(self.test_input, '20200101000000002.htz')
        with open(index_file, 'wb') as fh:
            fh.write(b'dummy htz')

        index_file = os.path.join(self.test_input, '20200101000000003.maff')
        with open(index_file, 'wb') as fh:
            fh.write(b'dummy maff')

        index_file = os.path.join(self.test_input, '20200101000000004.html')
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('single file content')

        for _info in wsb2file.run(self.test_input, self.test_output, prefix=False):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, 'myitem.htd'),
            os.path.join(self.test_output, 'myitem.htd', 'index.html'),
            os.path.join(self.test_output, 'myitem(1).htz'),
            os.path.join(self.test_output, 'myitem(2).maff'),
            os.path.join(self.test_output, 'myitem(3).html'),
            os.path.join(self.test_output, 'myitem(4).htm'),
            os.path.join(self.test_output, 'myitem(5)'),
        })

    def test_recursive(self):
        """Check if recursive item is correctly handled."""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000001": {
    "type": "folder",
    "title": "Folder1"
  },
  "20200101000000002": {
    "type": "folder",
    "title": "Folder2"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000001"
  ],
  "20200101000000001": [
    "20200101000000002"
  ],
  "20200101000000002": [
    "20200101000000001"
  ]
})""")

        for _info in wsb2file.run(self.test_input, self.test_output):
            pass

        self.assertEqual(set(glob.iglob(os.path.join(self.test_output, '**'), recursive=True)), {
            os.path.join(self.test_output, ''),
            os.path.join(self.test_output, '1-Folder1'),
            os.path.join(self.test_output, '1-Folder1', '1-Folder2'),
            os.path.join(self.test_output, '1-Folder1', '1-Folder2', '1-Folder1'),
        })


if __name__ == '__main__':
    unittest.main()
