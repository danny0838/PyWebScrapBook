import glob
import os
import platform
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime

import webscrapbook

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
