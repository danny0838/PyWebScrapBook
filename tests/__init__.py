import glob
import os
import platform
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime

import webscrapbook
from webscrapbook import util
from webscrapbook._polyfill import zipfile
from webscrapbook.util.fs import zip_timestamp

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

PROG_DIR = os.path.abspath(os.path.dirname(webscrapbook.__file__))

# The root directory for placing temp directories and files.
# None for auto-detection from the local system.
TEMP_DIR = None

DUMMY_BYTES = 'Lorem ipsum dolor sit amet 崽芺穵縡葥螑扤一鈜珽凈竻氻衶乇'.encode('UTF-8')
DUMMY_BYTES1 = 'Duis aute irure dolor 傜帙伔鮈鳭魻邘一崷絊珖旽忉俉屮'.encode('UTF-8')
DUMMY_BYTES2 = 'Quisque quis maximus dui. 毌狴极脞洝爣滒鉡邔扥垵犽炂妺庉瘃丌秅僔跬。'.encode('UTF-8')
DUMMY_BYTES3 = ('Proin porta ante tortor, dapibus venenatis sem volutpat vel. '
                '梊佫朸縟蛵錂邗一堥婃戙咇屳昴乇，滉揘兀杶秖楱呯氕屮佷綧柊仂芺。').encode('UTF-8')
DUMMY_BYTES4 = ('Proin porta ante tortor, dapibus venenatis sem volutpat vel.'
                'Donec imperdiet rutrum tellus, nec scelerisque turpis finibus id.'
                'In suscipit imperdiet eros ac interdum. Nullam porttitor vestibulum ultrices.'
                '梊佫朸縟蛵錂邗一堥婃戙咇屳昴乇，滉揘兀杶秖楱呯氕屮佷綧柊仂芺。'
                '稂侄仵諤溠糑匟一菆崌浯玠肊洼乇，嵊裋屮迕勀戣岤仜亍玤滫峗尐沴。'
                '烺一柶粘崵溡乇碤澯旡，捰乜玸惃愓溙乇榞旡宄。').encode('UTF-8')

