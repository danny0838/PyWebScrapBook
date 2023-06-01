import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import lxml.html

from webscrapbook import util
from webscrapbook._polyfill import zipfile

from . import DUMMY_ZIP_DT, ROOT_DIR, TEMP_DIR, require_altsep, require_sep

test_root = os.path.join(ROOT_DIR, 'test_util')


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='util-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)


def tearDownModule():
    # cleanup the temp directory
    _tmpdir.cleanup()


class TestUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def test_import_module_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'import_module_file.py')
        with open(dst, 'w', encoding='UTF-8') as fh:
            fh.write("""test_key = 'test_value'""")

        # import
        mod = util.import_module_file('webscrapbook._test_import_module_file', dst)
        self.assertEqual(mod.__name__, 'webscrapbook._test_import_module_file')
        self.assertEqual(mod.test_key, 'test_value')

        # reuse if imported
        mod2 = util.import_module_file('webscrapbook._test_import_module_file', dst)
        self.assertIs(mod2, mod)

    def test_datetime_to_id(self):
        # create an ID from UTC time
        self.assertEqual(
            util.datetime_to_id(datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc)),
            '20200102030405067')

        # create an ID from corresponding UTC time if datetime is another timezone
        self.assertEqual(
            util.datetime_to_id(datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone(timedelta(hours=8)))),
            '20200101190405067')

        # create for now if datetime not provided
        self.assertAlmostEqual(
            util.id_to_datetime(util.datetime_to_id(None)).timestamp(),
            datetime.now(timezone.utc).timestamp(),
            delta=3)

    def test_datetime_to_id_legacy(self):
        # create an ID from local datetime
        self.assertEqual(
            util.datetime_to_id_legacy(datetime(2020, 1, 2, 3, 4, 5, 67000)),
            '20200102030405')

        # create an ID from the corresponding local time if datetime is at another timezone
        dt = datetime(2020, 1, 2, 3, 4, 5, 67000)
        self.assertEqual(
            util.datetime_to_id_legacy(datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc)),
            util.datetime_to_id_legacy(dt + dt.astimezone().utcoffset()),
        )

        # create for now if datetime not provided
        self.assertAlmostEqual(
            util.id_to_datetime_legacy(util.datetime_to_id_legacy(None)).timestamp(),
            datetime.now().timestamp(),
            delta=3,
        )

    def test_id_to_datetime(self):
        self.assertEqual(
            util.id_to_datetime('20200102030405067'),
            datetime(2020, 1, 2, 3, 4, 5, 67000, timezone.utc),
        )

        # invalid format (not match regex)
        self.assertIsNone(util.id_to_datetime('20200102030405'))

        # invalid format (number out of range)
        self.assertIsNone(util.id_to_datetime('20200102030465067'))

    def test_id_to_datetime_legacy(self):
        self.assertEqual(
            util.id_to_datetime_legacy('20200102030405'),
            datetime(2020, 1, 2, 3, 4, 5),
        )

        # accuracy below seconds
        self.assertEqual(
            util.id_to_datetime_legacy('20200102030405123'),
            datetime(2020, 1, 2, 3, 4, 5, 123000),
        )

        self.assertEqual(
            util.id_to_datetime_legacy('20200102030405123456'),
            datetime(2020, 1, 2, 3, 4, 5, 123456),
        )

        # accuracy below microseconds are dropped
        self.assertEqual(
            util.id_to_datetime_legacy('202001020304051234567'),
            datetime(2020, 1, 2, 3, 4, 5, 123456),
        )

        self.assertEqual(
            util.id_to_datetime_legacy('20200102030405123456789'),
            datetime(2020, 1, 2, 3, 4, 5, 123456),
        )

        # invalid format (not match regex)
        self.assertIsNone(util.id_to_datetime_legacy('20200102'))

        # invalid format (number out of range)
        self.assertIsNone(util.id_to_datetime_legacy('20200102036505'))

    @require_sep()
    def test_unify_pathsep_cs(self):
        self.assertEqual(
            util.unify_pathsep('a/b\\c/d'),
            'a/b\\c/d')

    @require_altsep()
    def test_unify_pathsep_ci(self):
        self.assertEqual(
            util.unify_pathsep('a/b\\c/d'),
            'a/b/c/d')

    def test_validate_filename(self):
        # basic
        self.assertEqual(
            util.validate_filename(''),
            '_')
        self.assertEqual(
            util.validate_filename('foo/bar'),
            'foo_bar')
        self.assertEqual(
            util.validate_filename('foo\\bar'),
            'foo_bar')

        self.assertEqual(
            util.validate_filename('abc\x0D\x0A\x09\x0Cxyz'),
            'abc xyz')

        self.assertEqual(
            util.validate_filename(''.join(chr(i) for i in range(0xA0))),
            "!_#$%&'()_+,-._0123456789_;_=__@ABCDEFGHIJKLMNOPQRSTUVWXYZ[_]^_`abcdefghijklmnopqrstuvwxyz{_}~")
        self.assertEqual(
            util.validate_filename('\u00A0中文𠀀'),
            '\u00A0中文𠀀')
        self.assertEqual(
            util.validate_filename('123%.dat'),
            '123%.dat')

        # Windows
        self.assertEqual(
            util.validate_filename(' '),
            '_')
        self.assertEqual(
            util.validate_filename('  '),
            '_')
        self.assertEqual(
            util.validate_filename('  wsb  '),
            'wsb')
        self.assertEqual(
            util.validate_filename('.'),
            '_')
        self.assertEqual(
            util.validate_filename('..'),
            '_')

        self.assertEqual(
            util.validate_filename('.wsb'),
            '_.wsb')
        self.assertEqual(
            util.validate_filename('..wsb'),
            '_..wsb')
        self.assertEqual(
            util.validate_filename('  ..wsb'),
            '_..wsb')
        self.assertEqual(
            util.validate_filename('foo.'),
            'foo')
        self.assertEqual(
            util.validate_filename('foo..  '),
            'foo')

        self.assertEqual(
            util.validate_filename('con'),
            'con_')
        self.assertEqual(
            util.validate_filename('prn'),
            'prn_')
        self.assertEqual(
            util.validate_filename('aux'),
            'aux_')
        self.assertEqual(
            util.validate_filename('com0'),
            'com0_')
        self.assertEqual(
            util.validate_filename('com9'),
            'com9_')
        self.assertEqual(
            util.validate_filename('lpt0'),
            'lpt0_')
        self.assertEqual(
            util.validate_filename('lpt9'),
            'lpt9_')
        self.assertEqual(
            util.validate_filename('con.txt'),
            'con_.txt')
        self.assertEqual(
            util.validate_filename('prn.txt'),
            'prn_.txt')
        self.assertEqual(
            util.validate_filename('aux.txt'),
            'aux_.txt')
        self.assertEqual(
            util.validate_filename('com0.txt'),
            'com0_.txt')
        self.assertEqual(
            util.validate_filename('com9.txt'),
            'com9_.txt')
        self.assertEqual(
            util.validate_filename('lpt0.txt'),
            'lpt0_.txt')
        self.assertEqual(
            util.validate_filename('lpt9.txt'),
            'lpt9_.txt')

        # force_ascii=True
        self.assertEqual(
            util.validate_filename(''.join(chr(i) for i in range(0xA0)), force_ascii=True),
            "!_#$%&'()_+,-._0123456789_;_=__@ABCDEFGHIJKLMNOPQRSTUVWXYZ[_]^_`abcdefghijklmnopqrstuvwxyz{_}~")
        self.assertEqual(
            util.validate_filename('\u00A0中文𠀀', force_ascii=True),
            '%C2%A0%E4%B8%AD%E6%96%87%F0%A0%80%80')
        self.assertEqual(
            util.validate_filename('123%.dat', force_ascii=True),
            '123%.dat')

    def test_crop(self):
        self.assertEqual(util.crop('dummy text', 10), 'dummy text')
        self.assertEqual(util.crop('dummy text', 9), 'dummy ...')
        self.assertEqual(util.crop('dummy text', 8), 'dummy...')
        self.assertEqual(util.crop('dummy text', 7), 'dumm...')
        self.assertEqual(util.crop('dummy text', 4), 'd...')
        self.assertEqual(util.crop('dummy text', 3), '...')
        self.assertEqual(util.crop('dummy text', 2), '...')
        self.assertEqual(util.crop('dummy text', 1), '...')
        self.assertEqual(util.crop('dummy text', 0), '...')

        self.assertEqual(util.crop('中文字串𠀀', 5), '中文字串𠀀')
        self.assertEqual(util.crop('中文字串𠀀', 4), '中...')

    def test_format_string(self):
        # %% => %
        self.assertEqual(util.format_string('format %%', {}), 'format %')

        # %% => %, overwriting mapping
        self.assertEqual(util.format_string('format %%', {'': '123'}), 'format %')

        # %key% => value
        self.assertEqual(util.format_string('format %key%', {'key': 'value'}), 'format value')
        self.assertEqual(util.format_string('format %foo_bar%', {'foo_bar': 'snake_value'}), 'format snake_value')

        # %unknown% => ''
        self.assertEqual(util.format_string('format %unknown%', {}), 'format ')

        # %broken key% => not formatted
        self.assertEqual(util.format_string('format %foo bar%', {}), 'format %foo bar%')
        self.assertEqual(util.format_string('format 15%, 30%.\nformat 45%.', {}), 'format 15%, 30%.\nformat 45%.')

    def test_compress_code(self):
        input = """\
function () {
  d.addEventListener('click', function (e) {
    e.preventDefault();
    console.log(e.target);
  }, true);
}
"""
        expected = """function () { d.addEventListener('click', function (e) { e.preventDefault(); console.log(e.target); }, true); } """
        self.assertEqual(util.compress_code(input), expected)

        input = """\
ul  >  li  :not([hidden])  {
  color:  red;
}
"""
        expected = """ul > li :not([hidden]) { color: red; } """
        self.assertEqual(util.compress_code(input), expected)

    def test_fix_codec(self):
        self.assertEqual(util.fix_codec('big5'), 'big5hkscs')
        self.assertEqual(util.fix_codec('BIG5'), 'big5hkscs')
        self.assertEqual(util.fix_codec('gb_2312-80'), 'GBK')
        self.assertEqual(util.fix_codec('UTF-8'), 'UTF-8')
        self.assertEqual(util.fix_codec('unicode-1-1-utf-8'), 'UTF-8')

    def test_sniff_bom(self):
        fh = io.BytesIO(b'\xef\xbb\xbf' + '中文'.encode('UTF-8'))
        self.assertEqual(util.sniff_bom(fh), 'UTF-8-SIG')
        self.assertEqual(fh.tell(), 3)

        fh = io.BytesIO(b'\xff\xfe' + '中文'.encode('UTF-16-LE'))
        self.assertEqual(util.sniff_bom(fh), 'UTF-16-LE')
        self.assertEqual(fh.tell(), 2)

        fh = io.BytesIO(b'\xfe\xff' + '中文'.encode('UTF-16-BE'))
        self.assertEqual(util.sniff_bom(fh), 'UTF-16-BE')
        self.assertEqual(fh.tell(), 2)

        fh = io.BytesIO(b'\xff\xfe\x00\x00' + '中文'.encode('UTF-32-LE'))
        self.assertEqual(util.sniff_bom(fh), 'UTF-32-LE')
        self.assertEqual(fh.tell(), 4)

        fh = io.BytesIO(b'\x00\x00\xfe\xff' + '中文'.encode('UTF-32-BE'))
        self.assertEqual(util.sniff_bom(fh), 'UTF-32-BE')
        self.assertEqual(fh.tell(), 4)

        fh = io.BytesIO('中文'.encode('UTF-8'))
        self.assertIsNone(util.sniff_bom(fh))
        self.assertEqual(fh.tell(), 0)

        fh = io.BytesIO('中文'.encode('Big5'))
        self.assertIsNone(util.sniff_bom(fh))
        self.assertEqual(fh.tell(), 0)

    def test_is_nullhost(self):
        self.assertTrue(util.is_nullhost('0.0.0.0'))
        self.assertFalse(util.is_nullhost('127.0.0.1'))
        self.assertFalse(util.is_localhost('192.168.0.1'))
        self.assertTrue(util.is_nullhost('::'))
        self.assertFalse(util.is_nullhost('::1'))
        self.assertTrue(util.is_nullhost('0::0'))
        self.assertTrue(util.is_nullhost('0000::0000'))
        self.assertTrue(util.is_nullhost('0000:0000::0000'))
        self.assertTrue(util.is_nullhost('0:0:0:0:0:0:0:0'))
        self.assertTrue(util.is_nullhost('0000:0000:0000:0000:0000:0000:0000:0000'))
        self.assertFalse(util.is_nullhost('wtf'))

    def test_is_localhost(self):
        self.assertFalse(util.is_localhost('0.0.0.0'))
        self.assertTrue(util.is_localhost('127.0.0.1'))
        self.assertFalse(util.is_localhost('192.168.0.1'))
        self.assertFalse(util.is_localhost('::'))
        self.assertTrue(util.is_localhost('::1'))
        self.assertTrue(util.is_localhost('0:0:0:0:0:0:0:1'))
        self.assertTrue(util.is_localhost('0000:0000:0000:0000:0000:0000:0000:0001'))
        self.assertFalse(util.is_localhost('wtf'))

    def test_get_relative_url(self):
        self.assertEqual(
            util.get_relative_url(
                os.path.join(tmpdir),
                os.path.join(tmpdir, 'tree', 'meta.js'),
                start_is_dir=False,
            ),
            '../',
        )

        self.assertEqual(
            util.get_relative_url(
                os.path.join(tmpdir, 'tree', 'icon'),
                os.path.join(tmpdir, 'data', '20200101000000000'),
            ),
            '../../tree/icon/',
        )

        self.assertEqual(
            util.get_relative_url(
                os.path.join(tmpdir, 'tree', 'icon', 'dummy.png'),
                os.path.join(tmpdir, 'data', '20200101000000000'),
                path_is_dir=False,
            ),
            '../../tree/icon/dummy.png',
        )

        self.assertEqual(
            util.get_relative_url(
                os.path.join(tmpdir, 'data', '20200102000000000'),
                os.path.join(tmpdir, 'data', '20200101000000000'),
            ),
            '../20200102000000000/',
        )

        self.assertEqual(
            util.get_relative_url(
                os.path.join(tmpdir, '中文#456.png'),
                os.path.join(tmpdir, '中文#123.png'),
                path_is_dir=False,
                start_is_dir=False,
            ),
            '%E4%B8%AD%E6%96%87%23456.png',
        )

    def test_checksum(self):
        # file
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'checksum.txt')
        with open(dst, 'w'):
            pass

        self.assertEqual(
            util.checksum(dst),
            'da39a3ee5e6b4b0d3255bfef95601890afd80709',
        )

        self.assertEqual(
            util.checksum(dst, method='sha256'),
            'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        )

        # file-like
        self.assertEqual(
            util.checksum(io.BytesIO(b''), method='sha256'),
            'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        )

        self.assertEqual(
            util.checksum(io.BytesIO(b'ABC'), method='sha256'),
            'b5d4045c3f466fa91fe2cc6abe79232a1a57cdf104f7a26e716e0a1e2789df78',
        )

    def test_format_filesize(self):
        self.assertEqual(util.format_filesize(0), '0 B')
        self.assertEqual(util.format_filesize(3), '3 B')
        self.assertEqual(util.format_filesize(1000), '1000 B')
        self.assertEqual(util.format_filesize(1024), '1.0 KB')
        self.assertEqual(util.format_filesize(1080), '1.1 KB')
        self.assertEqual(util.format_filesize(10000), '9.8 KB')
        self.assertEqual(util.format_filesize(10240), '10 KB')
        self.assertEqual(util.format_filesize(20480), '20 KB')
        self.assertEqual(util.format_filesize(1048576), '1.0 MB')
        self.assertEqual(util.format_filesize(2621440), '2.5 MB')
        self.assertEqual(util.format_filesize(10485760), '10 MB')
        self.assertEqual(util.format_filesize(1073741824), '1.0 GB')
        self.assertEqual(util.format_filesize(10737418240), '10 GB')
        self.assertEqual(util.format_filesize(1e14), '91 TB')
        self.assertEqual(util.format_filesize(1e28), '8272 YB')

        self.assertEqual(util.format_filesize(0, si=True), '0 B')
        self.assertEqual(util.format_filesize(3, si=True), '3 B')
        self.assertEqual(util.format_filesize(1000, si=True), '1.0 kB')
        self.assertEqual(util.format_filesize(1024, si=True), '1.0 kB')
        self.assertEqual(util.format_filesize(1080, si=True), '1.1 kB')
        self.assertEqual(util.format_filesize(10000, si=True), '10 kB')
        self.assertEqual(util.format_filesize(10240, si=True), '10 kB')
        self.assertEqual(util.format_filesize(20480, si=True), '20 kB')
        self.assertEqual(util.format_filesize(1048576, si=True), '1.0 MB')
        self.assertEqual(util.format_filesize(2621440, si=True), '2.6 MB')
        self.assertEqual(util.format_filesize(10485760, si=True), '10 MB')
        self.assertEqual(util.format_filesize(1073741824, si=True), '1.1 GB')
        self.assertEqual(util.format_filesize(10737418240, si=True), '11 GB')
        self.assertEqual(util.format_filesize(1e14, si=True), '100 TB')
        self.assertEqual(util.format_filesize(1e28, si=True), '10000 YB')

        # space
        self.assertEqual(util.format_filesize(0, space=''), '0B')
        self.assertEqual(util.format_filesize(1048576, space='\xA0'), '1.0\xA0MB')

    def test_is_compressible(self):
        # None
        self.assertFalse(util.is_compressible(None))

        # text/*
        self.assertTrue(util.is_compressible('text/plain'))
        self.assertTrue(util.is_compressible('text/html'))
        self.assertTrue(util.is_compressible('text/css'))
        self.assertTrue(util.is_compressible('text/javascript'))
        self.assertTrue(util.is_compressible('text/markdown'))

        # binary
        self.assertFalse(util.is_compressible('image/jpeg'))
        self.assertFalse(util.is_compressible('application/octet-stream'))
        self.assertFalse(util.is_compressible('application/ogg'))
        self.assertFalse(util.is_compressible('application/pdf'))
        self.assertFalse(util.is_compressible('application/zip'))
        self.assertFalse(util.is_compressible('application/x-rar-compressed'))
        self.assertFalse(util.is_compressible('application/x-gzip'))
        self.assertFalse(util.is_compressible('application/html+zip'))
        self.assertFalse(util.is_compressible('application/x-maff'))

        # text-like application/*
        self.assertTrue(util.is_compressible('application/javascript'))
        self.assertTrue(util.is_compressible('application/ecmascript'))
        self.assertTrue(util.is_compressible('application/x-ecmascript'))
        self.assertTrue(util.is_compressible('application/x-javascript'))
        self.assertTrue(util.is_compressible('application/json'))
        self.assertTrue(util.is_compressible('application/xml'))

        # text-like suffixes
        self.assertTrue(util.is_compressible('application/xhtml+xml'))
        self.assertTrue(util.is_compressible('application/ld+json'))

    def test_mime_is_html(self):
        self.assertTrue(util.mime_is_html('text/html'))
        self.assertTrue(util.mime_is_html('application/xhtml+xml'))
        self.assertFalse(util.mime_is_html('application/html+zip'))
        self.assertFalse(util.mime_is_html('application/x-maff'))
        self.assertFalse(util.mime_is_html('text/plain'))
        self.assertFalse(util.mime_is_html('text/markdown'))
        self.assertFalse(util.mime_is_html('text/xml'))
        self.assertFalse(util.mime_is_html('image/svg+xml'))
        self.assertFalse(util.mime_is_html('application/octet-stream'))

    def test_mime_is_xhtml(self):
        self.assertFalse(util.mime_is_xhtml('text/html'))
        self.assertTrue(util.mime_is_xhtml('application/xhtml+xml'))
        self.assertFalse(util.mime_is_xhtml('application/html+zip'))
        self.assertFalse(util.mime_is_xhtml('application/x-maff'))
        self.assertFalse(util.mime_is_xhtml('text/plain'))
        self.assertFalse(util.mime_is_xhtml('text/markdown'))
        self.assertFalse(util.mime_is_xhtml('text/xml'))
        self.assertFalse(util.mime_is_xhtml('image/svg+xml'))
        self.assertFalse(util.mime_is_xhtml('application/octet-stream'))

    def test_mime_is_svg(self):
        self.assertFalse(util.mime_is_svg('text/html'))
        self.assertFalse(util.mime_is_svg('application/xhtml+xml'))
        self.assertFalse(util.mime_is_svg('application/html+zip'))
        self.assertFalse(util.mime_is_svg('application/x-maff'))
        self.assertFalse(util.mime_is_svg('text/plain'))
        self.assertFalse(util.mime_is_svg('text/markdown'))
        self.assertFalse(util.mime_is_svg('text/xml'))
        self.assertTrue(util.mime_is_svg('image/svg+xml'))
        self.assertFalse(util.mime_is_svg('application/octet-stream'))

    def test_mime_is_archive(self):
        self.assertFalse(util.mime_is_archive('text/html'))
        self.assertFalse(util.mime_is_archive('application/xhtml+xml'))
        self.assertTrue(util.mime_is_archive('application/html+zip'))
        self.assertTrue(util.mime_is_archive('application/x-maff'))
        self.assertFalse(util.mime_is_archive('text/plain'))
        self.assertFalse(util.mime_is_archive('text/markdown'))
        self.assertFalse(util.mime_is_archive('text/xml'))
        self.assertFalse(util.mime_is_archive('image/svg+xml'))
        self.assertFalse(util.mime_is_archive('application/octet-stream'))

    def test_mime_is_htz(self):
        self.assertFalse(util.mime_is_htz('text/html'))
        self.assertFalse(util.mime_is_htz('application/xhtml+xml'))
        self.assertTrue(util.mime_is_htz('application/html+zip'))
        self.assertFalse(util.mime_is_htz('application/x-maff'))
        self.assertFalse(util.mime_is_htz('text/plain'))
        self.assertFalse(util.mime_is_htz('text/markdown'))
        self.assertFalse(util.mime_is_htz('text/xml'))
        self.assertFalse(util.mime_is_htz('image/svg+xml'))
        self.assertFalse(util.mime_is_htz('application/octet-stream'))

    def test_mime_is_maff(self):
        self.assertFalse(util.mime_is_maff('text/html'))
        self.assertFalse(util.mime_is_maff('application/xhtml+xml'))
        self.assertFalse(util.mime_is_maff('application/html+zip'))
        self.assertTrue(util.mime_is_maff('application/x-maff'))
        self.assertFalse(util.mime_is_maff('text/plain'))
        self.assertFalse(util.mime_is_maff('text/markdown'))
        self.assertFalse(util.mime_is_maff('text/xml'))
        self.assertFalse(util.mime_is_maff('image/svg+xml'))
        self.assertFalse(util.mime_is_maff('application/octet-stream'))

    def test_mime_is_markdown(self):
        self.assertFalse(util.mime_is_markdown('text/html'))
        self.assertFalse(util.mime_is_markdown('application/xhtml+xml'))
        self.assertFalse(util.mime_is_markdown('application/html+zip'))
        self.assertFalse(util.mime_is_markdown('application/x-maff'))
        self.assertFalse(util.mime_is_markdown('text/plain'))
        self.assertTrue(util.mime_is_markdown('text/markdown'))
        self.assertFalse(util.mime_is_markdown('text/xml'))
        self.assertFalse(util.mime_is_markdown('image/svg+xml'))
        self.assertFalse(util.mime_is_markdown('application/octet-stream'))

    def test_mime_is_wsba(self):
        self.assertFalse(util.mime_is_wsba('text/html'))
        self.assertFalse(util.mime_is_wsba('application/xhtml+xml'))
        self.assertFalse(util.mime_is_wsba('application/html+zip'))
        self.assertFalse(util.mime_is_wsba('application/x-maff'))
        self.assertFalse(util.mime_is_wsba('text/plain'))
        self.assertFalse(util.mime_is_wsba('text/markdown'))
        self.assertTrue(util.mime_is_wsba('application/wsba+zip'))
        self.assertFalse(util.mime_is_wsba('text/xml'))
        self.assertFalse(util.mime_is_wsba('image/svg+xml'))
        self.assertFalse(util.mime_is_wsba('application/octet-stream'))

    def test_is_html(self):
        self.assertTrue(util.is_html('index.html'))
        self.assertTrue(util.is_html('index.xhtml'))
        self.assertFalse(util.is_html('20200101000000000.htz'))
        self.assertFalse(util.is_html('20200101000000000.maff'))
        self.assertFalse(util.is_html('20200101000000000/index.md'))
        self.assertFalse(util.is_html('20200101000000000/test.txt'))
        self.assertFalse(util.is_html('20200101000000000/test.xml'))
        self.assertFalse(util.is_html('20200101000000000/test.svg'))
        self.assertFalse(util.is_html('20200101000000000/whatever'))

    def test_is_xhtml(self):
        self.assertFalse(util.is_xhtml('index.html'))
        self.assertTrue(util.is_xhtml('index.xhtml'))
        self.assertFalse(util.is_xhtml('20200101000000000.htz'))
        self.assertFalse(util.is_xhtml('20200101000000000.maff'))
        self.assertFalse(util.is_xhtml('20200101000000000/index.md'))
        self.assertFalse(util.is_xhtml('20200101000000000/test.txt'))
        self.assertFalse(util.is_xhtml('20200101000000000/test.xml'))
        self.assertFalse(util.is_xhtml('20200101000000000/test.svg'))
        self.assertFalse(util.is_xhtml('20200101000000000/whatever'))

    def test_is_svg(self):
        self.assertFalse(util.is_svg('index.html'))
        self.assertFalse(util.is_svg('index.xhtml'))
        self.assertFalse(util.is_svg('20200101000000000.htz'))
        self.assertFalse(util.is_svg('20200101000000000.maff'))
        self.assertFalse(util.is_svg('20200101000000000/index.md'))
        self.assertFalse(util.is_svg('20200101000000000/test.txt'))
        self.assertFalse(util.is_svg('20200101000000000/test.xml'))
        self.assertTrue(util.is_svg('20200101000000000/test.svg'))
        self.assertFalse(util.is_svg('20200101000000000/whatever'))

    def test_is_archive(self):
        self.assertFalse(util.is_archive('index.html'))
        self.assertFalse(util.is_archive('index.xhtml'))
        self.assertTrue(util.is_archive('20200101000000000.htz'))
        self.assertTrue(util.is_archive('20200101000000000.maff'))
        self.assertFalse(util.is_archive('20200101000000000/index.md'))
        self.assertFalse(util.is_archive('20200101000000000/test.txt'))
        self.assertFalse(util.is_archive('20200101000000000/test.xml'))
        self.assertFalse(util.is_archive('20200101000000000/test.svg'))
        self.assertFalse(util.is_archive('20200101000000000/whatever'))

    def test_is_htz(self):
        self.assertFalse(util.is_htz('index.html'))
        self.assertFalse(util.is_htz('index.xhtml'))
        self.assertTrue(util.is_htz('20200101000000000.htz'))
        self.assertFalse(util.is_htz('20200101000000000.maff'))
        self.assertFalse(util.is_htz('20200101000000000/index.md'))
        self.assertFalse(util.is_htz('20200101000000000/test.txt'))
        self.assertFalse(util.is_htz('20200101000000000/test.xml'))
        self.assertFalse(util.is_htz('20200101000000000/test.svg'))
        self.assertFalse(util.is_htz('20200101000000000/whatever'))

    def test_is_maff(self):
        self.assertFalse(util.is_maff('index.html'))
        self.assertFalse(util.is_maff('index.xhtml'))
        self.assertFalse(util.is_maff('20200101000000000.htz'))
        self.assertTrue(util.is_maff('20200101000000000.maff'))
        self.assertFalse(util.is_maff('20200101000000000/index.md'))
        self.assertFalse(util.is_maff('20200101000000000/test.txt'))
        self.assertFalse(util.is_maff('20200101000000000/test.xml'))
        self.assertFalse(util.is_maff('20200101000000000/test.svg'))
        self.assertFalse(util.is_maff('20200101000000000/whatever'))

    def test_is_markdown(self):
        self.assertFalse(util.is_markdown('index.html'))
        self.assertFalse(util.is_markdown('index.xhtml'))
        self.assertFalse(util.is_markdown('20200101000000000.htz'))
        self.assertFalse(util.is_markdown('20200101000000000.maff'))
        self.assertTrue(util.is_markdown('20200101000000000/index.md'))
        self.assertFalse(util.is_markdown('20200101000000000/test.txt'))
        self.assertFalse(util.is_markdown('20200101000000000/test.xml'))
        self.assertFalse(util.is_markdown('20200101000000000/test.svg'))
        self.assertFalse(util.is_markdown('20200101000000000/whatever'))

    def test_is_wsba(self):
        self.assertFalse(util.is_wsba('index.html'))
        self.assertFalse(util.is_wsba('index.xhtml'))
        self.assertFalse(util.is_wsba('20200101000000000.htz'))
        self.assertFalse(util.is_wsba('20200101000000000.maff'))
        self.assertFalse(util.is_wsba('20200101000000000/index.md'))
        self.assertTrue(util.is_wsba('20200101000000000-example.wsba'))
        self.assertFalse(util.is_wsba('20200101000000000/test.txt'))
        self.assertFalse(util.is_wsba('20200101000000000/test.xml'))
        self.assertFalse(util.is_wsba('20200101000000000/test.svg'))
        self.assertFalse(util.is_wsba('20200101000000000/whatever'))

    def test_parse_content_type(self):
        self.assertEqual(
            util.parse_content_type('text/html; charset=UTF-8'),
            ('text/html', {'charset': 'UTF-8'}),
        )
        self.assertEqual(
            util.parse_content_type('text/html; charset="UTF-8"'),
            ('text/html', {'charset': 'UTF-8'}),
        )
        self.assertEqual(
            util.parse_content_type('TEXT/HTML; CHARSET="UTF-8"'),
            ('text/html', {'charset': 'UTF-8'}),
        )
        self.assertEqual(
            util.parse_content_type(None),
            (None, {}),
        )
        self.assertEqual(
            util.parse_content_type(''),
            (None, {}),
        )

    def test_parse_datauri(self):
        self.assertEqual(
            util.parse_datauri('data:text/plain;base64,QUJDMTIz5Lit5paH'),
            (b'ABC123\xe4\xb8\xad\xe6\x96\x87', 'text/plain', {}),
        )
        self.assertEqual(
            util.parse_datauri('data:text/plain,ABC123%E4%B8%AD%E6%96%87'),
            (b'ABC123\xe4\xb8\xad\xe6\x96\x87', 'text/plain', {}),
        )
        self.assertEqual(
            util.parse_datauri('data:text/plain;filename=ABC%E6%AA%94.md;base64,QUJDMTIz5Lit5paH'),
            (b'ABC123\xe4\xb8\xad\xe6\x96\x87', 'text/plain', {'filename': 'ABC%E6%AA%94.md'}),
        )
        self.assertEqual(
            util.parse_datauri('data:text/plain;filename=ABC%E6%AA%94.md,ABC123%E4%B8%AD%E6%96%87'),
            (b'ABC123\xe4\xb8\xad\xe6\x96\x87', 'text/plain', {'filename': 'ABC%E6%AA%94.md'}),
        )
        self.assertEqual(
            util.parse_datauri('data:text/plain;charset=big5;filename=ABC%E6%AA%94.md;base64,QUJDMTIz5Lit5paH'),
            (b'ABC123\xe4\xb8\xad\xe6\x96\x87', 'text/plain', {'filename': 'ABC%E6%AA%94.md', 'charset': 'big5'}),
        )
        self.assertEqual(
            util.parse_datauri('data:text/plain;charset=big5;filename=ABC%E6%AA%94.md,ABC123%E4%B8%AD%E6%96%87'),
            (b'ABC123\xe4\xb8\xad\xe6\x96\x87', 'text/plain', {'filename': 'ABC%E6%AA%94.md', 'charset': 'big5'}),
        )

        # missing MIME => empty MIME
        self.assertEqual(
            util.parse_datauri('data:,ABC'),
            (b'ABC', '', {}),
        )

        # non-ASCII data => treat as UTF-8
        self.assertEqual(
            util.parse_datauri('data:text/plain,ABC中文'),
            (b'ABC\xe4\xb8\xad\xe6\x96\x87', 'text/plain', {}),
        )

        # incomplete => raise DataUriMalformedError
        with self.assertRaises(util.DataUriMalformedError):
            util.parse_datauri('data:')
        with self.assertRaises(util.DataUriMalformedError):
            util.parse_datauri('data:text/html')
        with self.assertRaises(util.DataUriMalformedError):
            util.parse_datauri('data:text/html;base64')

        # malformed base64 => raise DataUriMalformedError
        with self.assertRaises(util.DataUriMalformedError):
            util.parse_datauri('data:text/plain;base64,ABC')

    def test_get_html_charset(self):
        root = os.path.join(test_root, 'get_html_charset')
        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset1.html')), 'UTF-8')
        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset1.html'), default='Big5'), 'big5hkscs')

        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset2.html')), 'UTF-8')
        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset3.html')), 'big5hkscs')
        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset4.html')), 'UTF-8')
        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset5.html')), 'big5hkscs')

        self.assertIsNone(util.get_html_charset(os.path.join(root, 'charset6.html')))
        self.assertIsNone(util.get_html_charset(os.path.join(root, 'charset6.html'), none_from_bom=True))
        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset6.html'), none_from_bom=False), 'UTF-16-BE')

        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset7.html')), 'UTF-8')
        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset7.html'), quickly=True), 'UTF-8')
        self.assertEqual(util.get_html_charset(os.path.join(root, 'charset7.html'), quickly=False), 'big5hkscs')

    def test_load_html_tree(self):
        # HTML5
        # @FIXME: &nbsp; becomes unescaped \u00A0
        # @FIXME: < & > becomes escaped &lt; &amp; &gt;
        html = """<!DOCTYPE html>
<html>
<head>
<title>中文</title>
<meta charset="UTF-8">
<style>
<!--/*--><![CDATA[/*><!--*/
body::after { content: "<my> <" "/style> & godness"; }
/*]]>*/-->
</style>
<script>
<!--//--><![CDATA[//><!--
console.log('test <my> <' + '/script> & tag');
//--><!]]>
</script>
</head>
<body>
foo&nbsp;&nbsp;&nbsp;中文<br>
&quot;123&quot; &lt; &amp; &gt; 456 (escaped)<br>
"123" < & > 456 (unescaped)<br>
<input type="checkbox" checked>
</body>
</html>
"""
        fh = io.BytesIO(html.encode('UTF-8'))
        tree = util.load_html_tree(fh)
        html1 = lxml.html.tostring(tree, encoding='unicode', method='html')
        self.assertEqual(html1, """<!DOCTYPE html>
<html>
<head>
<title>中文</title>
<meta charset="UTF-8">
<style>
<!--/*--><![CDATA[/*><!--*/
body::after { content: "<my> <" "/style> & godness"; }
/*]]>*/-->
</style>
<script>
<!--//--><![CDATA[//><!--
console.log('test <my> <' + '/script> & tag');
//--><!]]>
</script>
</head>
<body>
foo   中文<br>
"123" &lt; &amp; &gt; 456 (escaped)<br>
"123" &lt; &amp; &gt; 456 (unescaped)<br>
<input type="checkbox" checked>
</body>
</html>""")

        # XHTML1.1
        # @FIXME: bad order for doctype and XML declaration
        # @FIXME: bad format for XML declaration
        # @FIXME: &nbsp; becomes unescaped \u00A0
        # @FIXME: < & > etc. escaped in <style> and <script>
        html = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>中文</title>
<meta charset="UTF-8" />
<style>
<!--/*--><![CDATA[/*><!--*/
body::after { content: "<my> <" "/style> & godness"; }
/*]]>*/-->
</style>
<script type="text/javascript">
<!--//--><![CDATA[//><!--
console.log('test <my> <' + '/script> & tag');
//--><!]]>
</script>
</head>
<body>
foo&nbsp;&nbsp;&nbsp;中文<br/>
&quot;123&quot; &lt; &amp; &gt; 456 (escaped)<br/>
<input type="checkbox" checked="checked" />
</body>
</html>
"""
        fh = io.BytesIO(html.encode('UTF-8'))
        tree = util.load_html_tree(fh)
        html1 = lxml.html.tostring(tree, encoding='unicode', method='xml')
        self.assertEqual(html1, """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<?xml version="1.0" encoding="UTF-8"??><html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>中文</title>
<meta charset="UTF-8"/>
<style>
&lt;!--/*--&gt;&lt;![CDATA[/*&gt;&lt;!--*/
body::after { content: "&lt;my&gt; &lt;" "/style&gt; &amp; godness"; }
/*]]&gt;*/--&gt;
</style>
<script type="text/javascript">
&lt;!--//--&gt;&lt;![CDATA[//&gt;&lt;!--
console.log('test &lt;my&gt; &lt;' + '/script&gt; &amp; tag');
//--&gt;&lt;!]]&gt;
</script>
</head>
<body>
foo   中文<br/>
"123" &lt; &amp; &gt; 456 (escaped)<br/>
<input type="checkbox" checked="checked"/>
</body>
</html>""")

    def test_parse_meta_refresh_content(self):
        # check time parsing
        self.assertEqual(
            util.parse_meta_refresh_content('3'),
            (3, '', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3.5'),
            (3, '', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('0'),
            (0, '', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content(' 3 '),
            (3, '', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content(' 3 ;'),
            (3, '', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('-1'),
            (None, None, None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('abc'),
            (None, None, None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content(''),
            (None, None, None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content(';'),
            (None, None, None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content(';url=target.html'),
            (None, None, None),
        )

        # check target parsing
        self.assertEqual(
            util.parse_meta_refresh_content('3;target.html'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3,target.html'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3 target.html'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=target.html'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3,url=target.html'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3 url=target.html'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3 ; url = target.html '),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url\u3000=\u3000target.html'),
            (3, 'url\u3000=\u3000target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=target.html .com'),
            (3, 'target.html .com', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url="target.html" .com'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content("3;url='target.html' .com"),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url="target.html'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url target.html'),
            (3, 'url target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;u=target.html'),
            (3, 'u=target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=中文.html'),
            (3, '中文.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=%E4%B8%AD%E6%96%87.html'),
            (3, '%E4%B8%AD%E6%96%87.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=data:text/plain;charset=utf-8,mycontent'),
            (3, 'data:text/plain;charset=utf-8,mycontent', None),
        )

        # check context parsing
        self.assertEqual(
            util.parse_meta_refresh_content('3;url=target.html'),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=target.html', None),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=target.html', []),
            (3, 'target.html', None),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=target.html', ['noscript']),
            (3, 'target.html', ['noscript']),
        )

        self.assertEqual(
            util.parse_meta_refresh_content('3;url=target.html', ['noscript', 'noframes']),
            (3, 'target.html', ['noscript', 'noframes']),
        )

        c = ['noscript']
        self.assertIsNot(
            util.parse_meta_refresh_content('3;url=target.html', c).context,
            c,
        )

    def test_iter_meta_refresh(self):
        root = os.path.join(test_root, 'iter_meta_refresh')
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'refresh1.html'))),
            [
                (15, 'target.html', None),
                (0, '', None),
                (0, 'target.html', None),
                (0, 'target2.html', None),
            ],
        )
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'refresh2.html'))),
            [
                (15, 'target.html', None),
                (None, None, None),
                (None, None, None),
            ],
        )
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'refresh3.html'))),
            [
                (0, 'target-title.html', ['title']),
                (0, 'target-iframe.html', ['iframe']),
                (0, 'target-noframes.html', ['noframes']),
                (0, 'target-noscript.html', ['noscript']),
                (0, 'target-noembed.html', ['noembed']),
                (0, 'target-textarea.html', ['textarea']),
                (0, 'target-template.html', ['template']),
                (0, 'target-xmp.html', ['xmp']),
            ],
        )
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'refresh4.html'))),
            [(0, 'target.html', ['noscript', 'noframes'])],
        )
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'refresh5.html'))),
            [
                (0, '中文.html', None),
                (0, '%E4%B8%AD%E6%96%87.html', None),
            ],
        )
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'refresh6.html'))),
            [
                (0, '中文.html', None),
                (0, '%E4%B8%AD%E6%96%87.html', None),
            ],
        )
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'refresh7.html'))),
            [
                (0, b'\xE4\xB8\xAD\xE6\x96\x87.html'.decode('windows-1252'), None),
                (0, '%E4%B8%AD%E6%96%87.html', None),
            ],
        )
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'refresh7.html'), encoding='UTF-8')),
            [
                (0, '中文.html', None),
                (0, '%E4%B8%AD%E6%96%87.html', None),
            ],
        )
        self.assertEqual(
            list(util.iter_meta_refresh(os.path.join(root, 'nonexist.html'))),
            [],
        )

        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('refresh.html', '<meta http-equiv="refresh" content="0;url=target.html">')

        with zipfile.ZipFile(zfile, 'r') as zh, zh.open('refresh.html') as fh:
            self.assertEqual(
                list(util.iter_meta_refresh(fh)),
                [(0, 'target.html', None)],
            )

    def test_get_meta_refresh(self):
        root = os.path.join(test_root, 'get_meta_refresh')

        self.assertEqual(
            util.get_meta_refresh(os.path.join(root, 'refresh1.html')),
            (0, 'target.html', None),
        )

        self.assertEqual(
            util.get_meta_refresh(os.path.join(root, 'refresh2.html')),
            (None, None, None),
        )

        self.assertEqual(
            util.get_meta_refresh(os.path.join(root, 'refresh3.html')),
            (0, 'target1.html', None),
        )

        self.assertEqual(
            util.get_meta_refresh(os.path.join(root, 'refresh4.html')),
            (None, None, None),
        )

        self.assertEqual(
            util.get_meta_refresh(os.path.join(root, 'refresh5.html')),
            (None, None, None),
        )

        self.assertEqual(
            util.get_meta_refresh(os.path.join(root, 'refresh6.html')),
            (0, 'target.html', None),
        )

        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('refresh.html', '<meta http-equiv="refresh" content="0;url=target.html">')

        with zipfile.ZipFile(zfile, 'r') as zh, zh.open('refresh.html') as fh:
            self.assertEqual(
                util.get_meta_refresh(fh),
                (0, 'target.html', None),
            )

    def test_get_meta_refreshed_file(self):
        root = os.path.join(test_root, 'get_meta_refreshed_file')

        self.assertEqual(
            util.get_meta_refreshed_file(os.path.join(root, 'case01', 'index.html')),
            os.path.join(root, 'case01', 'refresh.html'),
        )

        self.assertEqual(
            util.get_meta_refreshed_file(os.path.join(root, 'case02', 'index.html')),
            os.path.join(root, 'test.html'),
        )

        self.assertEqual(
            util.get_meta_refreshed_file(os.path.join(root, 'case03', 'index.html')),
            os.path.join(root, 'case03', 'refresh2.html'),
        )

        self.assertEqual(
            util.get_meta_refreshed_file(os.path.join(root, 'case04', 'index.html')),
            os.path.join(root, 'case04', 'refresh1.html'),
        )

        self.assertIsNone(
            util.get_meta_refreshed_file(os.path.join(root, 'case05', 'index.html')),
        )

        with self.assertRaises(util.MetaRefreshCircularError):
            util.get_meta_refreshed_file(os.path.join(root, 'case06', 'index.html'))

        with self.assertRaises(util.MetaRefreshCircularError):
            util.get_meta_refreshed_file(os.path.join(root, 'case07', 'index.html'))

        with self.assertRaises(util.MetaRefreshCircularError):
            util.get_meta_refreshed_file(os.path.join(root, 'case08', 'index.html'))

    def test_parse_maff_index_rdf(self):
        maff_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'tempfile.maff')
        with zipfile.ZipFile(maff_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('19870101/index.rdf', DUMMY_ZIP_DT), """<?xml version="1.0"?>
<RDF:RDF xmlns:MAF="http://maf.mozdev.org/metadata/rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:root">
    <MAF:originalurl RDF:resource="http://example.com/"/>
    <MAF:title RDF:resource="Example MAFF"/>
    <MAF:archivetime RDF:resource="Mon, 25 Dec 2017 17:27:46 GMT"/>
    <MAF:indexfilename RDF:resource="index.html"/>
    <MAF:charset RDF:resource="UTF-8"/>
  </RDF:Description>
</RDF:RDF>""")

        with zipfile.ZipFile(maff_filename, 'r') as zh:
            with zh.open('19870101/index.rdf', 'r') as rdf:
                self.assertEqual(
                    util.parse_maff_index_rdf(rdf),
                    ('Example MAFF', 'http://example.com/', 'Mon, 25 Dec 2017 17:27:46 GMT', 'index.html', 'UTF-8'),
                )

    def test_get_maff_pages(self):
        maff_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'tempfile.maff')
        with zipfile.ZipFile(maff_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('webpage1/index.rdf', DUMMY_ZIP_DT), """<?xml version="1.0"?>
<RDF:RDF xmlns:MAF="http://maf.mozdev.org/metadata/rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <RDF:Description RDF:about="urn:root">
    <MAF:originalurl RDF:resource="http://example.com/"/>
    <MAF:title RDF:resource="Example MAFF"/>
    <MAF:archivetime RDF:resource="Mon, 25 Dec 2017 17:27:46 GMT"/>
    <MAF:indexfilename RDF:resource="index.html"/>
    <MAF:charset RDF:resource="UTF-8"/>
  </RDF:Description>
</RDF:RDF>""")
            zh.writestr(zipfile.ZipInfo('webpage2/index.html', DUMMY_ZIP_DT), '')
            zh.writestr(zipfile.ZipInfo('webpage3/index.svg', DUMMY_ZIP_DT), '')

        self.assertEqual(util.get_maff_pages(maff_filename), [
            ('Example MAFF', 'http://example.com/', 'Mon, 25 Dec 2017 17:27:46 GMT', 'webpage1/index.html', 'UTF-8'),
            (None, None, None, 'webpage2/index.html', None),
            (None, None, None, 'webpage3/index.svg', None),
        ])

        with zipfile.ZipFile(maff_filename, 'r') as zh:
            self.assertEqual(util.get_maff_pages(zh), [
                ('Example MAFF', 'http://example.com/', 'Mon, 25 Dec 2017 17:27:46 GMT', 'webpage1/index.html', 'UTF-8'),
                (None, None, None, 'webpage2/index.html', None),
                (None, None, None, 'webpage3/index.svg', None),
            ])

    @mock.patch('sys.stderr', io.StringIO())
    def test_encrypt(self):
        self.assertEqual(
            util.encrypt('1234', 'salt', 'plain'),
            '1234salt',
        )
        self.assertEqual(
            util.encrypt('1234', 'salt', 'md5'),
            '1fadcf6eb4345975be993f237c51d426',
        )
        self.assertEqual(
            util.encrypt('1234', 'salt', 'sha1'),
            '40c95464b7eacddb5572af5468ffb1cdb5b13f35',
        )
        self.assertEqual(
            util.encrypt('1234', 'salt', 'sha256'),
            '4b3bed8af7b7612e8c1e25f63ba24496f5b16b2df44efb2db7ce3cb24b7e96f7',
        )
        self.assertEqual(
            util.encrypt('1234', 'salt', 'unknown'),
            '1234salt',
        )


if __name__ == '__main__':
    unittest.main()
