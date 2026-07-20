import io
import unittest
from contextlib import nullcontext
from unittest import mock

from webscrapbook._polyfill import zipfile
from webscrapbook.util.fs import zip_mode

from . import DUMMY_TS, DUMMY_ZIP_DT


class TestZipInfoExt(unittest.TestCase):
    def test_init(self):
        # default to current datetime if not provided
        with mock.patch('time.time', return_value=DUMMY_TS):
            zinfo = zipfile.ZipInfo()
            self.assertEqual(zinfo.date_time, DUMMY_ZIP_DT)

        # default to 0o40775 for folders
        zinfo = zipfile.ZipInfo('folder/')
        self.assertEqual(zinfo.external_attr, (0o40775 << 16) | 0x10)

        # tidy bad bits for folders
        zinfo = zipfile.ZipInfo('folder/', mode=0o777777)
        self.assertEqual(zinfo.external_attr, (0o47777 << 16) | 0x10)

        # default to 0o100600 for files
        zinfo = zipfile.ZipInfo('file.txt')
        self.assertEqual(zinfo.external_attr, 0o600 << 16)

    def test_set_datetime(self):
        # before local 1980-01-01 00:00:00 (DOS min)
        dt = (1979, 12, 30, 23, 59, 59)
        zinfo = zipfile.ZipInfo('dummy')._set_datetime(dt)
        self.assertEqual(zinfo.date_time, (1980, 1, 1, 0, 0, 0))

        # normal
        dt = (2038, 1, 19, 3, 14, 7)
        zinfo = zipfile.ZipInfo('dummy')._set_datetime(dt)
        self.assertEqual(zinfo.date_time, dt)

        # after local 2107-12-31 23:59:59 (DOS max)
        dt = (2108, 1, 2, 0, 0, 0)
        zinfo = zipfile.ZipInfo('dummy')._set_datetime(dt)
        self.assertEqual(zinfo.date_time, (2107, 12, 31, 23, 59, 58))


