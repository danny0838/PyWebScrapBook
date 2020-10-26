from unittest import mock
import unittest
import os
import shutil
import zipfile
import time
from base64 import b64decode
from datetime import datetime, timezone

from lxml import etree

from webscrapbook import WSB_DIR
from webscrapbook import util
from webscrapbook.scrapbook.host import Host
from webscrapbook.scrapbook.convert import wsb2sb
from webscrapbook.scrapbook.convert.wsb2sb import RDF, NS1, NC

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
        cls.test_input_config = os.path.join(cls.test_input, WSB_DIR, 'config.ini')
        cls.test_input_tree = os.path.join(cls.test_input, WSB_DIR, 'tree')
        cls.test_input_meta = os.path.join(cls.test_input_tree, 'meta.js')
        cls.test_input_toc = os.path.join(cls.test_input_tree, 'toc.js')
        cls.test_output = os.path.join(test_root, 'output')
        cls.test_output_rdf = os.path.join(cls.test_output, 'scrapbook.rdf')

    def setUp(self):
        """Set up a general temp test folder
        """
        os.makedirs(self.test_input_tree, exist_ok=True)
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

    def test_meta_basic(self):
        """A sample of typical WebScrapBook item."""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "title": "Hello 中文",
    "create": "20200102000000000",
    "modify": "20200103000000000",
    "source": "http://example.com",
    "icon": "favicon.bmp",
    "comment": "some comment\\nsecond line\\nthird line",
    "charset": "UTF-8",
    "locked": true
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        icon_file = os.path.join(self.test_input, '20200101000000000', 'favicon.bmp')
        os.makedirs(os.path.dirname(icon_file), exist_ok=True)
        with open(icon_file, 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        oid = util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000'))
        self.assertEqual(tree.getroot().tag, f'{RDF}RDF')
        self.assertEqual(dict(tree.find(f'{RDF}Description').attrib), {
            f'{RDF}about': f'urn:scrapbook:item{oid}',
            f'{NS1}id': oid,
            f'{NS1}type': '',
            f'{NS1}title': 'Hello 中文',
            f'{NS1}create': util.datetime_to_id_legacy(util.id_to_datetime('20200102000000000')),
            f'{NS1}modify': util.datetime_to_id_legacy(util.id_to_datetime('20200103000000000')),
            f'{NS1}source': 'http://example.com',
            f'{NS1}icon': f'resource://scrapbook/data/{oid}/favicon.bmp',
            f'{NS1}comment': 'some comment __BR__ second line __BR__ third line',
            f'{NS1}chars': 'UTF-8',
            f'{NS1}lock': 'true'
            })

    def test_meta_separator(self):
        """A sample of typical WebScrapBook separator item."""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "separator",
    "title": "Hello 中文",
    "create": "20200102000000000",
    "modify": "20200103000000000"
  }
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        oid = util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000'))
        self.assertEqual(dict(tree.find(f'{NC}BookmarkSeparator').attrib), {
            f'{RDF}about': f'urn:scrapbook:item{oid}',
            f'{NS1}id': oid,
            f'{NS1}type': 'separator',
            f'{NS1}title': 'Hello 中文',
            f'{NS1}create': util.datetime_to_id_legacy(util.id_to_datetime('20200102000000000')),
            f'{NS1}modify': util.datetime_to_id_legacy(util.id_to_datetime('20200103000000000')),
            f'{NS1}source': '',
            f'{NS1}icon': '',
            f'{NS1}comment': '',
            f'{NS1}chars': '',
            })

    def test_meta_type01(self):
        """postit => note"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "postit"
  }
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(tree.find(f'{RDF}Description').attrib[f'{NS1}type'], 'note')

    def test_meta_type02(self):
        """note => notex"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "note"
  }
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(tree.find(f'{RDF}Description').attrib[f'{NS1}type'], 'notex')

    def test_meta_marked01(self):
        """true marked property with "" type => marked type"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "marked": true
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(tree.find(f'{RDF}Description').attrib[f'{NS1}type'], 'marked')
        self.assertIsNone(tree.find(f'{RDF}Description').attrib.get(f'{NS1}marked'))

    def test_meta_marked02(self):
        """marked property with other type => discard marked"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "file",
    "marked": true
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(tree.find(f'{RDF}Description').attrib[f'{NS1}type'], 'file')
        self.assertIsNone(tree.find(f'{RDF}Description').attrib.get(f'{NS1}marked'))

    def test_meta_marked03(self):
        """false marked property => normal type"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "marked": false
  }
})""")

        index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('page content')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(tree.find(f'{RDF}Description').attrib[f'{NS1}type'], '')
        self.assertIsNone(tree.find(f'{RDF}Description').attrib.get(f'{NS1}marked'))

    def test_meta_create(self):
        """empty create property => no create property"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "create": ""
  }
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertIsNone(tree.find(f'{RDF}Description').attrib.get(f'{NS1}create'))

    def test_meta_modify(self):
        """empty modify property => no modify property"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "modify": ""
  }
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertIsNone(tree.find(f'{RDF}Description').attrib.get(f'{NS1}modify'))

    def test_meta_icon01(self):
        """Empty icon with icon-moz property => moz-icon:// """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "image",
    "icon": "",
    "icon-moz": "moz-icon://myimage.png?size=16"
  }
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            tree.find(f'{RDF}Description').attrib[f'{NS1}icon'],
            'moz-icon://myimage.png?size=16'
            )

    def test_meta_icon02(self):
        """File with empty icon => moz-icon:// """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "file",
    "icon": ""
  }
})""")
        index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('<meta charset="UTF-8"><meta http-equiv="refresh" content="0;URL=./myfile.txt">')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            tree.find(f'{RDF}Description').attrib[f'{NS1}icon'],
            'moz-icon://myfile.txt?size=16'
            )

    def test_meta_icon03(self):
        """Absolute URL => use as-is"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "icon": "data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA"
  }
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            tree.find(f'{RDF}Description').attrib[f'{NS1}icon'],
            'data:image/bmp;base64,Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'
            )

    def test_meta_icon04(self):
        """Favicon cache => icon folder"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.html",
    "type": "",
    "icon": ".wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp"
  }
})""")
        icon_file = os.path.join(self.test_input_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp')
        os.makedirs(os.path.dirname(icon_file), exist_ok=True)
        with open(icon_file, 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            tree.find(f'{RDF}Description').attrib[f'{NS1}icon'],
            'resource://scrapbook/icon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'
            )
        self.assertTrue(
            os.path.isfile(os.path.join(self.test_output, 'icon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp'))
            )

    def test_meta_icon05(self):
        """Item folder => mapped item folder"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "icon": "favicon.bmp"
  }
})""")
        icon_file = os.path.join(self.test_input, '20200101000000000', 'favicon.bmp')
        os.makedirs(os.path.dirname(icon_file), exist_ok=True)
        with open(icon_file, 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            tree.find(f'{RDF}Description').attrib[f'{NS1}icon'],
            'resource://scrapbook/data/20200101080000/favicon.bmp'
            )
        self.assertTrue(
            os.path.isfile(os.path.join(self.test_output, 'data', '20200101080000', 'favicon.bmp'))
            )

    def test_meta_icon06(self):
        """Data folder => data folder"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "icon": "../icons/favicon.bmp"
  }
})""")
        icon_file = os.path.join(self.test_input, 'icons', 'favicon.bmp')
        os.makedirs(os.path.dirname(icon_file), exist_ok=True)
        with open(icon_file, 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            tree.find(f'{RDF}Description').attrib[f'{NS1}icon'],
            'resource://scrapbook/data/icons/favicon.bmp'
            )
        self.assertTrue(
            os.path.isfile(os.path.join(self.test_output, 'data', 'icons', 'favicon.bmp'))
            )

    def test_meta_icon07(self):
        """Outside of data folder => scrapbook folder"""
        with open(self.test_input_config, 'w', encoding='UTF-8') as fh:
            fh.write("""\
[book ""]
data_dir = data
tree_dir = tree
""")
        meta_file = os.path.join(self.test_input, 'tree', 'meta.js')
        os.makedirs(os.path.dirname(meta_file), exist_ok=True)
        with open(meta_file, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": "",
    "icon": "../../icons/favicon.bmp"
  }
})""")
        icon_file = os.path.join(self.test_input, 'icons', 'favicon.bmp')
        os.makedirs(os.path.dirname(icon_file), exist_ok=True)
        with open(icon_file, 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual(
            tree.find(f'{RDF}Description').attrib[f'{NS1}icon'],
            'resource://scrapbook/icons/favicon.bmp'
            )
        self.assertTrue(
            os.path.isfile(os.path.join(self.test_output, 'icons', 'favicon.bmp'))
            )

    def test_id_mapping01(self):
        """WebScrapBook timestamp => legacy ScrapBook timestamp"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder"
  },
  "20200101000001000": {
    "type": "folder"
  },
  "20200101000002000": {
    "type": "folder"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000001000",
    "20200101000002000"
  ]
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual([node.attrib[f'{NS1}id'] for node in tree.findall(f'{RDF}Description')], [
            util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000')),
            util.datetime_to_id_legacy(util.id_to_datetime('20200101000001000')),
            util.datetime_to_id_legacy(util.id_to_datetime('20200101000002000')),
            ])
        self.assertEqual([node.attrib[f'{RDF}resource'] for node in tree.findall(f'{RDF}Seq/{RDF}li')], [
            'urn:scrapbook:item' + util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000')),
            'urn:scrapbook:item' + util.datetime_to_id_legacy(util.id_to_datetime('20200101000001000')),
            'urn:scrapbook:item' + util.datetime_to_id_legacy(util.id_to_datetime('20200101000002000')),
            ])

    def test_id_mapping02(self):
        """If conflict, increament by 1 from timestamp"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder"
  },
  "20200101000000001": {
    "type": "folder"
  },
  "20200101000000010": {
    "type": "folder"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000000001",
    "20200101000000010"
  ]
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual([node.attrib[f'{NS1}id'] for node in tree.findall(f'{RDF}Description')], [
            util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000')),
            util.datetime_to_id_legacy(util.id_to_datetime('20200101000001000')),
            util.datetime_to_id_legacy(util.id_to_datetime('20200101000002000')),
            ])
        self.assertEqual([node.attrib[f'{RDF}resource'] for node in tree.findall(f'{RDF}Seq/{RDF}li')], [
            'urn:scrapbook:item' + util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000')),
            'urn:scrapbook:item' + util.datetime_to_id_legacy(util.id_to_datetime('20200101000001000')),
            'urn:scrapbook:item' + util.datetime_to_id_legacy(util.id_to_datetime('20200101000002000')),
            ])

    def test_id_mapping03(self):
        """Legacy timestamp => use as-is"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000": {
    "type": "folder"
  },
  "20200101000010": {
    "type": "folder"
  },
  "20200101000100": {
    "type": "folder"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000",
    "20200101000010",
    "20200101000100"
  ]
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual([node.attrib[f'{NS1}id'] for node in tree.findall(f'{RDF}Description')], [
            '20200101000000',
            '20200101000010',
            '20200101000100',
            ])
        self.assertEqual([node.attrib[f'{RDF}resource'] for node in tree.findall(f'{RDF}Seq/{RDF}li')], [
            'urn:scrapbook:item20200101000000',
            'urn:scrapbook:item20200101000010',
            'urn:scrapbook:item20200101000100',
            ])

    def test_id_mapping04(self):
        """Increament by 1 from now if not timestamp"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "dummy1": {
    "type": "folder"
  },
  "dummy2": {
    "type": "folder"
  },
  "dummy3": {
    "type": "folder"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "dummy1",
    "dummy2",
    "dummy3"
  ]
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        ts_now = datetime.now(timezone.utc).timestamp()
        id_list = [n.attrib[f'{NS1}id'] for n in tree.findall(f'{RDF}Description')]
        ts_list = [util.id_to_datetime_legacy(id).timestamp() for id in id_list]
        self.assertAlmostEqual(ts_list[0], ts_now, delta=3)
        self.assertEqual(ts_list[0] + 1, ts_list[1])
        self.assertEqual(ts_list[0] + 2, ts_list[2])

        self.assertEqual([node.attrib[f'{RDF}resource'] for node in tree.findall(f'{RDF}Seq/{RDF}li')], [
            'urn:scrapbook:item' + id_list[0],
            'urn:scrapbook:item' + id_list[1],
            'urn:scrapbook:item' + id_list[2],
            ])

    def test_toc_no_root(self):
        """root list not exist => empty root container"""
        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertIsNotNone(tree.find(f'{RDF}Seq[@{RDF}about="urn:scrapbook:root"]'))
        self.assertIsNone(tree.find(f'{RDF}Seq[@{RDF}about="urn:scrapbook:root"]/{RDF}li'))

    def test_toc_duplicate(self):
        """Duplicated item => preserve only the first one (depth first)"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000001": {
    "type": "folder"
  },
  "20200101000002": {
    "type": "folder"
  },
  "20200101000003": {
    "type": "folder"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000001",
    "20200101000002",
    "20200101000003"
  ],
  "20200101000001": [
    "20200101000002"
  ]
})""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        with open(self.test_output_rdf, 'rb') as fh:
            tree = etree.parse(fh)

        self.assertEqual([
            node.attrib[f'{RDF}resource']
            for node in
            tree.findall(f'{RDF}Seq[@{RDF}about="urn:scrapbook:root"]/{RDF}li')
            ], [
            'urn:scrapbook:item20200101000001',
            'urn:scrapbook:item20200101000003',
            ])

        self.assertEqual([
            node.attrib[f'{RDF}resource']
            for node in
            tree.findall(f'{RDF}Seq[@{RDF}about="urn:scrapbook:item20200101000001"]/{RDF}li')
            ], [
            'urn:scrapbook:item20200101000002',
            ])

    def test_copy_data_files01(self):
        """###/index.html => copy ###/* to <ID>/*"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000/index.html",
    "type": ""
  }
})""")

        index_dir = os.path.join(self.test_input, '20200101000000000')
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('page content')
        with open(os.path.join(index_dir, 'page.html'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')
        os.makedirs(os.path.join(self.test_input, '20200101000000001'), exist_ok=True)
        with open(os.path.join(self.test_input, 'other.html'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        oid = util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000'))
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data'))),
            {oid},
            )
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data', oid))),
            {'index.html', 'page.html'},
            )

    def test_copy_data_files02(self):
        """###.html => copy ###.html to <ID>/*"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.html",
    "type": ""
  }
})""")

        with open(os.path.join(self.test_input, '20200101000000000.html'), 'w', encoding='UTF-8') as fh:
            fh.write('page content')
        with open(os.path.join(self.test_input, 'page.html'), 'w', encoding='UTF-8') as fh:
            fh.write('dummy')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        oid = util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000'))
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data'))),
            {oid},
            )
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data', oid))),
            {'index.html'},
            )

    def test_copy_data_files03(self):
        """###.htz => copy internal files to <ID>/*"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.htz",
    "type": ""
  }
})""")

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000000.htz'), 'w') as zh:
            zh.writestr('index.html', 'page content')
            zh.writestr('page.html', 'dummy')
            zh.writestr('subdir/page2.html', 'dummy2')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        oid = util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000'))
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data'))),
            {oid},
            )
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data', oid))),
            {'index.html', 'page.html', 'subdir'},
            )
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data', oid, 'subdir'))),
            {'page2.html'},
            )

    def test_copy_data_files04(self):
        """###.maff => copy internal files of first topdir to <ID>/*"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.maff",
    "type": ""
  }
})""")

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000000.maff'), 'w') as zh:
            zh.writestr('20200101000000000/index.html', 'page content')
            zh.writestr('20200101000000000/page.html', 'dummy')
            zh.writestr('20200101000000000/subdir/page2.html', 'dummy2')
            zh.writestr('20200101000000001/index.html', 'page content 2')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        oid = util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000'))
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data'))),
            {oid},
            )
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data', oid))),
            {'index.html', 'page.html', 'subdir'},
            )
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data', oid, 'subdir'))),
            {'page2.html'},
            )

    def test_copy_data_files05(self):
        """###.maff => copy nothing if no page"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "20200101000000000.maff",
    "type": ""
  }
})""")

        with zipfile.ZipFile(os.path.join(self.test_input, '20200101000000000.maff'), 'w') as zh:
            zh.writestr('index.html', 'dummy')

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        oid = util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000'))
        self.assertFalse(os.path.lexists(os.path.join(self.test_output, 'data', oid)))

    def test_copy_data_files06(self):
        """foo.bar => copy it and create meta refresh"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "index": "中文#1.xhtml",
    "type": ""
  }
})""")

        with open(os.path.join(self.test_input, '中文#1.xhtml'), 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Title of document</title>
</head>
<body>
some content
</body>
</html>
""")

        for info in wsb2sb.run(self.test_input, self.test_output):
            pass

        oid = util.datetime_to_id_legacy(util.id_to_datetime('20200101000000000'))
        self.assertEqual(
            set(os.listdir(os.path.join(self.test_output, 'data', oid))),
            {'index.html', '中文#1.xhtml'},
            )
        self.assertEqual(
            util.parse_meta_refresh(os.path.join(self.test_output, 'data', oid, 'index.html')).target,
            './%E4%B8%AD%E6%96%87%231.xhtml'
            )

if __name__ == '__main__':
    unittest.main()
