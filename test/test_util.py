from unittest import mock
import unittest
import sys
import os
import platform
import subprocess
import shutil
import io
import time
import zipfile
import collections
from webscrapbook import util
from webscrapbook.util import frozendict

root_dir = os.path.abspath(os.path.dirname(__file__))

class TestUtils(unittest.TestCase):
    def test_frozendict(self):
        dict_ = {'a': 1, 'b': 2, 'c': 3}
        frozendict_ = frozendict(dict_)

        self.assertTrue(isinstance(frozendict_, collections.abc.Hashable))
        self.assertTrue(isinstance(frozendict_, collections.abc.Mapping))
        self.assertFalse(isinstance(frozendict_, collections.abc.MutableMapping))

        self.assertEqual(eval(repr(frozendict_)), frozendict_)
        self.assertRegex(repr(frozendict_), r'^frozendict\([^)]*\)$')

        self.assertTrue(frozendict_ == dict_)
        self.assertTrue('a' in frozendict_)
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

    def test_get_breadcrumbs(self):
        # directory
        self.assertEqual(list(util.get_breadcrumbs(['/path/to/directory/'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('directory', '/path/to/directory/', '/', True)
            ])

        # conflicting directory/file
        self.assertEqual(list(util.get_breadcrumbs(['/path/to/fake.ext!/'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('fake.ext!', '/path/to/fake.ext!/', '/', True),
            ])

        # sub-archive path(s)
        self.assertEqual(list(util.get_breadcrumbs(['/path/to/archive.ext', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', True),
            ])

        self.assertEqual(list(util.get_breadcrumbs(['/path/to/archive.ext', 'subdir'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/subdir/', '/', True),
            ])

        self.assertEqual(list(util.get_breadcrumbs(['/path/to/archive.ext', 'nested1.zip', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('nested1.zip', '/path/to/archive.ext!/nested1.zip!/', '!/', True),
            ])

        self.assertEqual(list(util.get_breadcrumbs(['/path/to/archive.ext', 'nested1.zip', 'subdir'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('nested1.zip', '/path/to/archive.ext!/nested1.zip!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/nested1.zip!/subdir/', '/', True),
            ])

        self.assertEqual(list(util.get_breadcrumbs(['/path/to/archive.ext', 'subdir/nested1.zip', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/subdir/', '/', False),
            ('nested1.zip', '/path/to/archive.ext!/subdir/nested1.zip!/', '!/', True),
            ])

        # base
        self.assertEqual(list(util.get_breadcrumbs(['/path/to/directory/'], base='/wsb')), [
            ('.', '/wsb/', '/', False),
            ('path', '/wsb/path/', '/', False),
            ('to', '/wsb/path/to/', '/', False),
            ('directory', '/wsb/path/to/directory/', '/', True),
            ])

        # base (with slash)
        self.assertEqual(list(util.get_breadcrumbs(['/path/to/directory/'], base='/wsb/')), [
            ('.', '/wsb/', '/', False),
            ('path', '/wsb/path/', '/', False),
            ('to', '/wsb/path/to/', '/', False),
            ('directory', '/wsb/path/to/directory/', '/', True),
            ])

        # topname
        self.assertEqual(list(util.get_breadcrumbs(['/path/to/directory/'], topname='MyWsb')), [
            ('MyWsb', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('directory', '/path/to/directory/', '/', True)
            ])

    def test_checksum(self):
        self.assertEqual(
            util.checksum(os.path.join(root_dir, 'test_util', 'checksum', 'checksum.txt')),
            'da39a3ee5e6b4b0d3255bfef95601890afd80709'
            )

        self.assertEqual(
            util.checksum(os.path.join(root_dir, 'test_util', 'checksum', 'checksum.txt'), method='sha256'),
            'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
            )

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_file_is_link(self):
        # junction
        entry = os.path.join(root_dir, 'test_util', 'file_info', 'junction')

        # capture_output is not supported in Python < 3.8
        subprocess.run([
            'mklink',
            '/j',
            entry,
            os.path.join(root_dir, 'test_util', 'file_info', 'folder'),
            ], shell=True, check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

        try:
            self.assertTrue(util.file_is_link(entry))
        finally:
            try:
                os.remove(entry)
            except FileNotFoundError:
                pass

        # directory
        entry = os.path.join(root_dir, 'test_util', 'file_info', 'folder')
        self.assertFalse(util.file_is_link(entry))

        # file
        entry = os.path.join(root_dir, 'test_util', 'file_info', 'file.txt')
        self.assertFalse(util.file_is_link(entry))

        # non-exist
        entry = os.path.join(root_dir, 'test_util', 'file_info', 'nonexist')
        self.assertFalse(util.file_is_link(entry))

    def test_file_is_link2(self):
        # symlink
        entry = os.path.join(root_dir, 'test_util', 'file_info', 'symlink')
        try:
            os.symlink(
                os.path.join(root_dir, 'test_util', 'file_info', 'file.txt'),
                entry,
                )
        except OSError:
            if platform.system() == 'Windows':
                self.skipTest('requires administrator or Developer Mode on Windows')
            else:
                raise

        try:
            self.assertTrue(util.file_is_link(entry))
        finally:
            try:
                os.remove(entry)
            except FileNotFoundError:
                pass

    def test_file_info(self):
        entry = os.path.join(root_dir, 'test_util', 'file_info', 'nonexist.file')
        self.assertEqual(
            util.file_info(entry),
            ('nonexist.file', None, None, None)
            )

        entry = os.path.join(root_dir, 'test_util', 'file_info', 'file.txt')
        self.assertEqual(
            util.file_info(entry),
            ('file.txt', 'file', 3, os.stat(entry).st_mtime)
            )

        entry = os.path.join(root_dir, 'test_util', 'file_info', 'folder')
        self.assertEqual(
            util.file_info(entry),
            ('folder', 'dir', None, os.stat(entry).st_mtime)
            )

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_file_info_junction(self):
        entry = os.path.join(root_dir, 'test_util', 'file_info', 'junction')

        # target directory
        # capture_output is not supported in Python < 3.8
        subprocess.run([
            'mklink',
            '/j',
            entry,
            os.path.join(root_dir, 'test_util', 'file_info', 'folder'),
            ], shell=True, check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

        try:
            self.assertEqual(
                util.file_info(entry),
                ('junction', 'link', None, os.lstat(entry).st_mtime)
                )
        finally:
            try:
                os.remove(entry)
            except FileNotFoundError:
                pass

        # target non-exist
        # capture_output is not supported in Python < 3.8
        subprocess.run([
            'mklink',
            '/j',
            entry,
            os.path.join(root_dir, 'test_util', 'file_info', 'nonexist'),
            ], shell=True, check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

        try:
            self.assertEqual(
                util.file_info(entry),
                ('junction', 'link', None, os.lstat(entry).st_mtime)
                )
        finally:
            try:
                os.remove(entry)
            except FileNotFoundError:
                pass

    def test_file_info_symlink(self):
        entry = os.path.join(root_dir, 'test_util', 'file_info', 'symlink')

        # target file
        try:
            os.symlink(
                os.path.join(root_dir, 'test_util', 'file_info', 'file.txt'),
                entry,
                )
        except OSError:
            if platform.system() == 'Windows':
                self.skipTest('requires administrator or Developer Mode on Windows')
            else:
                raise

        try:
            self.assertEqual(
                util.file_info(entry),
                ('symlink', 'link', None, os.lstat(entry).st_mtime)
                )
        finally:
            try:
                os.remove(entry)
            except FileNotFoundError:
                pass

        # target directory
        try:
            os.symlink(
                os.path.join(root_dir, 'test_util', 'file_info', 'folder'),
                entry,
                )
        except OSError:
            if platform.system() == 'Windows':
                self.skipTest('requires administrator or Developer Mode on Windows')
            else:
                raise

        try:
            self.assertEqual(
                util.file_info(entry),
                ('symlink', 'link', None, os.lstat(entry).st_mtime)
                )
        finally:
            try:
                os.remove(entry)
            except FileNotFoundError:
                pass

        # target non-exist
        try:
            os.symlink(
                os.path.join(root_dir, 'test_util', 'file_info', 'nonexist'),
                entry,
                )
        except OSError:
            if platform.system() == 'Windows':
                self.skipTest('requires administrator or Developer Mode on Windows')
            else:
                raise

        try:
            self.assertEqual(
                util.file_info(entry),
                ('symlink', 'link', None, os.lstat(entry).st_mtime)
                )
        finally:
            try:
                os.remove(entry)
            except FileNotFoundError:
                pass

    def test_listdir(self):
        entry = os.path.join(root_dir, 'test_util', 'listdir')
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

    def test_zip_tuple_timestamp(self):
        self.assertEqual(
            util.zip_tuple_timestamp((1987, 1, 1, 0, 0, 0)),
            time.mktime((1987, 1, 1, 0, 0, 0, 0, 0, -1))
            )

    def test_zip_timestamp(self):
        self.assertEqual(
            util.zip_timestamp(zipfile.ZipInfo('dummy', (1987, 1, 1, 0, 0, 0))),
            time.mktime((1987, 1, 1, 0, 0, 0, 0, 0, -1))
            )

    def test_zip_file_info(self):
        zip_filename = os.path.join(root_dir, 'test_util', 'zipfile.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), '123456')
                zh.writestr(zipfile.ZipInfo('folder/', (1988, 1, 1, 0, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1989, 1, 1, 0, 0, 0)), '123')
                zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

            self.assertEqual(
                util.zip_file_info(zip_filename, 'file.txt'),
                ('file.txt', 'file', 6, 536428800)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'folder'),
                ('folder', 'dir', None, 567964800)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'folder/'),
                ('folder', 'dir', None, 567964800)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'folder/.gitkeep'),
                ('.gitkeep', 'file', 3, 599587200)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'implicit_folder'),
                ('implicit_folder', None, None, None)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'implicit_folder/'),
                ('implicit_folder', None, None, None)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'implicit_folder', check_implicit_dir=True),
                ('implicit_folder', 'dir', None, None)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'implicit_folder/', check_implicit_dir=True),
                ('implicit_folder', 'dir', None, None)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'implicit_folder/.gitkeep'),
                ('.gitkeep', 'file', 4, 631123200)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'nonexist'),
                ('nonexist', None, None, None)
                )

            self.assertEqual(
                util.zip_file_info(zip_filename, 'nonexist/'),
                ('nonexist', None, None, None)
                )

            # take zipfile.ZipFile
            with zipfile.ZipFile(zip_filename, 'r') as zip:
                self.assertEqual(
                    util.zip_file_info(zip, 'file.txt'),
                    ('file.txt', 'file', 6, 536428800)
                    )
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_zip_listdir(self):
        zip_filename = os.path.join(root_dir, 'test_util', 'zipfile.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), '123456')
                zh.writestr(zipfile.ZipInfo('folder/', (1988, 1, 1, 0, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1989, 1, 1, 0, 0, 0)), '123')
                zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

            self.assertEqual(set(util.zip_listdir(zip_filename, '')), {
                ('folder', 'dir', None, 567964800),
                ('implicit_folder', 'dir', None, None),
                ('file.txt', 'file', 6, 536428800),
                })

            self.assertEqual(set(util.zip_listdir(zip_filename, '/')), {
                ('folder', 'dir', None, 567964800),
                ('implicit_folder', 'dir', None, None),
                ('file.txt', 'file', 6, 536428800),
                })

            self.assertEqual(set(util.zip_listdir(zip_filename, '', recursive=True)), {
                ('folder', 'dir', None, 567964800),
                ('folder/.gitkeep', 'file', 3, 599587200),
                ('implicit_folder', 'dir', None, None),
                ('implicit_folder/.gitkeep', 'file', 4, 631123200),
                ('file.txt', 'file', 6, 536428800),
                })

            self.assertEqual(set(util.zip_listdir(zip_filename, 'folder')), {
                ('.gitkeep', 'file', 3, 599587200)
                })

            self.assertEqual(set(util.zip_listdir(zip_filename, 'folder/')), {
                ('.gitkeep', 'file', 3, 599587200)
                })

            self.assertEqual(set(util.zip_listdir(zip_filename, 'implicit_folder')), {
                ('.gitkeep', 'file', 4, 631123200)
                })

            self.assertEqual(set(util.zip_listdir(zip_filename, 'implicit_folder/')), {
                ('.gitkeep', 'file', 4, 631123200)
                })

            with self.assertRaises(util.ZipDirNotFoundError):
                set(util.zip_listdir(zip_filename, 'nonexist'))

            with self.assertRaises(util.ZipDirNotFoundError):
                set(util.zip_listdir(zip_filename, 'nonexist/'))

            with self.assertRaises(util.ZipDirNotFoundError):
                set(util.zip_listdir(zip_filename, 'file.txt'))

            # take zipfile.ZipFile
            with zipfile.ZipFile(zip_filename, 'r') as zip:
                self.assertEqual(set(util.zip_listdir(zip, '')), {
                    ('folder', 'dir', None, 567964800),
                    ('implicit_folder', 'dir', None, None),
                    ('file.txt', 'file', 6, 536428800),
                    })
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_zip_hasdir(self):
        zip_filename = os.path.join(root_dir, 'test_util', 'zipfile.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('file.txt', '123456')
                zh.writestr('folder/', '')
                zh.writestr('folder/.gitkeep', '123')
                zh.writestr('implicit_folder/.gitkeep', '1234')

            self.assertTrue(util.zip_hasdir(zip_filename, ''))
            self.assertTrue(util.zip_hasdir(zip_filename, '/'))
            self.assertFalse(util.zip_hasdir(zip_filename, 'file.txt'))
            self.assertFalse(util.zip_hasdir(zip_filename, 'file.txt/'))
            self.assertTrue(util.zip_hasdir(zip_filename, 'folder'))
            self.assertTrue(util.zip_hasdir(zip_filename, 'folder/'))
            self.assertTrue(util.zip_hasdir(zip_filename, 'implicit_folder'))
            self.assertTrue(util.zip_hasdir(zip_filename, 'implicit_folder/'))
            self.assertFalse(util.zip_hasdir(zip_filename, 'implicit_folder/.gitkeep'))
            self.assertFalse(util.zip_hasdir(zip_filename, 'implicit_folder/.gitkeep/'))
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_parse_meta_refresh(self):
        self.assertEqual(
            util.parse_meta_refresh(os.path.join(root_dir, 'test_util', 'parse_meta_refresh', 'refresh1.html')),
            (0, 'target.html')
            )
        self.assertEqual(
            util.parse_meta_refresh(os.path.join(root_dir, 'test_util', 'parse_meta_refresh', 'refresh2.html')),
            (0, 'target.html')
            )
        self.assertEqual(
            util.parse_meta_refresh(os.path.join(root_dir, 'test_util', 'parse_meta_refresh', 'nonexist.html')),
            (None, None)
            )

        zip_filename = os.path.join(root_dir, 'test_util', 'zipfile.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('refresh.html', '<meta http-equiv="refresh" content="0;url=target.html">')

            with zipfile.ZipFile(zip_filename, 'r') as zh:
                with zh.open('refresh.html') as f:
                    self.assertEqual(
                        util.parse_meta_refresh(f),
                        (0, 'target.html')
                        )
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_parse_maff_index_rdf(self):
        maff_filename = os.path.join(root_dir, 'test_util', 'tempfile.maff')
        try:
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
                        ('Example MAFF', 'http://example.com/', 'Mon, 25 Dec 2017 17:27:46 GMT', 'index.html', 'UTF-8')
                        )
        finally:
            try:
                os.remove(maff_filename)
            except FileNotFoundError:
                pass

    def test_get_maff_pages(self):
        maff_filename = os.path.join(root_dir, 'test_util', 'tempfile.maff')
        try:
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
        finally:
            try:
                os.remove(maff_filename)
            except FileNotFoundError:
                pass

    @mock.patch('sys.stderr', io.StringIO())
    def test_encrypt(self):
        self.assertEqual(util.encrypt('1234', 'salt', 'plain'),
            '1234salt'
            )
        self.assertEqual(util.encrypt('1234', 'salt', 'md5'),
            '1fadcf6eb4345975be993f237c51d426'
            )
        self.assertEqual(util.encrypt('1234', 'salt', 'sha1'),
            '40c95464b7eacddb5572af5468ffb1cdb5b13f35'
            )
        self.assertEqual(util.encrypt('1234', 'salt', 'sha256'),
            '4b3bed8af7b7612e8c1e25f63ba24496f5b16b2df44efb2db7ce3cb24b7e96f7'
            )
        self.assertEqual(util.encrypt('1234', 'salt', 'unknown'),
            '1234salt'
            )

class TestTokenHandler(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_util', 'token_handler')
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except NotADirectoryError:
            os.remove(self.test_dir)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.util.TokenHandler.check_delete_expire')
    @mock.patch('webscrapbook.util.TokenHandler.DEFAULT_EXPIRY', 10)
    def test_acquire1(self, mock_check):
        now = time.time()
        expected_expire_time = int(now) + 10

        handler = util.TokenHandler(self.test_dir)
        token = handler.acquire()
        token_file = os.path.join(self.test_dir, token)

        self.assertTrue(os.path.isfile(token_file))
        with open(token_file, 'r', encoding='UTF-8') as f:
            self.assertAlmostEqual(int(f.read()), expected_expire_time, delta=1)
        self.assertAlmostEqual(mock_check.call_args[0][0], now, delta=1)

    @mock.patch('webscrapbook.util.TokenHandler.check_delete_expire')
    @mock.patch('webscrapbook.util.TokenHandler.DEFAULT_EXPIRY', 30)
    def test_acquire2(self, mock_check):
        now = 30000
        expected_expire_time = int(now) + 30

        handler = util.TokenHandler(self.test_dir)
        token = handler.acquire(now)
        token_file = os.path.join(self.test_dir, token)

        self.assertTrue(os.path.isfile(token_file))
        with open(token_file, 'r', encoding='UTF-8') as f:
            self.assertEqual(int(f.read()), expected_expire_time)
        self.assertEqual(mock_check.call_args[0][0], now)

    def test_validate1(self):
        token = 'sampleToken'
        token_time = int(time.time()) + 3

        token_file = os.path.join(self.test_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(token_time))

        handler = util.TokenHandler(self.test_dir)
        self.assertTrue(handler.validate(token))

    def test_validate2(self):
        token = 'sampleToken'
        token_time = int(time.time()) - 3

        token_file = os.path.join(self.test_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(token_time))

        handler = util.TokenHandler(self.test_dir)
        self.assertFalse(handler.validate(token))

    def test_validate3(self):
        token = 'sampleToken'
        now = 30000
        token_time = 30001

        token_file = os.path.join(self.test_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(token_time))

        handler = util.TokenHandler(self.test_dir)
        self.assertTrue(handler.validate(token, now))

    def test_validate4(self):
        token = 'sampleToken'
        now = 30000
        token_time = 29999

        token_file = os.path.join(self.test_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(token_time))

        handler = util.TokenHandler(self.test_dir)
        self.assertFalse(handler.validate(token, now))

    def test_delete(self):
        token = 'sampleToken'

        token_file = os.path.join(self.test_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(32768))

        handler = util.TokenHandler(self.test_dir)
        handler.delete(token)
        self.assertFalse(os.path.exists(token_file))

    def test_delete_expire1(self):
        now = int(time.time())

        with open(os.path.join(self.test_dir, 'sampleToken1'), 'w', encoding='UTF-8') as f:
            f.write(str(now - 100))
        with open(os.path.join(self.test_dir, 'sampleToken2'), 'w', encoding='UTF-8') as f:
            f.write(str(now - 10))
        with open(os.path.join(self.test_dir, 'sampleToken3'), 'w', encoding='UTF-8') as f:
            f.write(str(now + 10))
        with open(os.path.join(self.test_dir, 'sampleToken4'), 'w', encoding='UTF-8') as f:
            f.write(str(now + 100))

        handler = util.TokenHandler(self.test_dir)
        handler.delete_expire()

        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'sampleToken1')))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'sampleToken2')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'sampleToken3')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'sampleToken4')))

    def test_delete_expire2(self):
        now = 30000

        with open(os.path.join(self.test_dir, 'sampleToken1'), 'w', encoding='UTF-8') as f:
            f.write(str(29000))
        with open(os.path.join(self.test_dir, 'sampleToken2'), 'w', encoding='UTF-8') as f:
            f.write(str(29100))
        with open(os.path.join(self.test_dir, 'sampleToken3'), 'w', encoding='UTF-8') as f:
            f.write(str(30100))
        with open(os.path.join(self.test_dir, 'sampleToken4'), 'w', encoding='UTF-8') as f:
            f.write(str(30500))

        handler = util.TokenHandler(self.test_dir)
        handler.delete_expire(now)

        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'sampleToken1')))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'sampleToken2')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'sampleToken3')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'sampleToken4')))

    @mock.patch('webscrapbook.util.TokenHandler.delete_expire')
    def test_check_delete_expire1(self, mock_delete):
        now = int(time.time())

        handler = util.TokenHandler(self.test_dir)
        self.assertEqual(handler.last_purge, 0)

        handler.check_delete_expire()
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.last_purge, now, delta=1)

    @mock.patch('webscrapbook.util.TokenHandler.delete_expire')
    @mock.patch('webscrapbook.util.TokenHandler.PURGE_INTERVAL', 1000)
    def test_check_delete_expire2(self, mock_delete):
        now = int(time.time())

        handler = util.TokenHandler(self.test_dir)
        handler.last_purge = now - 1100

        handler.check_delete_expire()
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.last_purge, now, delta=1)

    @mock.patch('webscrapbook.util.TokenHandler.delete_expire')
    @mock.patch('webscrapbook.util.TokenHandler.PURGE_INTERVAL', 1000)
    def test_check_delete_expire3(self, mock_delete):
        now = int(time.time())

        handler = util.TokenHandler(self.test_dir)
        handler.last_purge = now - 900

        handler.check_delete_expire()
        mock_delete.assert_not_called()
        self.assertEqual(handler.last_purge, now - 900)

    @mock.patch('webscrapbook.util.TokenHandler.delete_expire')
    @mock.patch('webscrapbook.util.TokenHandler.PURGE_INTERVAL', 1000)
    def test_check_delete_expire4(self, mock_delete):
        now = 40000

        handler = util.TokenHandler(self.test_dir)
        handler.last_purge = now - 1100

        handler.check_delete_expire(now)
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.last_purge, now, delta=1)

    @mock.patch('webscrapbook.util.TokenHandler.delete_expire')
    @mock.patch('webscrapbook.util.TokenHandler.PURGE_INTERVAL', 1000)
    def test_check_delete_expire5(self, mock_delete):
        now = 40000

        handler = util.TokenHandler(self.test_dir)
        handler.last_purge = now - 900

        handler.check_delete_expire(now)
        mock_delete.assert_not_called()
        self.assertEqual(handler.last_purge, now - 900)

if __name__ == '__main__':
    unittest.main()