# compatible with os.stat_result.st_mtime or os.utime
DUMMY_TS = datetime(1990, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS1 = datetime(1991, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS2 = datetime(1992, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS3 = datetime(1993, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS4 = datetime(1994, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS5 = datetime(1995, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS6 = datetime(1996, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS7 = datetime(1997, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS8 = datetime(1998, 1, 2, 0, 0, 0).timestamp()
DUMMY_TS9 = datetime(1999, 1, 2, 0, 0, 0).timestamp()

# compatible with ZipInfo.date_time
# corresponds to above DUMMY_TS
DUMMY_ZIP_DT = (1990, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT1 = (1991, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT2 = (1992, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT3 = (1993, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT4 = (1994, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT5 = (1995, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT6 = (1996, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT7 = (1997, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT8 = (1998, 1, 2, 0, 0, 0)
DUMMY_ZIP_DT9 = (1999, 1, 2, 0, 0, 0)


# common requirement checking decorators
def require_sep(reason="requires '/' as filesystem path separator "
                       '(e.g. POSIX)'):
    support = os.sep == '/'
    return unittest.skipUnless(support, reason)


def require_case_insensitive(reason='requires case insensitive filesystem '
                                    '(e.g. Windows)'):
    support = os.path.normcase('ABC') == os.path.normcase('abc')
    return unittest.skipUnless(support, reason)


def require_posix_mode(reason='requires POSIX mode support'):
    support = os.name == 'posix'
    return unittest.skipUnless(support, reason)


def require_junction(reason='requires junction creation support'):
    support = platform.system() == 'Windows'
    return unittest.skipUnless(support, reason)


def require_junction_deletion(reason='requires good junction deletion support '
                                     '(e.g. Python >= 3.8)'):
    support = sys.version_info >= (3, 8)
    return unittest.skipUnless(support, reason)


def require_symlink(reason='requires symlink creation support '
                           '(Windows requires Administrator or Developer Mode)'):
    try:
        support = require_symlink.support
    except AttributeError:
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.symlink(__file__, os.path.join(tmpdir, 'temp.link'))
            except OSError:
                support = False
            else:
                support = True
        require_symlink.support = support
    return unittest.skipUnless(support, reason)


@contextmanager
def test_file_cleanup(*paths):
    """Call os.remove() afterwards for given paths.

    - Mainly to prevent tree cleanup issue for junctions in Python 3.7
    """
    try:
        yield
    finally:
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass


def glob_files(path):
    """Get a set of files and directories under the path (inclusive).

    - Note that the path itself in the glob result will be appended an os.sep,
      and shuould usually be matched with os.path.join(path, '')
    - Hidden ('.'-leading) files are not included unless include_hidden=True,
      which is supported since Python 3.11, is provided to glob.

    Returns:
        set: files and directories under the path (inclusive)
    """
    return {*glob.iglob(os.path.join(glob.escape(path), '**'), recursive=True)}


class TestFileMixin:
    """A mixin class for unittest.TestCase to support file testing utilities"""
    @staticmethod
    def get_file_data(data, follow_symlinks=False):
        """Convert file data to a comparable format.

        Args:
            data: a dict with {'bytes': bytes, 'stat': os.stat_result or zipfile.ZipInfo}
                or {'file': cpath}
                or {'file': file-like}
                or {'zip': ZipFile, 'filename': str}
            follow_symlinks: whether to follow symlink (or junction) to get file stat
        """
        if 'file' in data:
            cpath = util.fs.CPath(data['file'])
            if len(cpath.path) == 1:
                file = cpath.file
                st = os.stat(file) if follow_symlinks else os.lstat(file)
                if os.path.isfile(file):
                    with open(file, 'rb') as fh:
                        bytes_ = fh.read()
                else:
                    bytes_ = None
                return {'stat': st, 'bytes': bytes_}
            else:
                with util.fs.open_archive_path(cpath) as zh:
                    try:
                        st = zh.getinfo(cpath[-1])
                    except KeyError:
                        try:
                            st = zh.getinfo(cpath[-1] + '/')
                        except KeyError:
                            st = bytes_ = None
                        else:
                            bytes_ = None
                    else:
                        bytes_ = zh.read(st)
                return {'stat': st, 'bytes': bytes_}
        elif 'zip' in data:
            try:
                st = data['zip'].getinfo(data['filename'])
            except KeyError:
                st = bytes_ = None
            else:
                bytes_ = None if st.is_dir() else data['zip'].read(st)
            return {'stat': st, 'bytes': bytes_}

        return data

    def assert_file_equal(self, *datas):
        """Assert if file datas are equivalent.

        Args:
            *datas: compatible data format with get_file_data()
        """
        # Such bits may be changed by the API when copying among ZIP files,
        # and we don't really care about them.
        excluded_flag_bits = 1 << 3

        datas = [self.get_file_data(data) for data in datas]
        for i in range(1, len(datas)):
            self.assertEqual(datas[0].get('bytes'), datas[i].get('bytes'), msg='bytes not equal')

            st0 = datas[0].get('stat')
            sti = datas[i].get('stat')

            if isinstance(st0, os.stat_result):
                if isinstance(sti, os.stat_result):
                    stat0 = {
                        'mode': st0.st_mode,
                        'uid': st0.st_uid,
                        'gid': st0.st_gid,
                        'mtime': st0.st_mtime,
                    }
                else:
                    stat0 = {
                        'mtime': st0.st_mtime,
                    }

            elif isinstance(st0, zipfile.ZipInfo):
                if isinstance(sti, zipfile.ZipInfo):
                    stat0 = {
                        'mtime': zip_timestamp(st0),
                        'compress_type': st0.compress_type,
                        'comment': st0.comment,
                        'extra': st0.extra,
                        'flag_bits': st0.flag_bits & ~excluded_flag_bits,
                        'internal_attr': st0.internal_attr,
                        'external_attr': st0.external_attr,
                    }
                else:
                    stat0 = {
                        'mtime': zip_timestamp(st0),
                    }
            else:
                stat0 = {}

            if isinstance(sti, os.stat_result):
                if isinstance(st0, os.stat_result):
                    stati = {
                        'mode': sti.st_mode,
                        'uid': sti.st_uid,
                        'gid': sti.st_gid,
                        'mtime': sti.st_mtime,
                    }
                else:
                    stati = {
                        'mtime': sti.st_mtime,
                    }

            elif isinstance(sti, zipfile.ZipInfo):
                if isinstance(st0, zipfile.ZipInfo):
                    stati = {
                        'mtime': zip_timestamp(sti),
                        'compress_type': sti.compress_type,
                        'comment': sti.comment,
                        'extra': sti.extra,
                        'flag_bits': sti.flag_bits & ~excluded_flag_bits,
                        'internal_attr': sti.internal_attr,
                        'external_attr': sti.external_attr,
                    }
                else:
                    stati = {
                        'mtime': zip_timestamp(sti),
                    }
            else:
                stati = {}

            for i in {*stat0, *stati}:
                if i == 'mtime':
                    self.assertAlmostEqual(stat0.get(i), stati.get(i), delta=2, msg=f"stat['{i}'] not equal")
                else:
                    self.assertEqual(stat0.get(i), stati.get(i), msg=f"stat['{i}'] not equal")