class TestZipFileExt(unittest.TestCase):
    def test_init(self):
        fh = io.BytesIO()

        # Enforce strict_timestamps=False
        with zipfile.ZipFile(fh, 'w', strict_timestamps=True) as zh:
            self.assertEqual(zh._strict_timestamps, False)
            zh._strict_timestamps = True
            self.assertEqual(zh._strict_timestamps, False)
            del zh._strict_timestamps
            self.assertEqual(zh._strict_timestamps, False)

        with zipfile.ZipFile(fh, strict_timestamps=True) as zh:
            self.assertEqual(zh._strict_timestamps, False)
            zh._strict_timestamps = True
            self.assertEqual(zh._strict_timestamps, False)
            del zh._strict_timestamps
            self.assertEqual(zh._strict_timestamps, False)

        # Ensure every member is read as ZipInfoExt.
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.writestr('file1.txt', 'foo')
            zh.mkdir('folder/')
            zh.writestr('folder/file2.txt', 'bar')

        with zipfile.ZipFile(fh) as zh:
            self.assertIsInstance(zh.getinfo('file1.txt'), zipfile.ZipInfoExt)
            self.assertIsInstance(zh.getinfo('folder/'), zipfile.ZipInfoExt)
            self.assertIsInstance(zh.getinfo('folder/file2.txt'), zipfile.ZipInfoExt)

    def test_open(self):
        fh = io.BytesIO()
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.writestr('file.txt', 'foo')

        # read with ZipInfoExt
        with zipfile.ZipFile(fh) as zh:
            def m_open(zf, name, mode, *args, **kwargs):
                self.assertEqual(zf, zh)
                self.assertIsInstance(name, zipfile.ZipInfoExt)
                self.assertIs(name, zinfo)
                self.assertEqual(mode, 'r')
                self.assertEqual(args, ())
                self.assertEqual(kwargs, {})
                return nullcontext()

            zinfo = zipfile.ZipInfo('file.txt')
            with mock.patch('zipfile.ZipFile.open', m_open):
                with zh.open(zinfo):
                    pass

        # read with name
        with zipfile.ZipFile(fh) as zh:
            def m_open(zf, name, mode, *args, **kwargs):
                self.assertEqual(zf, zh)
                self.assertIsInstance(name, zipfile.ZipInfoExt)
                self.assertEqual(name.filename, 'file.txt')
                self.assertEqual(mode, 'r')
                self.assertEqual(args, ())
                self.assertEqual(kwargs, {})
                return nullcontext()

            with mock.patch('zipfile.ZipFile.open', m_open):
                with zh.open('file.txt'):
                    pass

        # write with ZipInfoExt
        with zipfile.ZipFile(fh, 'w') as zh:
            def m_open(zf, name, mode, *args, **kwargs):
                self.assertEqual(zf, zh)
                self.assertIsInstance(name, zipfile.ZipInfoExt)
                self.assertIs(name, zinfo)
                self.assertEqual(mode, 'w')
                self.assertEqual(args, ())
                self.assertEqual(kwargs, {})
                return nullcontext()

            zinfo = zipfile.ZipInfo('file.txt')
            with mock.patch('zipfile.ZipFile.open', m_open):
                with zh.open(zinfo, 'w'):
                    pass

        # write with name
        with zipfile.ZipFile(fh, 'w') as zh:
            def m_open(zf, name, mode, *args, **kwargs):
                self.assertEqual(zf, zh)
                self.assertIsInstance(name, zipfile.ZipInfoExt)
                self.assertEqual(name.filename, 'file.txt')
                self.assertEqual(mode, 'w')
                self.assertEqual(args, ())
                self.assertEqual(kwargs, {})
                return nullcontext()

            with mock.patch('zipfile.ZipFile.open', m_open):
                with zh.open('file.txt', 'w'):
                    pass

    def test_writestr(self):
        fh = io.BytesIO()

        # check passed arguments when passing ZipInfoExt
        with zipfile.ZipFile(fh, 'w') as zh:
            def m_writestr(zf, member, data, *args, **kwargs):
                self.assertEqual(zf, zh)
                self.assertIsInstance(member, zipfile.ZipInfoExt)
                self.assertIs(member, zinfo)
                self.assertIs(data, 'foo')
                self.assertEqual(args, ())
                self.assertEqual(kwargs, {})

            zinfo = zipfile.ZipInfo('file.txt')
            with mock.patch('zipfile.ZipFile.writestr', m_writestr):
                zh.writestr(zinfo, 'foo')

        # check passed arguments when passing arcname
        with zipfile.ZipFile(fh, 'w') as zh:
            def m_writestr(zf, member, data, *args, **kwargs):
                self.assertEqual(zf, zh)
                self.assertIsInstance(member, zipfile.ZipInfoExt)
                self.assertEqual(member.filename, 'file.txt')
                self.assertIs(data, 'foo')
                self.assertEqual(args, ())
                self.assertEqual(kwargs, {})

            with mock.patch('zipfile.ZipFile.writestr', m_writestr):
                zh.writestr('file.txt', 'foo')

        # should write folder with mode 0x40775
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.writestr('folder/', b'')
            zinfo = zh.getinfo('folder/')
            self.assertEqual(oct(zip_mode(zinfo)), '0o40775')

        # should write file with mode 0o600
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.writestr('file.txt', b'foo')
            zinfo = zh.getinfo('file.txt')
            self.assertEqual(oct(zip_mode(zinfo)), '0o600')

    def test_mkdir(self):
        fh = io.BytesIO()

        # ZipInfoExt('folder/')
        zinfo = zipfile.ZipInfo('foo/')
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.mkdir(zinfo)
        with zipfile.ZipFile(fh) as zh:
            zinfo = zh.getinfo('foo/')
            self.assertEqual(zinfo.file_size, 0)
            self.assertEqual(zinfo.compress_size, 0)
            self.assertEqual(zinfo.CRC, 0)

        # ZipInfoExt('folder') should raise
        zinfo = zipfile.ZipInfo('foo')
        with zipfile.ZipFile(fh, 'w') as zh:
            with self.assertRaises(ValueError):
                zh.mkdir(zinfo)

        # folder/
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.mkdir('foo/')
        with zipfile.ZipFile(fh) as zh:
            zinfo = zh.getinfo('foo/')
            self.assertEqual(zinfo.file_size, 0)
            self.assertEqual(zinfo.compress_size, 0)
            self.assertEqual(zinfo.CRC, 0)
            self.assertEqual(oct(zip_mode(zinfo)), '0o40777')

        # folder
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.mkdir('foo')
        with zipfile.ZipFile(fh) as zh:
            zinfo = zh.getinfo('foo/')
            self.assertEqual(zinfo.file_size, 0)
            self.assertEqual(zinfo.compress_size, 0)
            self.assertEqual(zinfo.CRC, 0)
            self.assertEqual(oct(zip_mode(zinfo)), '0o40777')


if __name__ == '__main__':
    unittest.main()
