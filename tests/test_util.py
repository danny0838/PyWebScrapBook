import collections
import io
import os
import platform
import subprocess
import tempfile
import time
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from unittest import mock

import lxml.html

from webscrapbook import util
from webscrapbook.util import frozendict, zip_tuple_timestamp

from . import ROOT_DIR, SYMLINK_SUPPORTED, TEMP_DIR

test_root = os.path.join(ROOT_DIR, 'test_util')


def setUpModule():
    """Set up a temp directory for testing."""
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='util-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)


def tearDownModule():
    """Cleanup the temp directory."""
    _tmpdir.cleanup()


class TestUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def test_frozendict(self):
        dict_ = {'a': 1, 'b': 2, 'c': 3}
        frozendict_ = frozendict(dict_)

        self.assertTrue(isinstance(frozendict_, collections.abc.Hashable))
        self.assertTrue(isinstance(frozendict_, collections.abc.Mapping))
        self.assertFalse(isinstance(frozendict_, collections.abc.MutableMapping))

        self.assertEqual(eval(repr(frozendict_)), frozendict_)
        self.assertRegex(repr(frozendict_), r'^frozendict\([^)]*\)$')

        self.assertTrue(frozendict_ == dict_)
        self.assertIn('a', frozendict_)
        self.assertEqual(set(frozendict_), {'a', 'b', 'c'})
        self.assertEqual(list(reversed(frozendict_)), list(frozendict_)[::-1])

        with self.assertRaises(TypeError):
            frozendict_['a'] = 2
        with self.assertRaises(TypeError):
            del frozendict_['a']

        frozendict2 = frozendict_.copy()
        self.assertEqual(frozendict_, frozendict2)
        self.assertIsNot(frozendict_, frozendict2)

    def test_make_hashable(self):
        self.assertEqual(
            type(util.make_hashable({1, 2, 3})),
            frozenset
        )

        self.assertEqual(
            type(util.make_hashable(['foo', 'bar', 'baz'])),
            tuple
        )

        self.assertEqual(
            type(util.make_hashable({'a': 123, 'b': 456, 'c': 789})),
            frozendict
        )

        self.assertEqual(
            set(util.make_hashable([{'a': 123, 'b': 456}, [1, 2, 3]])),
            {(1, 2, 3), frozendict({'a': 123, 'b': 456})}
        )

    def test_import_module_file(self):
        mod = util.import_module_file('webscrapbook._test_import_module_file', os.path.join(test_root, 'import_module_file.py'))
        self.assertEqual(mod.__name__, 'webscrapbook._test_import_module_file')
        self.assertEqual(mod.test_key, 'test_value')

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

        # create an ID from corresponding local time if datetime is another timezone
        self.assertEqual(
            util.datetime_to_id_legacy(datetime(2020, 1, 2, 3, 4, 5, 67000, tzinfo=timezone.utc)),
            util.datetime_to_id_legacy(datetime(2020, 1, 2, 3, 4, 5, 67000) + datetime.now().astimezone().utcoffset())
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

    def test_validate_filename(self):
        self.assertEqual(
            util.validate_filename(''),
            '_')
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
            util.validate_filename('foo.'),
            'foo')
        self.assertEqual(
            util.validate_filename('  wsb  '),
            'wsb')
        self.assertEqual(
            util.validate_filename('foo\\bar'),
            'foo_bar')
        self.assertEqual(
            util.validate_filename(''.join(chr(i) for i in range(0xA0))),
            "!_#$%&'()_+,-._0123456789_;(=)_@ABCDEFGHIJKLMNOPQRSTUVWXYZ[_]^_`abcdefghijklmnopqrstuvwxyz{_}-")
        self.assertEqual(
            util.validate_filename('\u00A0中文𠀀'),
            '\u00A0中文𠀀')
        self.assertEqual(
            util.validate_filename(''.join(chr(i) for i in range(0xA0)), force_ascii=True),
            "!_#$%25&'()_+,-._0123456789_;(=)_@ABCDEFGHIJKLMNOPQRSTUVWXYZ[_]^_`abcdefghijklmnopqrstuvwxyz{_}-")
        self.assertEqual(
            util.validate_filename('\u00A0中文𠀀', force_ascii=True),
            '%C2%A0%E4%B8%AD%E6%96%87%F0%A0%80%80')

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
        self.assertEqual(
            util.checksum(os.path.join(test_root, 'checksum', 'checksum.txt')),
            'da39a3ee5e6b4b0d3255bfef95601890afd80709',
        )

        self.assertEqual(
            util.checksum(os.path.join(test_root, 'checksum', 'checksum.txt'), method='sha256'),
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

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_file_is_link(self):
        # junction
        entry = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'junction')

        # capture_output is not supported in Python < 3.8
        subprocess.run(
            [
                'mklink',
                '/j',
                entry,
                os.path.join(test_root, 'file_info', 'folder'),
            ],
            shell=True, check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            self.assertTrue(util.file_is_link(entry))
        finally:
            # prevent tree cleanup issue for junction in Python 3.7
            os.remove(entry)

        # directory
        entry = os.path.join(test_root, 'file_info', 'folder')
        self.assertFalse(util.file_is_link(entry))

        # file
        entry = os.path.join(test_root, 'file_info', 'file.txt')
        self.assertFalse(util.file_is_link(entry))

        # non-exist
        entry = os.path.join(test_root, 'file_info', 'nonexist')
        self.assertFalse(util.file_is_link(entry))

    @unittest.skipIf(platform.system() == 'Windows' and not SYMLINK_SUPPORTED,
                     'requires administrator or Developer Mode on Windows')
    def test_file_is_link2(self):
        # symlink
        entry = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'symlink')

        os.symlink(
            os.path.join(test_root, 'file_info', 'file.txt'),
            entry,
        )

        self.assertTrue(util.file_is_link(entry))

    def test_file_info_nonexist(self):
        entry = os.path.join(test_root, 'file_info', 'nonexist.file')
        self.assertEqual(
            util.file_info(entry),
            ('nonexist.file', None, None, None),
        )

    def test_file_info_file(self):
        entry = os.path.join(test_root, 'file_info', 'file.txt')
        self.assertEqual(
            util.file_info(entry),
            ('file.txt', 'file', 3, os.stat(entry).st_mtime),
        )

    def test_file_info_dir(self):
        entry = os.path.join(test_root, 'file_info', 'folder')
        self.assertEqual(
            util.file_info(entry),
            ('folder', 'dir', None, os.stat(entry).st_mtime),
        )

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_file_info_junction_dir(self):
        entry = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'junction')

        # capture_output is not supported in Python < 3.8
        subprocess.run(
            [
                'mklink',
                '/j',
                entry,
                os.path.join(test_root, 'file_info', 'folder'),
            ],
            shell=True, check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            self.assertEqual(
                util.file_info(entry),
                ('junction', 'link', None, os.lstat(entry).st_mtime),
            )
        finally:
            # prevent tree cleanup issue for junction in Python 3.7
            os.remove(entry)

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_file_info_junction_nonexist(self):
        entry = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'junction')

        # capture_output is not supported in Python < 3.8
        subprocess.run(
            [
                'mklink',
                '/j',
                entry,
                os.path.join(test_root, 'file_info', 'nonexist'),
            ],
            shell=True, check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            self.assertEqual(
                util.file_info(entry),
                ('junction', 'link', None, os.lstat(entry).st_mtime),
            )
        finally:
            # prevent tree cleanup issue for junction in Python 3.7
            os.remove(entry)

    @unittest.skipIf(platform.system() == 'Windows' and not SYMLINK_SUPPORTED,
                     'requires administrator or Developer Mode on Windows')
    def test_file_info_symlink_file(self):
        entry = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'symlink')

        # target file
        os.symlink(
            os.path.join(test_root, 'file_info', 'file.txt'),
            entry,
        )

        self.assertEqual(
            util.file_info(entry),
            ('symlink', 'link', None, os.lstat(entry).st_mtime),
        )

    @unittest.skipIf(platform.system() == 'Windows' and not SYMLINK_SUPPORTED,
                     'requires administrator or Developer Mode on Windows')
    def test_file_info_symlink_dir(self):
        entry = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'symlink')

        os.symlink(
            os.path.join(test_root, 'file_info', 'folder'),
            entry,
        )

        self.assertEqual(
            util.file_info(entry),
            ('symlink', 'link', None, os.lstat(entry).st_mtime),
        )

    @unittest.skipIf(platform.system() == 'Windows' and not SYMLINK_SUPPORTED,
                     'requires administrator or Developer Mode on Windows')
    def test_file_info_symlink_nonexist(self):
        entry = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'symlink')

        os.symlink(
            os.path.join(test_root, 'file_info', 'nonexist'),
            entry,
        )

        self.assertEqual(
            util.file_info(entry),
            ('symlink', 'link', None, os.lstat(entry).st_mtime),
        )

    def test_listdir(self):
        entry = os.path.join(test_root, 'listdir')
        self.assertEqual(set(util.listdir(entry)), {
            ('file.txt', 'file', 3, os.stat(os.path.join(entry, 'file.txt')).st_mtime),
            ('folder', 'dir', None, os.stat(os.path.join(entry, 'folder')).st_mtime),
        })
        self.assertEqual(set(util.listdir(entry, recursive=True)), {
            ('file.txt', 'file', 3, os.stat(os.path.join(entry, 'file.txt')).st_mtime),
            ('folder', 'dir', None, os.stat(os.path.join(entry, 'folder')).st_mtime),
            ('folder/.gitkeep', 'file', 0, os.stat(os.path.join(entry, 'folder', '.gitkeep')).st_mtime),
        })

    def test_format_filesize(self):
        self.assertEqual(util.format_filesize(0), '0\xA0B')
        self.assertEqual(util.format_filesize(3), '3\xA0B')
        self.assertEqual(util.format_filesize(1000), '1000\xA0B')
        self.assertEqual(util.format_filesize(1024), '1.0\xA0KB')
        self.assertEqual(util.format_filesize(1080), '1.1\xA0KB')
        self.assertEqual(util.format_filesize(10000), '9.8\xA0KB')
        self.assertEqual(util.format_filesize(10240), '10\xA0KB')
        self.assertEqual(util.format_filesize(20480), '20\xA0KB')
        self.assertEqual(util.format_filesize(1048576), '1.0\xA0MB')
        self.assertEqual(util.format_filesize(2621440), '2.5\xA0MB')
        self.assertEqual(util.format_filesize(10485760), '10\xA0MB')
        self.assertEqual(util.format_filesize(1073741824), '1.0\xA0GB')
        self.assertEqual(util.format_filesize(10737418240), '10\xA0GB')
        self.assertEqual(util.format_filesize(1e14), '91\xA0TB')
        self.assertEqual(util.format_filesize(1e28), '8272\xA0YB')

        self.assertEqual(util.format_filesize(0, si=True), '0\xA0B')
        self.assertEqual(util.format_filesize(3, si=True), '3\xA0B')
        self.assertEqual(util.format_filesize(1000, si=True), '1.0\xA0kB')
        self.assertEqual(util.format_filesize(1024, si=True), '1.0\xA0kB')
        self.assertEqual(util.format_filesize(1080, si=True), '1.1\xA0kB')
        self.assertEqual(util.format_filesize(10000, si=True), '10\xA0kB')
        self.assertEqual(util.format_filesize(10240, si=True), '10\xA0kB')
        self.assertEqual(util.format_filesize(20480, si=True), '20\xA0kB')
        self.assertEqual(util.format_filesize(1048576, si=True), '1.0\xA0MB')
        self.assertEqual(util.format_filesize(2621440, si=True), '2.6\xA0MB')
        self.assertEqual(util.format_filesize(10485760, si=True), '10\xA0MB')
        self.assertEqual(util.format_filesize(1073741824, si=True), '1.1\xA0GB')
        self.assertEqual(util.format_filesize(10737418240, si=True), '11\xA0GB')
        self.assertEqual(util.format_filesize(1e14, si=True), '100\xA0TB')
        self.assertEqual(util.format_filesize(1e28, si=True), '10000\xA0YB')

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

    def test_zip_fix_subpath(self):
        subpath = 'abc/def/測試.txt'
        self.assertEqual(util.zip_fix_subpath(subpath), subpath)

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_fix_subpath_altsep(self):
        self.assertEqual(util.zip_fix_subpath('abc\\def\\測試.txt'), 'abc/def/測試.txt')

    def test_zip_tuple_timestamp(self):
        self.assertEqual(
            util.zip_tuple_timestamp((1987, 1, 1, 0, 0, 0)),
            time.mktime((1987, 1, 1, 0, 0, 0, 0, 0, -1)),
        )

    def test_zip_timestamp(self):
        self.assertEqual(
            util.zip_timestamp(zipfile.ZipInfo('dummy', (1987, 1, 1, 0, 0, 0))),
            time.mktime((1987, 1, 1, 0, 0, 0, 0, 0, -1)),
        )

    def test_zip_file_info(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), '123456')
            zh.writestr(zipfile.ZipInfo('folder/', (1988, 1, 1, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1989, 1, 1, 0, 0, 0)), '123')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

        self.assertEqual(
            util.zip_file_info(zip_filename, 'file.txt'),
            ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'folder'),
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'folder/'),
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'folder/.gitkeep'),
            ('.gitkeep', 'file', 3, zip_tuple_timestamp((1989, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, ''),
            ('', None, None, None),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'implicit_folder'),
            ('implicit_folder', None, None, None),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'implicit_folder/'),
            ('implicit_folder', None, None, None),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, '', check_implicit_dir=True),
            ('', 'dir', None, None),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'implicit_folder', check_implicit_dir=True),
            ('implicit_folder', 'dir', None, None),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'implicit_folder/', check_implicit_dir=True),
            ('implicit_folder', 'dir', None, None),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'implicit_folder/.gitkeep'),
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'nonexist'),
            ('nonexist', None, None, None),
        )

        self.assertEqual(
            util.zip_file_info(zip_filename, 'nonexist/'),
            ('nonexist', None, None, None),
        )

        # take zipfile.ZipFile
        with zipfile.ZipFile(zip_filename, 'r') as zh:
            self.assertEqual(
                util.zip_file_info(zh, 'file.txt'),
                ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
            )

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_file_info_altsep(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('implicit_folder\\.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

        self.assertEqual(
            util.zip_file_info(zip_filename, 'implicit_folder\\.gitkeep'),
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0))),
        )

    def test_zip_listdir(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), '123456')
            zh.writestr(zipfile.ZipInfo('folder/', (1988, 1, 1, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1989, 1, 1, 0, 0, 0)), '123')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

        self.assertEqual(set(util.zip_listdir(zip_filename, '')), {
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
            ('implicit_folder', 'dir', None, None),
            ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
        })

        self.assertEqual(set(util.zip_listdir(zip_filename, '/')), {
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
            ('implicit_folder', 'dir', None, None),
            ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
        })

        self.assertEqual(set(util.zip_listdir(zip_filename, '', recursive=True)), {
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
            ('folder/.gitkeep', 'file', 3, zip_tuple_timestamp((1989, 1, 1, 0, 0, 0))),
            ('implicit_folder', 'dir', None, None),
            ('implicit_folder/.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0))),
            ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
        })

        self.assertEqual(set(util.zip_listdir(zip_filename, 'folder')), {
            ('.gitkeep', 'file', 3, zip_tuple_timestamp((1989, 1, 1, 0, 0, 0)))
        })

        self.assertEqual(set(util.zip_listdir(zip_filename, 'folder/')), {
            ('.gitkeep', 'file', 3, zip_tuple_timestamp((1989, 1, 1, 0, 0, 0)))
        })

        self.assertEqual(set(util.zip_listdir(zip_filename, 'implicit_folder')), {
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0)))
        })

        self.assertEqual(set(util.zip_listdir(zip_filename, 'implicit_folder/')), {
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0)))
        })

        with self.assertRaises(util.ZipDirNotFoundError):
            set(util.zip_listdir(zip_filename, 'nonexist'))

        with self.assertRaises(util.ZipDirNotFoundError):
            set(util.zip_listdir(zip_filename, 'nonexist/'))

        with self.assertRaises(util.ZipDirNotFoundError):
            set(util.zip_listdir(zip_filename, 'file.txt'))

        # take zipfile.ZipFile
        with zipfile.ZipFile(zip_filename, 'r') as zh:
            self.assertEqual(set(util.zip_listdir(zh, '')), {
                ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
                ('implicit_folder', 'dir', None, None),
                ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
            })

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_listdir_altsep(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo(r'implicit_folder\.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

        self.assertEqual(set(util.zip_listdir(zip_filename, 'implicit_folder\\')), {
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0)))
        })

    def test_zip_has(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr('file.txt', '123456')
            zh.writestr('folder/', '')
            zh.writestr('folder/.gitkeep', '123')
            zh.writestr('implicit_folder/.gitkeep', '1234')

        self.assertTrue(util.zip_has(zip_filename, '', type='dir'))
        self.assertTrue(util.zip_has(zip_filename, '/', type='dir'))
        self.assertFalse(util.zip_has(zip_filename, 'file.txt', type='dir'))
        self.assertFalse(util.zip_has(zip_filename, 'file.txt/', type='dir'))
        self.assertTrue(util.zip_has(zip_filename, 'folder', type='dir'))
        self.assertTrue(util.zip_has(zip_filename, 'folder/', type='dir'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder', type='dir'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder/', type='dir'))
        self.assertFalse(util.zip_has(zip_filename, 'implicit_folder/.gitkeep', type='dir'))
        self.assertFalse(util.zip_has(zip_filename, 'implicit_folder/.gitkeep/', type='dir'))
        self.assertFalse(util.zip_has(zip_filename, 'nonexist.foo', type='dir'))

        self.assertFalse(util.zip_has(zip_filename, '', type='file'))
        self.assertFalse(util.zip_has(zip_filename, '/', type='file'))
        self.assertTrue(util.zip_has(zip_filename, 'file.txt', type='file'))
        self.assertTrue(util.zip_has(zip_filename, 'file.txt/', type='file'))
        self.assertFalse(util.zip_has(zip_filename, 'folder', type='file'))
        self.assertFalse(util.zip_has(zip_filename, 'folder/', type='file'))
        self.assertFalse(util.zip_has(zip_filename, 'implicit_folder', type='file'))
        self.assertFalse(util.zip_has(zip_filename, 'implicit_folder/', type='file'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder/.gitkeep', type='file'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder/.gitkeep/', type='file'))
        self.assertFalse(util.zip_has(zip_filename, 'nonexist.foo', type='file'))

        self.assertTrue(util.zip_has(zip_filename, '', type='any'))
        self.assertTrue(util.zip_has(zip_filename, '/', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'file.txt', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'file.txt/', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'folder', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'folder/', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder/', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder/.gitkeep', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder/.gitkeep/', type='any'))
        self.assertFalse(util.zip_has(zip_filename, 'nonexist.foo', type='any'))

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_has_altsep(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr('implicit_folder\\.gitkeep', '1234')

        self.assertTrue(util.zip_has(zip_filename, '', type='dir'))
        self.assertTrue(util.zip_has(zip_filename, '\\', type='dir'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder', type='dir'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder\\', type='dir'))
        self.assertFalse(util.zip_has(zip_filename, 'implicit_folder\\.gitkeep', type='dir'))
        self.assertFalse(util.zip_has(zip_filename, 'implicit_folder\\.gitkeep\\', type='dir'))

        self.assertFalse(util.zip_has(zip_filename, '', type='file'))
        self.assertFalse(util.zip_has(zip_filename, '\\', type='file'))
        self.assertFalse(util.zip_has(zip_filename, 'implicit_folder', type='file'))
        self.assertFalse(util.zip_has(zip_filename, 'implicit_folder\\', type='file'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder\\.gitkeep', type='file'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder\\.gitkeep\\', type='file'))

        self.assertTrue(util.zip_has(zip_filename, '', type='any'))
        self.assertTrue(util.zip_has(zip_filename, '\\', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder\\', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder\\.gitkeep', type='any'))
        self.assertTrue(util.zip_has(zip_filename, 'implicit_folder\\.gitkeep\\', type='any'))

    def test_zip_compress01(self):
        """directory"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with open(os.path.join(temp_dir, 'file.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')
        os.makedirs(os.path.join(temp_dir, 'folder'), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, 'folder', 'subfolder'), exist_ok=True)
        with open(os.path.join(temp_dir, 'folder', 'subfolder', 'subfolderfile.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF')
        with open(os.path.join(temp_dir, 'folder', 'subfile.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('123456')

        util.zip_compress(zip_filename, os.path.join(temp_dir, 'folder'), 'myfolder')

        with zipfile.ZipFile(zip_filename) as zh:
            self.assertEqual(zh.read('myfolder/subfolder/subfolderfile.txt').decode('UTF-8'), 'ABCDEF')
            self.assertEqual(zh.read('myfolder/subfile.txt').decode('UTF-8'), '123456')

    def test_zip_compress02(self):
        """directory with subpath=''"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with open(os.path.join(temp_dir, 'file.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')
        os.makedirs(os.path.join(temp_dir, 'folder'), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, 'folder', 'subfolder'), exist_ok=True)
        with open(os.path.join(temp_dir, 'folder', 'subfolder', 'subfolderfile.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF')
        with open(os.path.join(temp_dir, 'folder', 'subfile.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('123456')

        util.zip_compress(zip_filename, os.path.join(temp_dir, 'folder'), '')

        with zipfile.ZipFile(zip_filename) as zh:
            self.assertEqual(zh.read('subfolder/subfolderfile.txt').decode('UTF-8'), 'ABCDEF')
            self.assertEqual(zh.read('subfile.txt').decode('UTF-8'), '123456')

    def test_zip_compress03(self):
        """directory with filter"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with open(os.path.join(temp_dir, 'file.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')
        os.makedirs(os.path.join(temp_dir, 'folder'), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, 'folder', 'subfolder'), exist_ok=True)
        with open(os.path.join(temp_dir, 'folder', 'subfolder', 'subfolderfile.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF')
        with open(os.path.join(temp_dir, 'folder', 'subfile.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('123456')

        util.zip_compress(zip_filename, os.path.join(temp_dir, 'folder'), 'myfolder', filter={'subfolder'})

        with zipfile.ZipFile(zip_filename) as zh:
            self.assertEqual(zh.read('myfolder/subfolder/subfolderfile.txt').decode('UTF-8'), 'ABCDEF')
            with self.assertRaises(KeyError):
                zh.getinfo('myfolder/subfile.txt')

    def test_zip_compress04(self):
        """file"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with open(os.path.join(temp_dir, 'file.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')
        os.makedirs(os.path.join(temp_dir, 'folder'), exist_ok=True)
        with open(os.path.join(temp_dir, 'folder', 'sybfile1.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('123456')

        util.zip_compress(zip_filename, os.path.join(temp_dir, 'file.txt'), 'myfile.txt')

        with zipfile.ZipFile(zip_filename) as zh:
            self.assertEqual(zh.read('myfile.txt').decode('UTF-8'), 'ABC中文')

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_compress05(self):
        """altsep"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        os.makedirs(os.path.join(temp_dir, 'folder', 'subfolder'), exist_ok=True)
        with open(os.path.join(temp_dir, 'folder', 'subfolder', 'subfolderfile.txt'), 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF')

        util.zip_compress(zip_filename, os.path.join(temp_dir, 'folder'), 'sub\\folder')

        with zipfile.ZipFile(zip_filename) as zh:
            self.assertEqual(zh.read('sub/folder/subfolder/subfolderfile.txt').decode('UTF-8'), 'ABCDEF')

    def test_zip_extract01(self):
        """root"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', (1987, 1, 2, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1987, 1, 3, 0, 0, 0)), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1987, 1, 4, 0, 0, 0)), 'abc')

        util.zip_extract(zip_filename, os.path.join(temp_dir, 'zipfile'))

        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'zipfile', 'file.txt')).st_mtime,
            zip_tuple_timestamp((1987, 1, 1, 0, 0, 0)),
        )
        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'zipfile', 'folder')).st_mtime,
            zip_tuple_timestamp((1987, 1, 2, 0, 0, 0)),
        )
        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'zipfile', 'folder', '.gitkeep')).st_mtime,
            zip_tuple_timestamp((1987, 1, 3, 0, 0, 0)),
        )
        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'zipfile', 'implicit_folder', '.gitkeep')).st_mtime,
            zip_tuple_timestamp((1987, 1, 4, 0, 0, 0)),
        )

    def test_zip_extract02(self):
        """folder explicit"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', (1987, 1, 2, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1987, 1, 3, 0, 0, 0)), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1987, 1, 4, 0, 0, 0)), 'abc')

        util.zip_extract(zip_filename, os.path.join(temp_dir, 'folder'), 'folder')

        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'folder')).st_mtime,
            zip_tuple_timestamp((1987, 1, 2, 0, 0, 0)),
        )
        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'folder', '.gitkeep')).st_mtime,
            zip_tuple_timestamp((1987, 1, 3, 0, 0, 0)),
        )

    def test_zip_extract03(self):
        """folder implicit"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', (1987, 1, 2, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1987, 1, 3, 0, 0, 0)), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1987, 1, 4, 0, 0, 0)), 'abc')

        util.zip_extract(zip_filename, os.path.join(temp_dir, 'implicit_folder'), 'implicit_folder')

        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'implicit_folder', '.gitkeep')).st_mtime,
            zip_tuple_timestamp((1987, 1, 4, 0, 0, 0)),
        )

    def test_zip_extract04(self):
        """file"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', (1987, 1, 2, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1987, 1, 3, 0, 0, 0)), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1987, 1, 4, 0, 0, 0)), 'abc')

        util.zip_extract(zip_filename, os.path.join(temp_dir, 'zipfile.txt'), 'file.txt')

        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'zipfile.txt')).st_mtime,
            zip_tuple_timestamp((1987, 1, 1, 0, 0, 0)),
        )

    def test_zip_extract05(self):
        """target exists"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', (1987, 1, 2, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1987, 1, 3, 0, 0, 0)), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1987, 1, 4, 0, 0, 0)), 'abc')

        with self.assertRaises(FileExistsError):
            util.zip_extract(zip_filename, temp_dir, '')

    def test_zip_extract06(self):
        """timezone adjust"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), 'ABC中文')

        test_offset = -12345  # use a timezone offset which is unlikely really used
        util.zip_extract(zip_filename, os.path.join(temp_dir, 'zipfile'), tzoffset=test_offset)
        delta = datetime.now().astimezone().utcoffset().total_seconds()

        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'zipfile', 'file.txt')).st_mtime,
            zip_tuple_timestamp((1987, 1, 1, 0, 0, 0)) - test_offset + delta,
        )

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_extract07(self):
        """altsep"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('sub\\folder\\.gitkeep', (1987, 1, 4, 0, 0, 0)), 'abc')

        util.zip_extract(zip_filename, os.path.join(temp_dir, 'folder'), 'sub\\folder')

        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'folder', '.gitkeep')).st_mtime,
            zip_tuple_timestamp((1987, 1, 4, 0, 0, 0)),
        )

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

        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr('refresh.html', '<meta http-equiv="refresh" content="0;url=target.html">')

        with zipfile.ZipFile(zip_filename, 'r') as zh:
            with zh.open('refresh.html') as fh:
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

        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr('refresh.html', '<meta http-equiv="refresh" content="0;url=target.html">')

        with zipfile.ZipFile(zip_filename, 'r') as zh:
            with zh.open('refresh.html') as fh:
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
            zh.writestr(zipfile.ZipInfo('19870101/index.rdf', (1987, 1, 1, 0, 0, 0)), """<?xml version="1.0"?>
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
            zh.writestr(zipfile.ZipInfo('webpage1/index.rdf', (1987, 1, 1, 0, 0, 0)), """<?xml version="1.0"?>
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
            zh.writestr(zipfile.ZipInfo('webpage2/index.html', (1987, 1, 1, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('webpage3/index.svg', (1987, 1, 1, 0, 0, 0)), '')

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
