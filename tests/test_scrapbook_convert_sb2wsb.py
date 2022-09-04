import os
import shutil
import time
import unittest
from unittest import mock

from webscrapbook import WSB_DIR, util
from webscrapbook.scrapbook.book import Book
from webscrapbook.scrapbook.convert import sb2wsb
from webscrapbook.scrapbook.host import Host

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
        cls.test_input_rdf = os.path.join(cls.test_input, 'scrapbook.rdf')
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

    def test_meta_basic01(self):
        """A typical item sample of legacy ScrapBook X."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:id="20200102030405"
                   NS1:create="20200102030406"
                   NS1:modify="20200102030407"
                   NS1:type=""
                   NS1:title="dummy title"
                   NS1:chars="UTF-8"
                   NS1:icon="favicon.ico"
                   NS1:source="http://example.com/foo"
                   NS1:comment="dummy comment __BR__ 2nd line"
                   NS1:lock="true" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertDictEqual(book.meta['20200102030405'], {
            'index': '20200102030405/index.html',
            'title': 'dummy title',
            'type': '',
            'create': util.datetime_to_id(util.id_to_datetime_legacy('20200102030406')),
            'modify': util.datetime_to_id(util.id_to_datetime_legacy('20200102030407')),
            'source': 'http://example.com/foo',
            'icon': 'favicon.ico',
            'comment': 'dummy comment\n2nd line',
            'charset': 'UTF-8',
            'locked': True,
        })

    def test_meta_basic02(self):
        """A typical item sample of legacy ScrapBook."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:id="20200102030405"
                   NS1:type=""
                   NS1:title="dummy title"
                   NS1:chars=""
                   NS1:comment="dummy comment __BR__ 2nd line"
                   NS1:icon="favicon.ico"
                   NS1:source="http://example.com/foo" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertDictEqual(book.meta['20200102030405'], {
            'index': '20200102030405/index.html',
            'title': 'dummy title',
            'type': '',
            'create': util.datetime_to_id(util.id_to_datetime_legacy('20200102030405')),
            'modify': util.datetime_to_id(util.id_to_datetime_legacy('20200102030405')),
            'source': 'http://example.com/foo',
            'icon': 'favicon.ico',
            'comment': 'dummy comment\n2nd line',
        })

    def test_meta_basic03(self):
        """Default value for missing keys.

        - type: ""
        - create: infer from id
        - modify: infer from create (and then id)
        """
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertDictEqual(book.meta['20200102030405'], {
            'index': '20200102030405/index.html',
            'type': '',
            'create': util.datetime_to_id(util.id_to_datetime_legacy('20200102030405')),
            'modify': util.datetime_to_id(util.id_to_datetime_legacy('20200102030405')),
        })

    def test_meta_basic04(self):
        """Should work correctly for another NS name

        (seen in some scrapbook.rdf files)
        """
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS2="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS2:id="20200102030405"
                   NS2:type=""
                   NS2:title="title"
                   NS2:comment="comment"
                   NS2:icon="favicon.ico"
                   NS2:source="http://example.com" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertDictEqual(book.meta['20200102030405'], {
            'index': '20200102030405/index.html',
            'type': '',
            'create': util.datetime_to_id(util.id_to_datetime_legacy('20200102030405')),
            'modify': util.datetime_to_id(util.id_to_datetime_legacy('20200102030405')),
            'title': 'title',
            'comment': 'comment',
            'icon': 'favicon.ico',
            'source': 'http://example.com',
        })

    def test_meta_type01(self):
        """Translate types."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200101010101"
                   NS1:type="" />
  <RDF:Description RDF:about="urn:scrapbook:item20200101010102"
                   NS1:type="combine" />
  <RDF:Description RDF:about="urn:scrapbook:item20200101010103"
                   NS1:type="marked" />
  <RDF:Description RDF:about="urn:scrapbook:item20200101010104"
                   NS1:type="note" />
  <RDF:Description RDF:about="urn:scrapbook:item20200101010105"
                   NS1:type="notex" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200101010101']['type'], '')
        self.assertIsNone(book.meta['20200101010101'].get('marked'))
        self.assertEqual(book.meta['20200101010102']['type'], 'combine')
        self.assertIsNone(book.meta['20200101010102'].get('marked'))
        self.assertEqual(book.meta['20200101010103']['type'], '')
        self.assertTrue(book.meta['20200101010103']['marked'])
        self.assertEqual(book.meta['20200101010104']['type'], 'postit')
        self.assertIsNone(book.meta['20200101010104'].get('marked'))
        self.assertEqual(book.meta['20200101010105']['type'], 'note')
        self.assertIsNone(book.meta['20200101010105'].get('marked'))

    def test_meta_type02(self):
        """Use "site" if it's "marked" and has sitemap.xml"""
        index_file = os.path.join(self.test_input, 'data', '20200101010101', 'index.html')
        sitemap_file = os.path.join(self.test_input, 'data', '20200101010101', 'sitemap.xml')
        os.makedirs(os.path.dirname(sitemap_file))
        with open(index_file, 'w', encoding='UTF-8') as fh:
            pass
        with open(sitemap_file, 'w', encoding='UTF-8') as fh:
            pass

        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200101010101"
                   NS1:type="marked" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200101010101']['type'], 'site')
        self.assertTrue(book.meta['20200101010101']['marked'])

    def test_meta_modify01(self):
        """Take modify if defined."""
        index_file = os.path.join(self.test_input, 'data', '20200102030405', 'index.html')
        os.makedirs(os.path.dirname(index_file))
        with open(index_file, 'w', encoding='UTF-8') as fh:
            pass
        t = time.mktime((2020, 1, 3, 0, 0, 0, 0, 0, -1))
        os.utime(index_file, (t, t))

        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:id="20200102030405"
                   NS1:type=""
                   NS1:create="20200102030406"
                   NS1:modify="20200102030407" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(
            book.meta['20200102030405']['modify'],
            util.datetime_to_id(util.id_to_datetime_legacy('20200102030407')),
        )

    def test_meta_modify02(self):
        """Take mtime of index.html if modify not defined."""
        index_file = os.path.join(self.test_input, 'data', '20200102030405', 'index.html')
        os.makedirs(os.path.dirname(index_file))
        with open(index_file, 'w', encoding='UTF-8') as fh:
            pass
        t = time.mktime((2020, 1, 3, 0, 0, 0, 0, 0, -1))
        os.utime(index_file, (t, t))

        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:id="20200102030405"
                   NS1:type=""
                   NS1:create="20200102030406" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(
            book.meta['20200102030405']['modify'],
            util.datetime_to_id(util.id_to_datetime_legacy('20200103000000')),
        )

    def test_meta_modify03(self):
        """Take create if modify not defined and no index.html."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:id="20200102030405"
                   NS1:type=""
                   NS1:create="20200102030406" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(
            book.meta['20200102030405']['modify'],
            util.datetime_to_id(util.id_to_datetime_legacy('20200102030406')),
        )

    def test_meta_icon01(self):
        """Resolve resource://scrapbook/data/<self-id>/..."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:icon="resource://scrapbook/data/20200102030405/favicon.ico" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200102030405']['icon'], 'favicon.ico')

    def test_meta_icon02(self):
        """Resolve resource://scrapbook/icon/..."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:icon="resource://scrapbook/icon/favicon.ico" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200102030405']['icon'], '../../icon/favicon.ico')

    def test_meta_icon03(self):
        """Resolve resource://scrapbook/..."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:icon="resource://scrapbook/favicon.ico" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200102030405']['icon'], '../../favicon.ico')

    def test_meta_icon04(self):
        """Resolve moz-icon://..."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:icon="moz-icon://foo.pdf?size=16" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200102030405']['icon'], '')
        self.assertEqual(book.meta['20200102030405']['icon-moz'], 'moz-icon://foo.pdf?size=16')

    def test_meta_icon05(self):
        """Handle special chars."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:icon="resource://scrapbook/%E4%B8%AD%E6%96%87%25%23abc.png" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200102030405']['icon'], '../../%E4%B8%AD%E6%96%87%25%23abc.png')

    def test_meta_icon06(self):
        """Special handling for an item without index file."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:type="bookmark"
                   NS1:icon="resource://scrapbook/data/20200101000000/favicon.ico" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200102030405']['icon'], '20200101000000/favicon.ico')

    def test_meta_icon07(self):
        """Special handling for an item with icon in self folder but no index file."""
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:scrapbook:item20200102030405"
                   NS1:type="folder"
                   NS1:icon="resource://scrapbook/data/20200102030405/favicon.ico" />
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_meta_files()

        self.assertEqual(book.meta['20200102030405']['index'], '20200102030405/index.html')
        self.assertEqual(book.meta['20200102030405']['icon'], 'favicon.ico')

    def test_toc(self):
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Seq RDF:about="urn:scrapbook:root">
    <RDF:li RDF:resource="urn:scrapbook:item20200101000000"/>
    <RDF:li RDF:resource="urn:scrapbook:item20200101000001"/>
    <RDF:li RDF:resource="urn:scrapbook:item20200101000002"/>
    <RDF:li RDF:resource="urn:scrapbook:item20200101000003"/>
    <RDF:li RDF:resource="urn:scrapbook:item20200101000004"/>
  </RDF:Seq>
  <RDF:Seq RDF:about="urn:scrapbook:item20200101000001">
    <RDF:li RDF:resource="urn:scrapbook:item20200101000005"/>
    <RDF:li RDF:resource="urn:scrapbook:item20200101000006"/>
  </RDF:Seq>
  <RDF:Seq RDF:about="urn:scrapbook:item20200101000002">
    <RDF:li RDF:resource="urn:scrapbook:item20200101000007"/>
    <RDF:li RDF:resource="urn:scrapbook:item20200101000008"/>
  </RDF:Seq>
  <RDF:Seq RDF:about="urn:scrapbook:item20200101000003">
    <RDF:li RDF:resource="urn:scrapbook:item20200101000009"/>
  </RDF:Seq>
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        book = Host(self.test_output).books['']
        book.load_toc_files()

        self.assertEqual(book.toc, {
            'root': [
                '20200101000000',
                '20200101000001',
                '20200101000002',
                '20200101000003',
                '20200101000004',
            ],
            '20200101000001': [
                '20200101000005',
                '20200101000006',
            ],
            '20200101000002': [
                '20200101000007',
                '20200101000008',
            ],
            '20200101000003': [
                '20200101000009',
            ],
        })

    def test_backup01(self):
        """Check legacy scrapbook files are backuped"""
        check_entries = [
            'backup/',
            'tree/',
            'scrapbook.rdf',
            'cache.rdf',
            'folders.txt',
            'collection.html',
            'combine.html',
            'combine.css',
            'note.html',
            'search.html',
            'sitemap.xsl',
            'note_template.html',
            'notex_template.html',
        ]

        for entry in check_entries:
            path = os.path.join(self.test_input, entry)
            if entry.endswith('/'):
                os.makedirs(path)
                with open(os.path.join(path, 'dummy'), 'w', encoding='UTF-8') as fh:
                    fh.write(entry)
            else:
                with open(path, 'w', encoding='UTF-8') as fh:
                    fh.write(entry)

        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        with os.scandir(os.path.join(self.test_output, WSB_DIR, 'backup')) as dirs:
            backup_dir = next(iter(dirs))
        for entry in check_entries:
            with self.subTest(entry=entry):
                path = os.path.join(backup_dir, entry)
                if entry.endswith('/'):
                    self.assertTrue(os.path.isdir(path))
                    self.assertTrue(os.path.isfile(os.path.join(path, 'dummy')))
                else:
                    self.assertTrue(os.path.isfile(path))

    def test_backup02(self):
        """Check no_backup"""
        check_entries = [
            'backup/',
            'tree/',
            'scrapbook.rdf',
            'cache.rdf',
            'folders.txt',
            'collection.html',
            'combine.html',
            'combine.css',
            'note.html',
            'search.html',
            'sitemap.xsl',
            'note_template.html',
            'notex_template.html',
        ]

        for entry in check_entries:
            path = os.path.join(self.test_input, entry)
            if entry.endswith('/'):
                os.makedirs(path)
                with open(os.path.join(path, 'dummy'), 'w', encoding='UTF-8') as fh:
                    fh.write(entry)
            else:
                with open(path, 'w', encoding='UTF-8') as fh:
                    fh.write(entry)

        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output, no_backup=True):
            pass

        self.assertFalse(os.path.exists(os.path.join(self.test_output, WSB_DIR, 'backup')))

    @mock.patch('webscrapbook.scrapbook.convert.migrate.ConvertDataFilesLegacy')
    def test_data01(self, mock_convert):
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output):
            pass

        mock_convert.assert_called_once()
        self.assertIsInstance(mock_convert.mock_calls[0][1][0], Book)
        self.assertEqual(mock_convert.mock_calls[0][1][0].id, '')
        self.assertEqual(mock_convert.mock_calls[0][1][0].top_dir, self.test_output)
        mock_convert.return_value.run.assert_called_once_with()

    @mock.patch('webscrapbook.scrapbook.convert.migrate.ConvertDataFilesLegacy')
    def test_data02(self, mock_convert):
        with open(self.test_input_rdf, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
</RDF:RDF>
""")

        for _info in sb2wsb.run(self.test_input, self.test_output, no_data_files=True):
            pass

        mock_convert.assert_not_called()


if __name__ == '__main__':
    unittest.main()
