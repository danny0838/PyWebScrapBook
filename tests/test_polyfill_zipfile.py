import io
import os
import struct
import tempfile
import time
import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest import mock

from webscrapbook._polyfill import zipfile

from . import (
    DUMMY_TS,
    DUMMY_TS2,
    DUMMY_TS3,
    DUMMY_TS4,
    DUMMY_TS5,
    DUMMY_TS_NS,
    DUMMY_TS_NS2,
    DUMMY_TS_NS3,
    DUMMY_TS_NS4,
    DUMMY_ZIP_DT,
    TEMP_DIR,
)


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='polyfill.zipfile-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)


def tearDownModule():
    # cleanup the temp directory
    _tmpdir.cleanup()


class TestZipInfoExt(unittest.TestCase):
    def test_init(self):
        # default to current datetime if not provided
        with mock.patch('time.time_ns', return_value=DUMMY_TS_NS):
            zinfo = zipfile.ZipInfo()
            self.assertEqual(zinfo.date_time, DUMMY_ZIP_DT)

        # default to 0o40775 for folders
        zinfo = zipfile.ZipInfo('folder/')
        self.assertEqual(zinfo.external_attr, (0o40775 << 16) | 0x10)

        # tidy bad bits and apply dmask for folders
        zinfo = zipfile.ZipInfo('folder/', mode=0o777777, dmask=0)
        self.assertEqual(zinfo.external_attr, (0o47777 << 16) | 0x10)

        # default to 0o100600 for files
        zinfo = zipfile.ZipInfo('file.txt')
        self.assertEqual(zinfo.external_attr, 0o100600 << 16)

        # tidy bad bits and apply fmask for files
        zinfo = zipfile.ZipInfo('file.txt', mode=0o777777, fmask=0)
        self.assertEqual(zinfo.external_attr, 0o107777 << 16)

    def test_get_datetime(self):
        # date_time
        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = b''
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS, DUMMY_TS_NS),
        )

        # NTFS Extra Field
        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = struct.pack(
            '<HHLHHQQQ', 0x000a, 32,
            0, 0x0001, 24,
            DUMMY_TS_NS2 // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            DUMMY_TS_NS3 // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            DUMMY_TS_NS4 // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
        )
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS3, DUMMY_TS_NS2),
        )

        # Extended timestamp (UT)
        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = struct.pack('<HHBL', 0x5455, 5, 1, int(DUMMY_TS2))
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS2, DUMMY_TS_NS2),
        )

        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = struct.pack('<HHBLL', 0x5455, 9, 3, int(DUMMY_TS2), int(DUMMY_TS3))
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS2, DUMMY_TS_NS2),
        )

        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = struct.pack('<HHBL', 0x5455, 5, 2, int(DUMMY_TS2))
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS, DUMMY_TS_NS),
        )

        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = struct.pack('<HHB', 0x5455, 1, 0)
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS, DUMMY_TS_NS),
        )

        # Unix1 (0x5855)
        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = struct.pack('<HHLL', 0x5855, 8, int(DUMMY_TS2), int(DUMMY_TS3))
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS2, DUMMY_TS_NS3),
        )

        # Unix0 (0x000d)
        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = struct.pack('<HHLLHH', 0x000d, 12, int(DUMMY_TS2), int(DUMMY_TS3), 0, 0)
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS2, DUMMY_TS_NS3),
        )

        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = struct.pack('<HHLLHH3s', 0x000d, 15, int(DUMMY_TS2), int(DUMMY_TS3), 1, 2, b'foo')
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS2, DUMMY_TS_NS3),
        )

        # NTFS > UT
        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = b''.join((
            struct.pack(
                '<HHLHHQQQ', 0x000a, 32,
                0, 0x0001, 24,
                DUMMY_TS_NS2 // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
                DUMMY_TS_NS3 // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
                DUMMY_TS_NS4 // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ),
            struct.pack('<HHBL', 0x5455, 5, 1, int(DUMMY_TS5)),
        ))
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS3, DUMMY_TS_NS2),
        )

        # UT > Unix1
        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = b''.join((
            struct.pack('<HHBL', 0x5455, 5, 1, int(DUMMY_TS2)),
            struct.pack('<HHLL', 0x5855, 8, int(DUMMY_TS3), int(DUMMY_TS4)),
        ))
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS2, DUMMY_TS_NS2),
        )

        # Unix1 > Unix0
        zinfo = zipfile.ZipInfo()
        zinfo.date_time = DUMMY_ZIP_DT
        zinfo.extra = b''.join((
            struct.pack('<HHLL', 0x5855, 8, int(DUMMY_TS2), int(DUMMY_TS3)),
            struct.pack('<HHLLHH', 0x000d, 12, int(DUMMY_TS4), int(DUMMY_TS5), 0, 0)
        ))
        self.assertEqual(
            zinfo._get_datetime(),
            (DUMMY_TS_NS2, DUMMY_TS_NS3),
        )

    def test_set_datetime_params(self):
        zinfo = zipfile.ZipInfo()

        # not set
        with mock.patch('time.time_ns', return_value=DUMMY_TS_NS):
            zinfo._set_datetime()
        self.assertEqual(zinfo.date_time, DUMMY_ZIP_DT)
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, DUMMY_TS_NS // 10 ** 9
        ))

        # None
        with mock.patch('time.time_ns', return_value=DUMMY_TS_NS):
            zinfo._set_datetime(None)
        self.assertEqual(zinfo.date_time, DUMMY_ZIP_DT)
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, DUMMY_TS_NS // 10 ** 9
        ))

        # float
        self.assertIsInstance(DUMMY_TS, float)
        zinfo._set_datetime(DUMMY_TS)
        self.assertEqual(zinfo.date_time, DUMMY_ZIP_DT)
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, DUMMY_TS_NS // 10 ** 9
        ))

        # int
        self.assertIsInstance(DUMMY_TS_NS, int)
        zinfo._set_datetime(DUMMY_TS_NS)
        self.assertEqual(zinfo.date_time, DUMMY_ZIP_DT)
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, DUMMY_TS_NS // 10 ** 9
        ))

        # os.stat_result
        root = tempfile.mkdtemp(dir=tmpdir)
        file = os.path.join(root, 'file.txt')
        with open(file, 'wb'):
            pass
        os.utime(file, ns=(DUMMY_TS_NS2, DUMMY_TS_NS))
        st = os.stat(file)

        zinfo._set_datetime(st)
        self.assertEqual(zinfo.date_time, DUMMY_ZIP_DT)
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, DUMMY_TS_NS // 10 ** 9
        ))

        # ZIP date_time tuple
        zinfo._set_datetime(DUMMY_ZIP_DT)
        self.assertEqual(zinfo.date_time, DUMMY_ZIP_DT)
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, DUMMY_TS_NS // 10 ** 9
        ))

    def test_set_datetime_extras(self):
        # should append new fields
        dt = datetime(2038, 1, 19, 3, 14, 7, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()
        zinfo.extra = b''.join((
            struct.pack('<HH', 0xf001, 0),
        ))
        zinfo._set_datetime(ts)
        extras = [extra for extra, _ in zipfile._Extra.iter(zinfo.extra)]
        self.assertEqual(extras, [
            struct.pack('<HH', 0xf001, 0),
            struct.pack('<HHBL', 0x5455, 5, 1, ts // 10 ** 9),
        ])

        # should append new fields but before the invalid tail
        dt = datetime(2038, 1, 19, 3, 14, 7, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()
        zinfo.extra = b''.join((
            struct.pack('<HH', 0xf001, 0),
            b'zzz',
        ))
        zinfo._set_datetime(ts)
        extras = [extra for extra, _ in zipfile._Extra.iter(zinfo.extra)]
        self.assertEqual(extras, [
            struct.pack('<HH', 0xf001, 0),
            struct.pack('<HHBL', 0x5455, 5, 1, ts // 10 ** 9),
            b'zzz',
        ])

        # should update fields in the original order
        # should update NTFS field if exists
        dt = datetime(2038, 1, 19, 3, 14, 7, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()
        zinfo.extra = b''.join((
            struct.pack('<HH', 0xf001, 0),
            struct.pack('<HH', 0x5455, 0),
            struct.pack('<HH', 0xf002, 0),
            struct.pack('<HH', 0x000a, 0),
            struct.pack('<HH', 0xf003, 0),
            b'zzz',
        ))
        zinfo._set_datetime(ts)
        extras = [extra for extra, _ in zipfile._Extra.iter(zinfo.extra)]
        self.assertEqual(extras, [
            struct.pack('<HH', 0xf001, 0),
            struct.pack('<HHBL', 0x5455, 5, 1, ts // 10 ** 9),
            struct.pack('<HH', 0xf002, 0),
            struct.pack(
                '<HHLHHQQQ', 0x000a, 32, 0, 0x0001, 24,
                ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
                ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
                ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ),
            struct.pack('<HH', 0xf003, 0),
            b'zzz',
        ])

        # should strip duplicated fields
        dt = datetime(2038, 1, 19, 3, 14, 7, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()
        zinfo.extra = b''.join((
            struct.pack('<HH', 0x5455, 0),
            struct.pack('<HHBL', 0x5455, 5, 1, 0),
            struct.pack('<HH', 0x000a, 0),
            struct.pack('<HHLHHQQQ', 0x000a, 32, 0, 0x0001, 24, 0, 0, 0),
        ))
        zinfo._set_datetime(ts)
        extras = [extra for extra, _ in zipfile._Extra.iter(zinfo.extra)]
        self.assertEqual(extras, [
            struct.pack('<HHBL', 0x5455, 5, 1, ts // 10 ** 9),
            struct.pack(
                '<HHLHHQQQ', 0x000a, 32, 0, 0x0001, 24,
                ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
                ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
                ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ),
        ])

        # should strip existing fields if no more valid
        dt = datetime(1600, 12, 31, 23, 59, 59, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()
        zinfo.extra = b''.join((
            struct.pack('<HHLHHQQQ', 0x000a, 32,
                        0, 0x0001, 24, 0x7777_7777, 0x7777_7777, 0x7777_7777),
            struct.pack('<HHBL', 0x5455, 5, 0x01, 0x7777),
            struct.pack('<HH', 0xf001, 0),
            b'zzz',
        ))
        zinfo._set_datetime(ts)
        extras = [extra for extra, _ in zipfile._Extra.iter(zinfo.extra)]
        self.assertEqual(extras, [
            struct.pack('<HH', 0xf001, 0),
            b'zzz',
        ])

    def test_set_datetime_special_dt(self):
        # before 1601-01-01T00:00:00Z (NTFS min)
        dt = datetime(1600, 12, 31, 23, 59, 59, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, (1980, 1, 1, 0, 0, 0))
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [])

        # before 1970-01-01T00:00:00Z (UT min)
        dt = datetime(1601, 1, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, (1980, 1, 1, 0, 0, 0))
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x000a])
        self.assertEqual(struct.unpack('<HHLHHQQQ', extras.get(0x000a)), (
            0x000a, 32, 0, 0x0001, 24,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
        ))

        dt = datetime(1969, 12, 31, 23, 59, 59, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, (1980, 1, 1, 0, 0, 0))
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x000a])
        self.assertEqual(struct.unpack('<HHLHHQQQ', extras.get(0x000a)), (
            0x000a, 32, 0, 0x0001, 24,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
        ))

        # before local 1980-01-01 00:00:00 (DOS min)
        dt = datetime(1979, 12, 30, 23, 59, 59, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, (1980, 1, 1, 0, 0, 0))
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x5455])
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, ts // 10 ** 9
        ))

        # normal
        dt = datetime(2038, 1, 19, 3, 14, 7, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, time.localtime(ts // 10 ** 9)[:6])
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x5455])
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, ts // 10 ** 9
        ))

        # after 2038-01-19T03:14:07Z (UT max if signed)
        dt = datetime(2038, 1, 19, 3, 14, 8, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, time.localtime(ts // 10 ** 9)[:6])
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x5455])
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, ts // 10 ** 9
        ))

        dt = datetime(2106, 2, 7, 6, 28, 15, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, time.localtime(ts // 10 ** 9)[:6])
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x5455])
        self.assertEqual(struct.unpack('<HHBL', extras.get(0x5455)), (
            0x5455, 5, 1, ts // 10 ** 9
        ))

        # after 2106-02-07T06:28:15Z (UT max)
        dt = datetime(2106, 2, 7, 6, 28, 16, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, time.localtime(ts // 10 ** 9)[:6])
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x000a])
        self.assertEqual(struct.unpack('<HHLHHQQQ', extras.get(0x000a)), (
            0x000a, 32, 0, 0x0001, 24,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
        ))

        dt = datetime(2107, 12, 31, 0, 0, 0, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, time.localtime(ts // 10 ** 9)[:6])
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x000a])
        self.assertEqual(struct.unpack('<HHLHHQQQ', extras.get(0x000a)), (
            0x000a, 32, 0, 0x0001, 24,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
        ))

        # after local 2107-12-31 23:59:59 (DOS max)
        dt = datetime(2108, 1, 2, 0, 0, 0, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, (2107, 12, 31, 23, 59, 58))
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x000a])
        self.assertEqual(struct.unpack('<HHLHHQQQ', extras.get(0x000a)), (
            0x000a, 32, 0, 0x0001, 24,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
        ))

        dt = datetime(2300, 1, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, (2107, 12, 31, 23, 59, 58))
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [0x000a])
        self.assertEqual(struct.unpack('<HHLHHQQQ', extras.get(0x000a)), (
            0x000a, 32, 0, 0x0001, 24,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
            ts // 100 + zipfile.WIN_TICKS_FROM_EPOCH,
        ))

        # after NTFS max
        ts = ((1 << 64) - zipfile.WIN_TICKS_FROM_EPOCH) * 100
        zinfo = zipfile.ZipInfo()._set_datetime(ts)
        self.assertEqual(zinfo.date_time, (2107, 12, 31, 23, 59, 58))
        extras = {tp: extra for extra, tp in zipfile._Extra.iter(zinfo.extra)}
        self.assertEqual(list(extras), [])

    def test_set_datetime_legacy_fields(self):
        """Update or clear legacy fields if exists."""
        dt = datetime(2038, 1, 19, 3, 14, 7, 123456, tzinfo=timezone.utc)
        ts = int(dt.timestamp() * 10 ** 9)
        zinfo = zipfile.ZipInfo()
        zinfo.extra = b''.join((
            struct.pack('<HHLL', 0x5855, 8, int(DUMMY_TS2), int(DUMMY_TS3)),
            struct.pack('<HHLLHH3s', 0x000d, 15, int(DUMMY_TS4), int(DUMMY_TS5), 1, 2, b'foo'),
        ))
        zinfo._set_datetime(ts)
        extras = [extra for extra, _ in zipfile._Extra.iter(zinfo.extra)]
        self.assertEqual(extras, [
            struct.pack('<HHLLHH3s', 0x000d, 15, ts // 10 ** 9, ts // 10 ** 9, 1, 2, b'foo'),
            struct.pack('<HHBL', 0x5455, 5, 1, ts // 10 ** 9),
        ])


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
            self.assertEqual(oct(zinfo._get_mode()), '0o40775')

        # should write file with mode 0o600
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.writestr('file.txt', b'foo')
            zinfo = zh.getinfo('file.txt')
            self.assertEqual(oct(zinfo._get_mode()), '0o100600')

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
            self.assertEqual(oct(zinfo._get_mode()), '0o40775')

        # folder
        with zipfile.ZipFile(fh, 'w') as zh:
            zh.mkdir('foo')
        with zipfile.ZipFile(fh) as zh:
            zinfo = zh.getinfo('foo/')
            self.assertEqual(zinfo.file_size, 0)
            self.assertEqual(zinfo.compress_size, 0)
            self.assertEqual(zinfo.CRC, 0)
            self.assertEqual(oct(zinfo._get_mode()), '0o40775')

    def test_set_compression(self):
        fh = io.BytesIO()

        # default compression to None
        # use default compresslevel for the autocompressor
        with zipfile.ZipFile(fh, 'w') as zh:
            self.assertEqual(zh.compression, None)
            self.assertEqual(zh.compresslevel, None)

            zinfo = zipfile.ZipInfo('foo.txt')
            zh._set_compression(zinfo)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_DEFLATED)
            self.assertEqual(zinfo._compresslevel, 9)

            zinfo = zipfile.ZipInfo('foo.jpg')
            zh._set_compression(zinfo)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(zinfo._compresslevel, None)

        with zipfile.ZipFile(fh, 'w', compression=None) as zh:
            self.assertEqual(zh.compression, None)
            self.assertEqual(zh.compresslevel, None)

        # suggest compresslevel for the autocompressor if set
        with zipfile.ZipFile(fh, 'w', compresslevel=6) as zh:
            zinfo = zipfile.ZipInfo('foo.txt')
            zh._set_compression(zinfo)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_DEFLATED)
            self.assertEqual(zinfo._compresslevel, 6)

            zinfo = zipfile.ZipInfo('foo.jpg')
            zh._set_compression(zinfo)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(zinfo._compresslevel, None)

        # take compression if set
        # take compresslevel
        with zipfile.ZipFile(fh, 'w', compression=zipfile.ZIP_DEFLATED) as zh:
            zinfo = zipfile.ZipInfo('foo.txt')
            zh._set_compression(zinfo)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_DEFLATED)
            self.assertEqual(zinfo._compresslevel, None)

            zinfo = zipfile.ZipInfo('foo.jpg')
            zh._set_compression(zinfo)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_DEFLATED)
            self.assertEqual(zinfo._compresslevel, None)

        with zipfile.ZipFile(fh, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as zh:
            zinfo = zipfile.ZipInfo('foo.txt')
            zh._set_compression(zinfo)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_DEFLATED)
            self.assertEqual(zinfo._compresslevel, 4)

            zinfo = zipfile.ZipInfo('foo.jpg')
            zh._set_compression(zinfo)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_DEFLATED)
            self.assertEqual(zinfo._compresslevel, 4)

    def test_extract(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, 'w') as zh:
            zinfo = zipfile.ZipInfo('file.txt', DUMMY_TS_NS)
            zh.writestr(zinfo, b'foo')
            zh.extract(zinfo, root)
        dst = os.path.join(root, zinfo.filename)
        self.assertTrue(os.path.isfile(dst))
        st = os.stat(dst)
        self.assertEqual(st.st_size, zinfo.file_size)
        self.assertEqual(st.st_mtime_ns, DUMMY_TS_NS)

        with zipfile.ZipFile(buf, 'w') as zh:
            zinfo = zipfile.ZipInfo('folder/', DUMMY_TS_NS2)
            zh.mkdir(zinfo)
            zh.extract(zinfo, root)
        dst = os.path.join(root, zinfo.filename)
        self.assertTrue(os.path.isdir(dst))
        st = os.stat(os.path.join(root, zinfo.filename))
        self.assertEqual(st.st_mtime_ns, DUMMY_TS_NS2)

    def test_extractall(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, 'w') as zh:
            zinfo1 = zipfile.ZipInfo('folder/', DUMMY_TS_NS)
            zh.mkdir(zinfo1)

            zinfo2 = zipfile.ZipInfo('folder/file2.txt', DUMMY_TS_NS2)
            zh.writestr(zinfo2, b'foo')

            zinfo3 = zipfile.ZipInfo('implicit_folder/file3.txt', DUMMY_TS_NS3)
            zh.writestr(zinfo3, b'bar')

            zh.extractall(root)

        dst = os.path.join(root, zinfo1.filename)
        self.assertTrue(os.path.isdir(dst))
        st = os.stat(dst)
        self.assertEqual(st.st_mtime_ns, DUMMY_TS_NS)

        dst = os.path.join(root, zinfo2.filename)
        self.assertTrue(os.path.isfile(dst))
        st = os.stat(dst)
        self.assertEqual(st.st_size, zinfo2.file_size)
        self.assertEqual(st.st_mtime_ns, DUMMY_TS_NS2)

        dst = os.path.join(root, 'implicit_folder')
        self.assertTrue(os.path.isdir(dst))
        st = os.stat(dst)
        self.assertAlmostEqual(st.st_mtime_ns, time.time_ns(), delta=10 ** 9)

        dst = os.path.join(root, zinfo3.filename)
        self.assertTrue(os.path.isfile(dst))
        st = os.stat(dst)
        self.assertEqual(st.st_size, zinfo3.file_size)
        self.assertEqual(st.st_mtime_ns, DUMMY_TS_NS3)

    def test_extractall_error_handling(self):
        """Should skip OSError when restoring attributes."""
        root = tempfile.mkdtemp(dir=tmpdir)
        buf = io.BytesIO()

        def m_err(*a, **k):
            raise OSError('dummy OSError')

        with zipfile.ZipFile(buf, 'w') as zh:
            zinfo1 = zipfile.ZipInfo('file1.txt', DUMMY_TS_NS)
            zh.writestr(zinfo1, b'foo')

            zinfo2 = zipfile.ZipInfo('file2.txt', DUMMY_TS_NS2)
            zh.writestr(zinfo2, b'bar')

            with mock.patch('os.utime', side_effect=m_err):
                zh.extractall(root)

        dst = os.path.join(root, zinfo1.filename)
        self.assertTrue(os.path.isfile(dst))
        st = os.stat(dst)
        self.assertEqual(st.st_size, zinfo1.file_size)
        self.assertAlmostEqual(st.st_mtime_ns, time.time_ns(), delta=10 ** 9)

        dst = os.path.join(root, zinfo2.filename)
        self.assertTrue(os.path.isfile(dst))
        st = os.stat(dst)
        self.assertEqual(st.st_size, zinfo2.file_size)
        self.assertAlmostEqual(st.st_mtime_ns, time.time_ns(), delta=10 ** 9)


if __name__ == '__main__':
    unittest.main()
