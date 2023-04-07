import functools
import io
import itertools
import os
import platform
import sys
import tempfile
import unittest
import warnings
from datetime import datetime
from unittest import mock

from webscrapbook import util
from webscrapbook._polyfill import zipfile
from webscrapbook.util.fs import zip_mode, zip_timestamp

from . import (
    DUMMY_BYTES,
    DUMMY_BYTES2,
    DUMMY_TS,
    DUMMY_TS2,
    DUMMY_TS3,
    DUMMY_TS4,
    DUMMY_TS5,
    DUMMY_TS6,
    DUMMY_ZIP_DT,
    DUMMY_ZIP_DT2,
    DUMMY_ZIP_DT3,
    DUMMY_ZIP_DT4,
    SYMLINK_SUPPORTED,
    TEMP_DIR,
    glob_files,
    test_file_cleanup,
)


def setUpModule():
    """Set up a temp directory for testing."""
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='util.fs-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)


def tearDownModule():
    """Cleanup the temp directory."""
    _tmpdir.cleanup()


class TestCPath(unittest.TestCase):
    def test_init(self):
        self.assertSequenceEqual(
            util.fs.CPath(r'C:\Users\Myname\myfile.txt'),
            [r'C:\Users\Myname\myfile.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath('/path/to/myfile.txt'),
            ['/path/to/myfile.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath(['/path/to/archive.zip', 'subfile.txt']),
            ['/path/to/archive.zip', 'subfile.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath(('/path/to/archive.zip', 'subfile.txt')),
            ['/path/to/archive.zip', 'subfile.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath({'/path/to/archive.zip': True, 'subfile.txt': None}),
            ['/path/to/archive.zip', 'subfile.txt'],
        )

        # subpaths
        self.assertSequenceEqual(
            util.fs.CPath('/path/to/archive.zip', 'subarchive.zip', 'subfile.txt'),
            ['/path/to/archive.zip', 'subarchive.zip', 'subfile.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath(['/path/to/archive.zip', 'subarchive.zip'], 'subfile.txt'),
            ['/path/to/archive.zip', 'subarchive.zip', 'subfile.txt'],
        )

        # singleton for CPath without subpaths
        cpath = util.fs.CPath('/path/to/archive.zip', 'subfile.txt')
        cpath2 = util.fs.CPath(cpath)
        self.assertIs(cpath2, cpath)

        # new instance for CPath with subpath(s)
        cpath = util.fs.CPath('/path/to/archive.zip', 'subarchive.zip')
        cpath2 = util.fs.CPath(cpath, 'subfile.txt')
        self.assertIsNot(cpath2, cpath)
        self.assertSequenceEqual(
            cpath,
            ['/path/to/archive.zip', 'subarchive.zip'],
        )
        self.assertSequenceEqual(
            cpath2,
            ['/path/to/archive.zip', 'subarchive.zip', 'subfile.txt'],
        )

    def test_str(self):
        self.assertSequenceEqual(
            str(util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt')),
            r'C:\Users\Myname\archive.zip!/subfile.txt',
        )
        self.assertSequenceEqual(
            str(util.fs.CPath('/path/to/archive.zip', 'subfile.txt')),
            '/path/to/archive.zip!/subfile.txt',
        )

    def test_repr(self):
        self.assertSequenceEqual(
            repr(util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt')),
            r"CPath('C:\\Users\\Myname\\archive.zip', 'subfile.txt')",
        )
        self.assertSequenceEqual(
            repr(util.fs.CPath('/path/to/archive.zip', 'subfile.txt')),
            r"CPath('/path/to/archive.zip', 'subfile.txt')",
        )

    def test_getitem(self):
        self.assertSequenceEqual(
            util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt')[0],
            r'C:\Users\Myname\archive.zip',
        )
        self.assertSequenceEqual(
            util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt')[1],
            'subfile.txt',
        )
        self.assertSequenceEqual(
            util.fs.CPath('/path/to/archive.zip', 'subfile.txt')[0],
            '/path/to/archive.zip',
        )
        self.assertSequenceEqual(
            util.fs.CPath('/path/to/archive.zip', 'subfile.txt')[1],
            'subfile.txt',
        )
        self.assertEqual(
            list(iter(util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt'))),
            [r'C:\Users\Myname\archive.zip', 'subfile.txt'],
        )

    def test_len(self):
        self.assertEqual(
            len(util.fs.CPath(r'C:\Users\Myname\archive.zip')),
            1,
        )
        self.assertEqual(
            len(util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt')),
            2,
        )
        self.assertEqual(
            len(util.fs.CPath('/path/to/archive.zip')),
            1,
        )
        self.assertEqual(
            len(util.fs.CPath('/path/to/archive.zip', 'subfile.txt')),
            2,
        )

    def test_eq(self):
        self.assertEqual(
            util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt'),
            util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt'),
        )
        self.assertEqual(
            util.fs.CPath('/path/to/archive.zip', 'subfile.txt'),
            util.fs.CPath('/path/to/archive.zip', 'subfile.txt'),
        )

    def test_copy(self):
        cpath = util.fs.CPath('/path/to/archive.zip', 'subfile.txt')
        cpath2 = cpath.copy()
        self.assertIsNot(cpath2, cpath)
        self.assertSequenceEqual(
            cpath,
            ['/path/to/archive.zip', 'subfile.txt'],
        )
        self.assertSequenceEqual(
            cpath2,
            ['/path/to/archive.zip', 'subfile.txt'],
        )

    def test_path(self):
        self.assertSequenceEqual(
            util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt').path,
            [r'C:\Users\Myname\archive.zip', 'subfile.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath('/path/to/archive.zip', 'subfile.txt').path,
            [r'/path/to/archive.zip', 'subfile.txt'],
        )

    def test_file(self):
        self.assertSequenceEqual(
            util.fs.CPath(r'C:\Users\Myname\archive.zip', 'subfile.txt').file,
            r'C:\Users\Myname\archive.zip',
        )
        self.assertSequenceEqual(
            util.fs.CPath('/path/to/archive.zip', 'subfile.txt').file,
            r'/path/to/archive.zip',
        )

    def test_resolve1(self):
        """Basic logic for a sub-archive path."""
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip'),
            [os.path.join(root, 'entry.zip')],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!'),
            [os.path.join(root, 'entry.zip!')],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/'),
            [os.path.join(root, 'entry.zip'), '']
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/subdir'),
            [os.path.join(root, 'entry.zip'), 'subdir'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/subdir/'),
            [os.path.join(root, 'entry.zip'), 'subdir'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/index.html'),
            [os.path.join(root, 'entry.zip'), 'index.html'],
        )

    def test_resolve2(self):
        """Handle conflicting file or directory."""
        # entry.zip!/entry1.zip!/ = entry.zip!/entry1.zip! >
        # entry.zip!/entry1.zip >
        # entry.zip!/ = entry.zip! >
        # entry.zip

        # entry.zip!/entry1.zip!/ > entry.zip!/entry1.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        os.makedirs(os.path.join(root, 'entry.zip!', 'entry1.zip!'), exist_ok=True)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip!', 'entry1.zip'), 'w'):
            pass
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/'),
            [os.path.join(root, 'entry.zip!', 'entry1.zip!')],
        )

        # entry.zip!/entry1.zip! > entry.zip!/entry1.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        os.makedirs(os.path.join(root, 'entry.zip!'), exist_ok=True)
        with open(os.path.join(root, 'entry.zip!', 'entry1.zip!'), 'w'):
            pass
        with zipfile.ZipFile(os.path.join(root, 'entry.zip!', 'entry1.zip'), 'w'):
            pass
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/'),
            [os.path.join(root, 'entry.zip!', 'entry1.zip!')],
        )

        # entry.zip!/entry1.zip > entry.zip!/
        root = tempfile.mkdtemp(dir=tmpdir)
        os.makedirs(os.path.join(root, 'entry.zip!'), exist_ok=True)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip!', 'entry1.zip'), 'w'):
            pass
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/'),
            [os.path.join(root, 'entry.zip!', 'entry1.zip'), ''],
        )

        # entry.zip!/ > entry.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        os.makedirs(os.path.join(root, 'entry.zip!'), exist_ok=True)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/'),
            [os.path.join(root, 'entry.zip!', 'entry1.zip!')],
        )

        # entry.zip! > entry.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        with open(os.path.join(root, 'entry.zip!'), 'w'):
            pass
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/'),
            [os.path.join(root, 'entry.zip!', 'entry1.zip!')],
        )

        # entry.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!'],
        )

        # other
        root = tempfile.mkdtemp(dir=tmpdir)
        with open(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/'),
            [os.path.join(root, 'entry.zip!', 'entry1.zip!')],
        )

    def test_resolve3(self):
        """Handle recursive sub-archive path."""
        # entry1.zip!/entry2.zip!/ >
        # entry1.zip!/entry2.zip >
        # entry1.zip!/ >
        # entry1.zip entry2.zip!/ >
        # entry1.zip entry2.zip >
        # entry1.zip >
        # other

        # entry1.zip!/entry2.zip!/ > entry1.zip!/entry2.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            zh.writestr('entry1.zip!/entry2.zip!/', '')

            buf2 = io.BytesIO()
            with zipfile.ZipFile(buf2, 'w'):
                pass
            zh.writestr('entry1.zip!/entry2.zip', buf2.getvalue())

            zh.writestr('entry1.zip!/', '')

            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!/entry2.zip!'],
        )

        # entry1.zip!/entry2.zip!/ > entry1.zip!/entry2.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            zh.writestr('entry1.zip!/entry2.zip!/.gitkeep', '')

            buf2 = io.BytesIO()
            with zipfile.ZipFile(buf2, 'w'):
                pass
            zh.writestr('entry1.zip!/entry2.zip', buf2.getvalue())

            zh.writestr('entry1.zip!/', '')

            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!/entry2.zip!'],
        )

        # entry1.zip!/entry2.zip > entry1.zip!/
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            buf2 = io.BytesIO()
            with zipfile.ZipFile(buf2, 'w'):
                pass
            zh.writestr('entry1.zip!/entry2.zip', buf2.getvalue())

            zh.writestr('entry1.zip!/', '')

            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!/entry2.zip', ''],
        )

        # entry1.zip!/ > entry1.zip entry2.zip!/
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            zh.writestr('entry1.zip!/entry2.zip', 'non-zip')

            zh.writestr('entry1.zip!/', '')

            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!/entry2.zip!'],
        )

        # entry1.zip!/ > entry1.zip entry2.zip!/
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            zh.writestr('entry1.zip!/', '')

            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!/entry2.zip!'],
        )

        # entry1.zip!/ > entry1.zip entry2.zip!/
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            zh.writestr('entry1.zip!/.gitkeep', '')

            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!/entry2.zip!'],
        )

        # entry1.zip entry2.zip!/ > entry1.zip entry2.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!/', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip', 'entry2.zip!'],
        )

        # entry1.zip entry2.zip!/ > entry1.zip entry2.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!/.gitkeep', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip', 'entry2.zip!'],
        )

        # entry1.zip entry2.zip > entry1.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip', 'entry2.zip', ''],
        )

        # entry1.zip
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            with zipfile.ZipFile(buf1, 'w') as zh1:
                zh1.writestr('entry2.zip', 'non-zip')
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip', 'entry2.zip!'],
        )

        # other
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            zh.writestr('entry1.zip', 'non-zip')

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!/entry2.zip!'],
        )

        # other
        root = tempfile.mkdtemp(dir=tmpdir)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/'),
            [os.path.join(root, 'entry.zip'), 'entry1.zip!/entry2.zip!'],
        )

    def test_resolve4(self):
        """Tidy path."""
        root = tempfile.mkdtemp(dir=tmpdir)
        os.makedirs(os.path.join(root, 'foo', 'bar'), exist_ok=True)
        with zipfile.ZipFile(os.path.join(root, 'foo', 'bar', 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}//foo///bar////entry.zip//'),
            [os.path.join(root, 'foo', 'bar', 'entry.zip')],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/./foo/././bar/./././entry.zip/./'),
            [os.path.join(root, 'foo', 'bar', 'entry.zip')],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/wtf/../bar/wtf/./wtf2/.././../entry.zip'),
            [os.path.join(root, 'foo', 'bar', 'entry.zip')],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/bar/entry.zip!//foo//bar///baz.txt//'),
            [os.path.join(root, 'foo', 'bar', 'entry.zip'), 'foo/bar/baz.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/bar/entry.zip!/./foo/./bar/././baz.txt/./'),
            [os.path.join(root, 'foo', 'bar', 'entry.zip'), 'foo/bar/baz.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/bar/entry.zip!/foo/wtf/../bar/wtf/./wtf2/../../baz.txt'),
            [os.path.join(root, 'foo', 'bar', 'entry.zip'), 'foo/bar/baz.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/bar/entry.zip!/../../'),
            [os.path.join(root, 'foo', 'bar', 'entry.zip'), ''],
        )

    def test_resolve_with_resolver1(self):
        root = tempfile.mkdtemp(dir=tmpdir)

        def resolver(p):
            return os.path.normpath(os.path.join(root, p))

        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip', resolver),
            [f'{root}/entry.zip'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/subdir', resolver),
            [f'{root}/entry.zip', 'subdir'],
        )

    def test_resolve_with_resolver2(self):
        # entry.zip!/entry1.zip > entry.zip!/
        root = tempfile.mkdtemp(dir=tmpdir)

        def resolver(p):
            return os.path.normpath(os.path.join(root, p))

        os.makedirs(os.path.join(root, 'entry.zip!'), exist_ok=True)
        with zipfile.ZipFile(os.path.join(root, 'entry.zip!', 'entry1.zip'), 'w'):
            pass
        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/', resolver),
            [f'{root}/entry.zip!/entry1.zip', ''],
        )

    def test_resolve_with_resolver3(self):
        # entry1.zip!/entry2.zip > entry1.zip!/
        root = tempfile.mkdtemp(dir=tmpdir)

        def resolver(p):
            return os.path.normpath(os.path.join(root, p))

        with zipfile.ZipFile(os.path.join(root, 'entry.zip'), 'w') as zh:
            buf2 = io.BytesIO()
            with zipfile.ZipFile(buf2, 'w'):
                pass
            zh.writestr('entry1.zip!/entry2.zip', buf2.getvalue())

            zh.writestr('entry1.zip!/', '')

            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w'):
                    pass
                zh1.writestr('entry2.zip!', '')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/entry.zip!/entry1.zip!/entry2.zip!/', resolver),
            [f'{root}/entry.zip', 'entry1.zip!/entry2.zip', ''],
        )

    def test_resolve_with_resolver4(self):
        root = tempfile.mkdtemp(dir=tmpdir)

        def resolver(p):
            return os.path.normpath(os.path.join(root, p))

        os.makedirs(os.path.join(root, 'foo', 'bar'), exist_ok=True)
        with zipfile.ZipFile(os.path.join(root, 'foo', 'bar', 'entry.zip'), 'w'):
            pass

        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}//foo///bar////entry.zip//', resolver),
            [f'{root}/foo/bar/entry.zip'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/./foo/././bar/./././entry.zip/./', resolver),
            [f'{root}/foo/bar/entry.zip'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/wtf/../bar/wtf/./wtf2/.././../entry.zip', resolver),
            [f'{root}/foo/bar/entry.zip'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/bar/entry.zip!//foo//bar///baz.txt//', resolver),
            [f'{root}/foo/bar/entry.zip', 'foo/bar/baz.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/bar/entry.zip!/./foo/./bar/././baz.txt/./', resolver),
            [f'{root}/foo/bar/entry.zip', 'foo/bar/baz.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/bar/entry.zip!/foo/wtf/../bar/wtf/./wtf2/../../baz.txt', resolver),
            [f'{root}/foo/bar/entry.zip', 'foo/bar/baz.txt'],
        )
        self.assertSequenceEqual(
            util.fs.CPath.resolve(f'{root}/foo/bar/entry.zip!/../../', resolver),
            [f'{root}/foo/bar/entry.zip', ''],
        )


class TestFsUtilBase(unittest.TestCase):
    def get_file_data(self, data, follow_symlinks=True):
        """Convert file data to a comparable format.

        Args:
            data: a dict with {'file': cpath}
                or {'bytes': bytes, 'stat': os.stat_result or zipfile.ZipInfo}
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
                rv = {'stat': st, 'bytes': bytes_}
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
                rv = {'stat': st, 'bytes': bytes_}
        else:
            rv = data
        return rv

    def assert_file_equal(self, *datas, is_move=False):
        """Assert if file datas are equivalent.

        Args:
            *datas: compatible data format with get_file_data()
            is_move: whether it's a move
        """
        # Such bits may be changed by the API when copying among ZIP files,
        # and we don't really care about them.
        excluded_flag_bits = 1 << 3

        datas = [self.get_file_data(data, follow_symlinks=not is_move) for data in datas]
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


class TestFsUtilBasicMixin:
    """Check for common bad cases for a filesystem operation.

    - Inherit a test method and pass exc to super() if an operation expects
      an alternative exception.
    """
    @property
    def func(self):
        """Subclass this and return the function to test for a test class.

        - Use a property method since a function as class variable becomes a
          bound class method and requires the 'self' parameter.
        """
        return NotImplemented

    def test_bad_parent(self, exc=util.fs.FSBadParentError):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'subdir', 'subpath')
        with open(os.path.join(root, 'subdir'), 'w'):
            pass
        with self.assertRaises(exc):
            self.func(dst)

    def test_bad_parent_grand(self, exc=util.fs.FSBadParentError):
        # Some operations may include os.makedirs(os.path.dirname(dst)),
        # which could raise a different exception when a file occupies at
        # parent or grand parent directory.  Add a check for grand parent
        # to catch them.
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'subdir', 'subdir2', 'subpath')
        with open(os.path.join(root, 'subdir'), 'w'):
            pass
        with self.assertRaises(exc):
            self.func(dst)

    def test_zip_bad_parent1(self, exc=util.fs.FSBadParentError):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep', 'abc')
        dst = [zfile, 'deep/subpath']
        with self.assertRaises(exc):
            self.func(dst)

    def test_zip_bad_parent2(self, exc=util.fs.FSBadParentError):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep', 'abc')
            zh.writestr('deep/subpath', 'def')
        dst = [zfile, 'deep/subpath']
        with self.assertRaises(exc):
            self.func(dst)

    def test_zip_archive_nonexist(self, exc=util.fs.FSEntryNotFoundError):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        dst = [zfile, 'deep/subpath']
        with self.assertRaises(exc):
            self.func(dst)

    def test_zip_archive_corrupted(self, exc=util.fs.FSBadZipFileError):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with open(zfile, 'w'):
            pass
        dst = [zfile, 'deep/subpath']
        with self.assertRaises(exc):
            self.func(dst)

    def test_zip_archive_bad_parent(self, exc=util.fs.FSEntryNotFoundError):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'subdir', 'archive.zip')
        with open(os.path.join(root, 'subdir'), 'w'):
            pass
        dst = [zfile, 'deep/subpath']
        with self.assertRaises(exc):
            self.func(dst)

    def test_zip_archive_bad_parent_grand(self, exc=util.fs.FSEntryNotFoundError):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'subdir', 'subdir2', 'archive.zip')
        with open(os.path.join(root, 'subdir'), 'w'):
            pass
        dst = [zfile, 'deep/subpath']
        with self.assertRaises(exc):
            self.func(dst)


class TestMkDir(TestFsUtilBasicMixin, TestFsUtilBase):
    @property
    def func(self):
        return util.fs.mkdir

    def test_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'subdir')
        util.fs.mkdir(dst)
        self.assertTrue(os.path.isdir(dst))

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX')
    def test_nonexist_mode(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'subdir')
        util.fs.mkdir(dst, mode=0o660)
        self.assertTrue(os.path.isdir(dst))
        self.assertEqual(oct(os.stat(dst).st_mode & 0o777), oct(0o660))

    def test_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'subdir')
        os.makedirs(dst, exist_ok=True)
        util.fs.mkdir(dst)
        self.assertTrue(os.path.isdir(dst))

    def test_dir_not_exist_ok(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'subdir')
        os.makedirs(dst, exist_ok=True)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.mkdir(dst, exist_ok=False)

    def test_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'subdir')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'w'):
            pass
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.mkdir(dst)

    def test_zip_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, 'deep/subdir']
        util.fs.mkdir(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['deep/subdir/'])

    def test_zip_nonexist_nested(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        dst = [zfile, 'nested/subarchive.zip', 'deep/subdir']
        with zipfile.ZipFile(zfile, 'w') as zh:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w'):
                pass
            zh.writestr(dst[1], buf.getvalue())
        util.fs.mkdir(dst)
        with zipfile.ZipFile(zfile) as zh:
            with zh.open(dst[1]) as fh:
                with zipfile.ZipFile(fh) as zh2:
                    self.assertEqual(zh2.namelist(), ['deep/subdir/'])
                    zinfo2 = zh2.getinfo('deep/subdir/')
                    self.assertAlmostEqual(zip_timestamp(zinfo2), datetime.now().timestamp(), delta=5)

    def test_zip_nonexist_mode(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, 'deep/subdir']
        util.fs.mkdir(dst, mode=0o660)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['deep/subdir/'])
            self.assertEqual(oct(zip_mode(zh.getinfo('deep/subdir/'))), oct(0o40660))

    def test_zip_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zinfo = zipfile.ZipInfo('deep/subdir/', DUMMY_ZIP_DT)
            zh.writestr(zinfo, '')
        dst = [zfile, 'deep/subdir']
        util.fs.mkdir(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['deep/subdir/'])
            zinfo = zh.getinfo('deep/subdir/')
            self.assertEqual(zip_timestamp(zinfo), DUMMY_TS)

    def test_zip_dir_not_exist_ok(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir/', '')
        dst = [zfile, 'deep/subdir']
        with self.assertRaises(util.fs.FSDirExistsError):
            util.fs.mkdir(dst, exist_ok=False)

    def test_zip_dir_implicit(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir/somefile.txt', 'abc')
        dst = [zfile, 'deep/subdir']
        util.fs.mkdir(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['deep/subdir/somefile.txt', 'deep/subdir/'])

    def test_zip_dir_implicit_not_exist_ok(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir/somefile.txt', 'abc')
        dst = [zfile, 'deep/subdir']
        util.fs.mkdir(dst, exist_ok=False)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['deep/subdir/somefile.txt', 'deep/subdir/'])

    def test_zip_dir_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, '']
        util.fs.mkdir(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), [])

    def test_zip_dir_root_not_exist_ok(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, '']
        with self.assertRaises(util.fs.FSDirExistsError):
            util.fs.mkdir(dst, exist_ok=False)

    def test_zip_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir', 'abc')
        dst = [zfile, 'deep/subdir']
        with self.assertRaises(util.fs.FSFileExistsError):
            util.fs.mkdir(dst)


class TestMkZip(TestFsUtilBasicMixin, TestFsUtilBase):
    @property
    def func(self):
        return util.fs.mkzip

    def test_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'archive.zip')
        util.fs.mkzip(dst)
        self.assertTrue(zipfile.is_zipfile(dst))

    def test_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'archive.zip')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'w'):
            pass
        util.fs.mkzip(dst)
        self.assertTrue(zipfile.is_zipfile(dst))

    def test_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'archive.zip')
        os.makedirs(dst, exist_ok=True)
        with self.assertRaises(util.fs.FSIsADirectoryError):
            util.fs.mkzip(dst)

    def test_zip_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, 'nested/subarchive.zip']
        util.fs.mkzip(dst)
        with zipfile.ZipFile(zfile) as zh:
            with zh.open('nested/subarchive.zip') as fh:
                self.assertTrue(zipfile.is_zipfile(fh))

    def test_zip_nonexist_nested(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        dst = [zfile, 'nested/subarchive.zip', 'nested2/subarchive2.zip']
        with zipfile.ZipFile(zfile, 'w') as zh:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w'):
                pass
            zh.writestr(dst[1], buf.getvalue())
        util.fs.mkzip(dst)
        with zipfile.ZipFile(zfile) as zh:
            with zh.open(dst[1]) as fh:
                with zipfile.ZipFile(fh) as zh2:
                    zinfo2 = zh2.getinfo(dst[-1])
                    self.assertAlmostEqual(zip_timestamp(zinfo2), datetime.now().timestamp(), delta=5)
                    self.assertEqual(zinfo2.compress_type, zipfile.ZIP_STORED)
                    with zh2.open(zinfo2) as fh2:
                        self.assertTrue(zipfile.is_zipfile(fh2))

    def test_zip_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zinfo = zipfile.ZipInfo('nested/subarchive.zip', DUMMY_ZIP_DT)
            zinfo.external_attr = 0o770 << 16
            zinfo.comment = 'my awesome file'.encode('UTF-8')
            zh.writestr(zinfo, '123', compress_type=zipfile.ZIP_BZIP2)
        dst = [zfile, 'nested/subarchive.zip']
        util.fs.mkzip(dst)
        with zipfile.ZipFile(zfile) as zh:
            zinfo = zh.getinfo(dst[-1])
            self.assertAlmostEqual(zip_timestamp(zinfo), datetime.now().timestamp(), delta=5)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(oct(zip_mode(zinfo)), oct(0o770))
            self.assertEqual(zinfo.comment.decode('UTF-8'), 'my awesome file')
            with zh.open(dst[-1]) as fh:
                self.assertTrue(zipfile.is_zipfile(fh))

    def test_zip_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('nested/subarchive.zip/', '')
        dst = [zfile, 'nested/subarchive.zip']
        with self.assertRaises(util.fs.FSIsADirectoryError):
            util.fs.mkzip(dst)

    def test_zip_dir_implicit(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('nested/subarchive.zip/subfile.txt', '123')
        dst = [zfile, 'nested/subarchive.zip']
        with self.assertRaises(util.fs.FSIsADirectoryError):
            util.fs.mkzip(dst)

    def test_zip_dir_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, '']
        with self.assertRaises(util.fs.FSIsADirectoryError):
            util.fs.mkzip(dst)


class TestSave(TestFsUtilBasicMixin, TestFsUtilBase):
    @property
    def func(self):
        return functools.partial(util.fs.save, src=DUMMY_BYTES)

    def test_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'file.txt')
        util.fs.save(dst, DUMMY_BYTES)
        with open(dst, 'rb') as fh:
            self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_nonexist_stream(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'file.txt')
        stream = io.BytesIO(DUMMY_BYTES)
        util.fs.save(dst, stream)
        with open(dst, 'rb') as fh:
            self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'file.txt')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'w'):
            pass
        util.fs.save(dst, DUMMY_BYTES)
        with open(dst, 'rb') as fh:
            self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'file.txt')
        os.makedirs(dst, exist_ok=True)
        with self.assertRaises(util.fs.FSIsADirectoryError):
            util.fs.save(dst, DUMMY_BYTES)

    def test_zip_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, 'nested/file.txt']
        util.fs.save(dst, DUMMY_BYTES)
        with zipfile.ZipFile(zfile) as zh:
            zinfo = zh.getinfo(dst[-1])
            self.assertAlmostEqual(zip_timestamp(zinfo), datetime.now().timestamp(), delta=5)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_DEFLATED)
            with zh.open(zinfo) as fh:
                self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_zip_nonexist_auto_compress_type(self):
        """Don't compress a non-compressible file type."""
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, 'nested/image.jpg']
        util.fs.save(dst, DUMMY_BYTES)
        with zipfile.ZipFile(zfile) as zh:
            zinfo = zh.getinfo(dst[-1])
            self.assertAlmostEqual(zip_timestamp(zinfo), datetime.now().timestamp(), delta=5)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_STORED)
            with zh.open(zinfo) as fh:
                self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_zip_nonexist_stream(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, 'nested/file.txt']
        stream = io.BytesIO(DUMMY_BYTES)
        util.fs.save(dst, stream)
        with zipfile.ZipFile(zfile) as zh:
            zinfo = zh.getinfo(dst[-1])
            self.assertAlmostEqual(zip_timestamp(zinfo), datetime.now().timestamp(), delta=5)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_DEFLATED)
            with zh.open(zinfo) as fh:
                self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_zip_nonexist_stream_auto_compress_type(self):
        """Don't compress a non-compressible file type."""
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, 'nested/image.jpg']
        stream = io.BytesIO(DUMMY_BYTES)
        util.fs.save(dst, stream)
        with zipfile.ZipFile(zfile) as zh:
            zinfo = zh.getinfo(dst[-1])
            self.assertAlmostEqual(zip_timestamp(zinfo), datetime.now().timestamp(), delta=5)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_STORED)
            with zh.open(zinfo) as fh:
                self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_zip_nonexist_nested(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        dst = [zfile, 'nested/subarchive.zip', 'nested2/file.txt']
        with zipfile.ZipFile(zfile, 'w') as zh:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w'):
                pass
            zh.writestr(dst[1], buf.getvalue())
        util.fs.save(dst, DUMMY_BYTES)
        with zipfile.ZipFile(zfile) as zh:
            with zh.open(dst[1]) as fh:
                with zipfile.ZipFile(fh) as zh2:
                    zinfo2 = zh2.getinfo(dst[-1])
                    self.assertAlmostEqual(zip_timestamp(zinfo2), datetime.now().timestamp(), delta=5)
                    self.assertEqual(zinfo2.compress_type, zipfile.ZIP_DEFLATED)
                    with zh2.open(zinfo2) as fh2:
                        self.assertEqual(fh2.read(), DUMMY_BYTES)

    def test_zip_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zinfo = zipfile.ZipInfo('nested/file.txt', DUMMY_ZIP_DT)
            zinfo.external_attr = 0o770 << 16
            zinfo.comment = 'my awesome file'.encode('UTF-8')
            zh.writestr(zinfo, '123', compress_type=zipfile.ZIP_BZIP2)
        dst = [zfile, 'nested/file.txt']
        util.fs.save(dst, DUMMY_BYTES)
        with zipfile.ZipFile(zfile) as zh:
            zinfo = zh.getinfo(dst[-1])
            self.assertAlmostEqual(zip_timestamp(zinfo), datetime.now().timestamp(), delta=5)
            self.assertEqual(oct(zip_mode(zinfo)), oct(0o770))
            self.assertEqual(zinfo.comment.decode('UTF-8'), 'my awesome file')
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_BZIP2)
            with zh.open(zinfo) as fh:
                self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_zip_file_stream(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zinfo = zipfile.ZipInfo('nested/file.txt', DUMMY_ZIP_DT)
            zinfo.external_attr = 0o770 << 16
            zinfo.comment = 'my awesome file'.encode('UTF-8')
            zh.writestr(zinfo, '123', compress_type=zipfile.ZIP_BZIP2)
        dst = [zfile, 'nested/file.txt']
        stream = io.BytesIO(DUMMY_BYTES)
        util.fs.save(dst, stream)
        with zipfile.ZipFile(zfile) as zh:
            zinfo = zh.getinfo(dst[-1])
            self.assertAlmostEqual(zip_timestamp(zinfo), datetime.now().timestamp(), delta=5)
            self.assertEqual(oct(zip_mode(zinfo)), oct(0o770))
            self.assertEqual(zinfo.comment.decode('UTF-8'), 'my awesome file')
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_BZIP2)
            with zh.open(zinfo) as fh:
                self.assertEqual(fh.read(), DUMMY_BYTES)

    def test_zip_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('nested/file.txt/', '')
        dst = [zfile, 'nested/file.txt']
        with self.assertRaises(util.fs.FSIsADirectoryError):
            util.fs.save(dst, DUMMY_BYTES)

    def test_zip_dir_implicit(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('nested/file.txt/subfile.txt', '123')
        dst = [zfile, 'nested/file.txt']
        with self.assertRaises(util.fs.FSIsADirectoryError):
            util.fs.save(dst, DUMMY_BYTES)

    def test_zip_dir_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w'):
            pass
        dst = [zfile, '']
        with self.assertRaises(util.fs.FSIsADirectoryError):
            util.fs.save(dst, DUMMY_BYTES)


class TestDelete(TestFsUtilBasicMixin, TestFsUtilBase):
    @property
    def func(self):
        return util.fs.delete

    def test_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'file.txt')
        util.fs.save(dst, DUMMY_BYTES)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))

    def test_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'folder')
        util.fs.mkdir(dst)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_junction1(self):
        """Delete the junction entity rather than the referenced directory."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'subdir')
        ref2 = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'junction')
        util.fs.save(ref2, DUMMY_BYTES)
        util.fs.junction(ref, dst)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))
        self.assertTrue(os.path.isdir(ref))
        self.assertTrue(os.path.isfile(ref2))

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_junction2(self):
        """Delete the junction entity even if target not exist."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        dst = os.path.join(root, 'junction')
        util.fs.junction(ref, dst)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    @unittest.skipUnless(sys.version_info >= (3, 8), 'requires Python >= 3.8')
    def test_junction_deep(self):
        """Delete junction entities under a directory without altering the
        referenced directory.
        """
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'subdir')
        ref2 = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2')
        link = os.path.join(root, 'subdir2', 'junction')
        util.fs.save(ref2, DUMMY_BYTES)
        util.fs.mkdir(os.path.dirname(link))
        util.fs.junction(ref, link)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))
        self.assertTrue(os.path.isdir(ref))
        self.assertTrue(os.path.isfile(ref2))

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink1(self):
        """Delete the symlink entity rather than the referenced directory."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'subdir')
        ref2 = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'symlink')
        util.fs.save(ref2, DUMMY_BYTES)
        os.symlink(ref, dst)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))
        self.assertTrue(os.path.isdir(ref))
        self.assertTrue(os.path.isfile(ref2))

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink2(self):
        """Delete the symlink entity rather than the referenced file."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'test.txt')
        dst = os.path.join(root, 'symlink')
        util.fs.save(ref, DUMMY_BYTES)
        os.symlink(ref, dst)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))
        self.assertTrue(os.path.isfile(ref))

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink3(self):
        """Delete the symlink entity even if target not exist."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        dst = os.path.join(root, 'symlink')
        os.symlink(ref, dst)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink_deep(self):
        """Delete symlink entities under a directory without altering the
        referenced directory.
        """
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'subdir')
        ref2 = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2')
        link = os.path.join(root, 'subdir2', 'symlink')
        util.fs.save(ref2, DUMMY_BYTES)
        util.fs.mkdir(dst)
        os.symlink(ref, link)
        util.fs.delete(dst)
        self.assertFalse(os.path.lexists(dst))
        self.assertTrue(os.path.isdir(ref))
        self.assertTrue(os.path.isfile(ref2))

    def test_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'nonexist')
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.delete(dst)

    def test_zip_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', 'abc')
            zh.writestr('nested/', '')
            zh.writestr('nested/file.txt', '123')
        dst = [zfile, 'nested/file.txt']
        util.fs.delete(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['file.txt', 'nested/'])

    def test_zip_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', 'abc')
            zh.writestr('nested/', '')
            zh.writestr('nested/folder/', '')
            zh.writestr('nested/folder/subfolder/', '')
            zh.writestr('nested/folder/subfile.txt', '123')
        dst = [zfile, 'nested/folder']
        util.fs.delete(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['file.txt', 'nested/'])

    def test_zip_dir_implicit(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', 'abc')
            zh.writestr('nested/folder/subfolder/', '')
            zh.writestr('nested/folder/subfile.txt', '123')
        dst = [zfile, 'nested/folder']
        util.fs.delete(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['file.txt'])

    def test_zip_dir_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', 'abc')
            zh.writestr('nested/folder/subfolder/', '')
            zh.writestr('nested/folder/subfile.txt', '123')
        dst = [zfile, '']
        util.fs.delete(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), [])

    def test_zip_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', 'abc')
            zh.writestr('nested/', '')
            zh.writestr('nested/file.txt', '123')
        dst = [zfile, 'nonexist']
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.delete(dst)

    # inherited
    def test_bad_parent(self):
        super().test_bad_parent(exc=util.fs.FSEntryNotFoundError)

    def test_bad_parent_grand(self):
        super().test_bad_parent_grand(exc=util.fs.FSEntryNotFoundError)

    def test_zip_bad_parent1(self):
        super().test_zip_bad_parent1(exc=util.fs.FSEntryNotFoundError)

    def test_zip_bad_parent2(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep', 'abc')
            zh.writestr('deep/subpath', 'def')
        dst = [zfile, 'deep/subpath']
        util.fs.delete(dst)
        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(zh.namelist(), ['deep'])


class TestMove(TestFsUtilBasicMixin, TestFsUtilBase):
    @property
    def func(self):
        return functools.partial(util.fs.move, cdst=os.path.join(tmpdir, 'nonexist'))

    def test_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'nonexist')
        dst = os.path.join(root, 'subdir2', 'nonexist2')
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.move(src, dst)

    def test_file_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2', 'test2.txt')
        util.fs.save(src, DUMMY_BYTES)
        orig_src = self.get_file_data({'file': src})
        util.fs.move(src, dst)
        self.assertFalse(os.path.lexists(src))
        self.assert_file_equal(orig_src, {'file': dst}, is_move=True)

    def test_file_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir', 'test2.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.save(dst, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)
        self.assertTrue(os.path.lexists(src))

    def test_file_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'test.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkdir(dst)
        orig_src = self.get_file_data({'file': src})
        util.fs.move(src, dst)
        self.assertFalse(os.path.lexists(src))
        self.assert_file_equal(orig_src, {'file': dst2}, is_move=True)

    def test_file_to_dir_with_same_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'test.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.save(dst2, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)
        self.assertTrue(os.path.lexists(src))

    def test_file_to_dir_with_same_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'test.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkdir(dst2)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)
        self.assertTrue(os.path.lexists(src))

    def test_dir_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = os.path.join(root, 'subdir2', 'subdir')
        dst2 = os.path.join(root, 'subdir2', 'subdir', 'file.txt')
        util.fs.save(src2, DUMMY_BYTES)
        orig_src = self.get_file_data({'file': src})
        orig_src2 = self.get_file_data({'file': src2})
        util.fs.move(src, dst)
        self.assertFalse(os.path.lexists(src))
        self.assert_file_equal(orig_src, {'file': dst}, is_move=True)
        self.assert_file_equal(orig_src2, {'file': dst2}, is_move=True)

    def test_dir_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        dst = os.path.join(root, 'subdir2', 'file2.txt')
        util.fs.mkdir(src)
        util.fs.save(dst, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)
        self.assertTrue(os.path.lexists(src))

    def test_dir_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'folder')
        dst3 = os.path.join(root, 'subdir2', 'folder', 'file.txt')
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkdir(dst)
        orig_src = self.get_file_data({'file': src})
        orig_src2 = self.get_file_data({'file': src2})
        util.fs.move(src, dst)
        self.assertFalse(os.path.lexists(src))
        self.assert_file_equal(orig_src, {'file': dst2}, is_move=True)
        self.assert_file_equal(orig_src2, {'file': dst3}, is_move=True)

    def test_dir_to_dir_with_same_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'folder')
        util.fs.mkdir(src)
        util.fs.save(dst2, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)
        self.assertTrue(os.path.lexists(src))

    def test_dir_to_dir_with_same_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'folder')
        util.fs.mkdir(src)
        util.fs.mkdir(dst2)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)
        self.assertTrue(os.path.lexists(src))

    def test_dir_to_child(self):
        """Moving a directory to a child should be prevented.

        - A general implementation of moving may cause recursive copying of
          contents and/or self deletion.
        """
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = os.path.join(root, 'subdir', 'folder', 'subfolder')
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSMoveInsideError):
            util.fs.move(src, dst)

        # verify no unexpected content change
        self.assertEqual(
            glob_files(src),
            {os.path.join(src, ''), src2},
        )

    def test_dir_to_child_self(self):
        """Moving a directory to a self should be prevented.

        - Copying to self is a special case of copying to child.  It may be
          allowed for a possible case insensitive renaming.  We don't allow
          it for a potential error.
        """
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = os.path.join(root, 'subdir', 'folder')
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSMoveInsideError):
            util.fs.move(src, dst)

        # verify no unexpected content change
        self.assertEqual(
            glob_files(src),
            {os.path.join(src, ''), src2},
        )

    @unittest.skipUnless(os.path.normcase('ABC') == os.path.normcase('abc'),
                         'requires case insensitive filesystem such as Windows')
    def test_dir_to_child_ci(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = os.path.join(root, 'subdir', 'Folder', 'subfolder')
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSMoveInsideError):
            util.fs.move(src, dst)

        # verify no unexpected content change
        self.assertEqual(
            glob_files(src),
            {os.path.join(src, ''), src2},
        )

    @unittest.skipUnless(os.path.normcase('ABC') == os.path.normcase('abc'),
                         'requires case insensitive filesystem such as Windows')
    def test_dir_to_child_self_ci(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = os.path.join(root, 'Subdir', 'folder')
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSMoveInsideError):
            util.fs.move(src, dst)

        # verify no unexpected content change
        self.assertEqual(
            glob_files(src),
            {os.path.join(src, ''), src2},
        )

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_junction_to_nonexist(self):
        """Move the entity rather than the referenced directory."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        src = os.path.join(root, 'junction')
        dst = os.path.join(root, 'folder')
        with test_file_cleanup(src, dst):
            util.fs.junction(ref, src)
            orig_src = self.get_file_data({'file': src}, follow_symlinks=False)
            util.fs.move(src, dst)
            self.assertFalse(os.path.lexists(src))
            self.assert_file_equal(orig_src, {'file': dst}, is_move=True)

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink_to_nonexist(self):
        """Move the entity rather than the referenced directory/file."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        src = os.path.join(root, 'symlink')
        dst = os.path.join(root, 'folder')
        os.symlink(ref, src)
        orig_src = self.get_file_data({'file': src}, follow_symlinks=False)
        util.fs.move(src, dst)
        self.assertFalse(os.path.lexists(src))
        self.assert_file_equal(orig_src, {'file': dst}, is_move=True)

    def test_disk_to_zip(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkzip(dst[0])
        with self.assertRaises(util.fs.FSMoveAcrossZipError):
            util.fs.move(src, dst)
        self.assertTrue(os.path.lexists(src))

    def test_zip_to_disk(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        dst = os.path.join(root, 'subdir')
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSMoveAcrossZipError):
            util.fs.move(src, dst)

    def test_zip_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/nonexist']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir/target']
        util.fs.mkzip(src[0])
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.move(src, dst)

    def test_zip_file_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir/file2.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        orig_src = self.get_file_data({'file': src})
        util.fs.move(src, dst)
        self.assert_file_equal(orig_src, {'file': dst}, is_move=True)

    def test_zip_file_to_nonexist_nested(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subarchive.zip', 'deep/file.txt']
        dst = [os.path.join(root, 'archive2.zip'), 'deep/subarchive2.zip', 'deep/file2.txt']
        util.fs.mkzip(src[:1])
        util.fs.mkzip(src[:2])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkzip(dst[:1])
        util.fs.mkzip(dst[:2])
        orig_src = self.get_file_data({'file': src})
        util.fs.move(src, dst)
        self.assert_file_equal(orig_src, {'file': dst}, is_move=True)

    def test_zip_file_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir/file2.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.save(dst, b'')
        with self.assertRaises(util.fs.FSFileExistsError):
            util.fs.move(src, dst)

    def test_zip_file_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkdir(dst)
        orig_src = self.get_file_data({'file': src})
        util.fs.move(src, dst)
        self.assert_file_equal(orig_src, {'file': dst2}, is_move=True)

    def test_zip_file_to_dir_with_same_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.save(dst2, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)

    def test_zip_file_to_dir_with_same_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkdir(dst2)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)

    def test_zip_dir_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        src3 = [os.path.join(root, 'archive.zip'), 'deep/subdir/explicit_dir']
        src4 = [os.path.join(root, 'archive.zip'), 'deep/subdir/implicit_dir/subfile.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir3']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir3/file.txt']
        dst3 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir3/explicit_dir']
        dst4 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir3/implicit_dir/subfile.txt']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkdir(src3)
        util.fs.save(src4, DUMMY_BYTES2)
        orig_src = self.get_file_data({'file': src})
        orig_src2 = self.get_file_data({'file': src2})
        orig_src3 = self.get_file_data({'file': src3})
        orig_src4 = self.get_file_data({'file': src4})
        util.fs.move(src, dst)
        self.assert_file_equal(orig_src, {'file': dst}, is_move=True)
        self.assert_file_equal(orig_src2, {'file': dst2}, is_move=True)
        self.assert_file_equal(orig_src3, {'file': dst3}, is_move=True)
        self.assert_file_equal(orig_src4, {'file': dst4}, is_move=True)

    def test_zip_dir_to_nonexist_nested(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subarchive.zip', 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subarchive.zip', 'deep/subdir/file.txt']
        dst = [os.path.join(root, 'archive2.zip'), 'deep/subarchive2.zip', 'deep/subdir2']
        dst2 = [os.path.join(root, 'archive2.zip'), 'deep/subarchive2.zip', 'deep/subdir2/file.txt']
        util.fs.mkzip(src[:1])
        util.fs.mkzip(src[:2])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkzip(dst[:1])
        util.fs.mkzip(dst[:2])
        orig_src = self.get_file_data({'file': src})
        orig_src2 = self.get_file_data({'file': src2})
        util.fs.move(src, dst)
        self.assert_file_equal(orig_src, {'file': dst}, is_move=True)
        self.assert_file_equal(orig_src2, {'file': dst2}, is_move=True)

    def test_zip_dir_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2/file.txt']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(dst, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSFileExistsError):
            util.fs.move(src, dst)

    def test_zip_dir_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir']
        dst3 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir/file.txt']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkdir(dst)
        orig_src = self.get_file_data({'file': src})
        orig_src2 = self.get_file_data({'file': src2})
        util.fs.move(src, dst)
        self.assert_file_equal(orig_src, {'file': dst2}, is_move=True)
        self.assert_file_equal(orig_src2, {'file': dst3}, is_move=True)

    def test_zip_dir_to_dir_with_same_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.mkdir(dst)
        util.fs.save(dst2, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)

    def test_zip_dir_to_dir_with_same_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.mkdir(dst)
        util.fs.mkdir(dst2)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.move(src, dst)

    def test_zip_dir_to_child1(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir/subdir2']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSMoveInsideError):
            util.fs.move(src, dst)

        # verify no unexpected content change
        with util.fs.open_archive_path(src) as zh:
            self.assertEqual(
                {*zh.namelist()},
                {'deep/subdir/', 'deep/subdir/file.txt'},
            )

    def test_zip_dir_to_child2(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subarchive.zip']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subarchive.zip', 'deep/file.txt']
        util.fs.mkzip(src[0])
        util.fs.mkzip(src)
        with self.assertRaises(util.fs.FSMoveInsideError):
            util.fs.move(src, dst)

        # verify no unexpected content change
        with util.fs.open_archive_path(src) as zh:
            self.assertEqual(
                {*zh.namelist()},
                {'deep/subarchive.zip'},
            )

    def test_zip_dir_to_child_self(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSMoveInsideError):
            util.fs.move(src, dst)

        # verify no unexpected content change
        with util.fs.open_archive_path(src) as zh:
            self.assertEqual(
                {*zh.namelist()},
                {'deep/subdir/', 'deep/subdir/file.txt'},
            )

    def test_zip_dir_root_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), '']
        src2 = [os.path.join(root, 'archive.zip'), 'subdir/file.txt']
        dst = [os.path.join(root, 'archive2.zip'), 'deep/subdir2']
        util.fs.mkzip(src[0])
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkzip(dst[0])
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.move(src, dst)

    # inherited
    def test_bad_parent(self):
        super().test_bad_parent(exc=util.fs.FSEntryNotFoundError)

    def test_bad_parent_grand(self):
        super().test_bad_parent_grand(exc=util.fs.FSEntryNotFoundError)


class TestCopy(TestFsUtilBasicMixin, TestFsUtilBase):
    @property
    def func(self):
        return functools.partial(util.fs.copy, cdst=os.path.join(tmpdir, 'nonexist'))

    def test_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'nonexist')
        dst = os.path.join(root, 'subdir2', 'nonexist2')
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.copy(src, dst)

    def test_file_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2', 'test2.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})

    def test_file_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir', 'test2.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.save(dst, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_file_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'test.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkdir(dst)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst2})

    def test_file_to_dir_with_same_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'test.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.save(dst2, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_file_to_dir_with_same_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'test.txt')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'test.txt')
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkdir(dst2)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_dir_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = os.path.join(root, 'subdir2', 'subdir')
        dst2 = os.path.join(root, 'subdir2', 'subdir', 'file.txt')
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'file': src2}, {'file': dst2})

    def test_dir_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        dst = os.path.join(root, 'subdir2', 'file2.txt')
        util.fs.mkdir(src)
        util.fs.save(dst, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_dir_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        src2 = os.path.join(root, 'subdir', 'folder', 'file.txt')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'folder')
        dst3 = os.path.join(root, 'subdir2', 'folder', 'file.txt')
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkdir(dst)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst2})
        self.assert_file_equal({'file': src2}, {'file': dst3})

    def test_dir_to_dir_with_same_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'folder')
        util.fs.mkdir(src)
        util.fs.save(dst2, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_dir_to_dir_with_same_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'folder')
        dst = os.path.join(root, 'subdir2')
        dst2 = os.path.join(root, 'subdir2', 'folder')
        util.fs.mkdir(src)
        util.fs.mkdir(dst2)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_junction_to_nonexist1(self):
        """Copy junction as a new regular directory."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'reference')
        ref2 = os.path.join(root, 'reference', 'file.txt')
        src = os.path.join(root, 'junction')
        dst = os.path.join(root, 'subdir')
        dst2 = os.path.join(root, 'subdir', 'file.txt')
        util.fs.save(ref2, DUMMY_BYTES)
        util.fs.junction(ref, src)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': ref}, {'file': dst})
        self.assert_file_equal({'file': ref2}, {'file': dst2})

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_junction_to_nonexist2(self):
        """Raises when copying a broken directory junction."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        src = os.path.join(root, 'junction')
        dst = os.path.join(root, 'subdir')
        with test_file_cleanup(src):
            util.fs.junction(ref, src)
            with self.assertRaises(util.fs.FSEntryNotFoundError):
                util.fs.copy(src, dst)

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_junction_to_nonexist_deep1(self):
        """Copy inner junctions as new regular directories.

        - May use stat of the junction entity (Python 3.8) or the referenced
          directory (Python < 3.8).
        """
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'reference')
        ref2 = os.path.join(root, 'reference', 'test.txt')
        src = os.path.join(root, 'subdir')
        src2 = os.path.join(root, 'subdir', 'junction')
        dst = os.path.join(root, 'newdir')
        dst2 = os.path.join(root, 'newdir', 'junction')
        dst3 = os.path.join(root, 'newdir', 'junction', 'test.txt')
        with test_file_cleanup(src2):
            util.fs.save(ref2, DUMMY_BYTES)
            util.fs.mkdir(src)
            util.fs.junction(ref, src2)
            util.fs.copy(src, dst)
            self.assert_file_equal({'file': src}, {'file': dst})
            self.assert_file_equal({'file': ref}, {'file': dst2})
            self.assert_file_equal({'file': ref2}, {'file': dst3})

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_junction_to_nonexist_deep2(self):
        """Raise for broken junctions, which are not copied."""
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir')
        src2 = os.path.join(root, 'subdir', 'junction')
        src3 = os.path.join(root, 'subdir', 'file.txt')
        dst = os.path.join(root, 'newdir')
        dst2 = os.path.join(root, 'newdir', 'junction')
        dst3 = os.path.join(root, 'newdir', 'file.txt')
        with test_file_cleanup(src2):
            util.fs.mkdir(src)
            util.fs.junction(os.path.join(root, 'nonexist'), src2)
            util.fs.save(src3, DUMMY_BYTES)
            with self.assertRaises(util.fs.FSPartialError):
                util.fs.copy(src, dst)
            self.assert_file_equal({'file': src}, {'file': dst})
            self.assertFalse(os.path.lexists(dst2))
            self.assert_file_equal({'file': src3}, {'file': dst3})

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink_to_nonexist1(self):
        """Copy symlink as a new regular directory."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'reference')
        ref2 = os.path.join(root, 'reference', 'file.txt')
        src = os.path.join(root, 'symlink')
        dst = os.path.join(root, 'subdir')
        dst2 = os.path.join(root, 'subdir', 'file.txt')
        util.fs.save(ref2, DUMMY_BYTES)
        os.symlink(ref, src)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': ref}, {'file': dst})
        self.assert_file_equal({'file': ref2}, {'file': dst2})

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink_to_nonexist2(self):
        """Raises when copying a broken symlink."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        src = os.path.join(root, 'symlink')
        dst = os.path.join(root, 'subdir')
        os.symlink(ref, src)
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.copy(src, dst)

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink_to_nonexist_deep1(self):
        """Copy inner symlinks as new regular directories/files.

        - Use stat of the symlink target.
        """
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'reference')
        ref2 = os.path.join(root, 'reference', 'test.txt')
        ref3 = os.path.join(root, 'reference-file.txt')
        src = os.path.join(root, 'subdir')
        src2 = os.path.join(root, 'subdir', 'symlink')
        src3 = os.path.join(root, 'subdir', 'symlink2')
        dst = os.path.join(root, 'newdir')
        dst2 = os.path.join(root, 'newdir', 'symlink')
        dst3 = os.path.join(root, 'newdir', 'symlink', 'test.txt')
        dst4 = os.path.join(root, 'newdir', 'symlink2')
        util.fs.save(ref2, DUMMY_BYTES)
        util.fs.save(ref3, DUMMY_BYTES2)
        util.fs.mkdir(src)
        os.symlink(ref, src2)
        os.symlink(ref3, src3)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'file': ref}, {'file': dst2})
        self.assert_file_equal({'file': ref2}, {'file': dst3})
        self.assert_file_equal({'file': ref3}, {'file': dst4})

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_symlink_to_nonexist_deep2(self):
        """Raise for broken symlinks, which are not copied."""
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir')
        src2 = os.path.join(root, 'subdir', 'symlink')
        src3 = os.path.join(root, 'subdir', 'file.txt')
        dst = os.path.join(root, 'newdir')
        dst2 = os.path.join(root, 'newdir', 'symlink')
        dst3 = os.path.join(root, 'newdir', 'file.txt')
        util.fs.mkdir(src)
        os.symlink(os.path.join(root, 'nonexist'), src2)
        util.fs.save(src3, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSPartialError):
            util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assertFalse(os.path.lexists(dst2))
        self.assert_file_equal({'file': src3}, {'file': dst3})

    def test_disk_to_zip_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir', 'nonexist')
        dst = [os.path.join(root, 'archive.zip'), 'deep/subpath']
        util.fs.mkzip(dst[0])
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.copy(src, dst)

    def test_disk_to_zip_file_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'deep', 'file.txt')
        dst = [os.path.join(root, 'archive.zip'), 'deep2/file2.txt']
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkzip(dst[0])
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})

    def test_disk_to_zip_dir_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'deep', 'folder')
        src2 = os.path.join(root, 'deep', 'folder', 'file.txt')
        dst = [os.path.join(root, 'archive.zip'), 'deep/newdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/newdir/file.txt']
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkzip(dst[0])
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'file': src2}, {'file': dst2})

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_disk_to_zip_junction_to_nonexist_deep1(self):
        """Copy inner junctions as new regular directories."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'reference')
        ref2 = os.path.join(root, 'reference', 'test.txt')
        src = os.path.join(root, 'deep')
        src2 = os.path.join(root, 'deep', 'junction')
        dst = [os.path.join(root, 'archive.zip'), 'deep/newdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/newdir/junction']
        dst3 = [os.path.join(root, 'archive.zip'), 'deep/newdir/junction/test.txt']
        util.fs.save(ref2, DUMMY_BYTES)
        util.fs.mkdir(src)
        util.fs.junction(ref, src2)
        util.fs.mkzip(dst[0])
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'file': ref}, {'file': dst2})
        self.assert_file_equal({'file': ref2}, {'file': dst3})

    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_disk_to_zip_junction_to_nonexist_deep2(self):
        """Raise for broken junctions, which are not copied."""
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir')
        src2 = os.path.join(root, 'subdir', 'junction')
        src3 = os.path.join(root, 'subdir', 'file.txt')
        dst = [os.path.join(root, 'archive.zip'), 'deep/newdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/newdir/junction']
        dst3 = [os.path.join(root, 'archive.zip'), 'deep/newdir/junction/file.txt']
        with test_file_cleanup(src2):
            util.fs.mkdir(src)
            util.fs.junction(os.path.join(root, 'nonexist'), src2)
            util.fs.mkzip(dst[0])
            util.fs.save(src3, DUMMY_BYTES)
            with self.assertRaises(util.fs.FSPartialError):
                util.fs.copy(src, dst)
            self.assert_file_equal({'file': src}, {'file': dst})
            self.assert_file_equal({}, {'file': dst2})
            self.assert_file_equal({}, {'file': dst3})

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_disk_to_zip_symlink_to_nonexist_deep1(self):
        """Copy inner symlinks as new regular directories/files."""
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'reference')
        ref2 = os.path.join(root, 'reference', 'test.txt')
        ref3 = os.path.join(root, 'reference-file.txt')
        src = os.path.join(root, 'deep')
        src2 = os.path.join(root, 'deep', 'symlink')
        src3 = os.path.join(root, 'deep', 'symlink2')
        dst = [os.path.join(root, 'archive.zip'), 'deep/newdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/newdir/symlink']
        dst3 = [os.path.join(root, 'archive.zip'), 'deep/newdir/symlink/test.txt']
        dst4 = [os.path.join(root, 'archive.zip'), 'deep/newdir/symlink2']
        util.fs.save(ref2, DUMMY_BYTES)
        util.fs.save(ref3, DUMMY_BYTES2)
        util.fs.mkdir(src)
        os.symlink(ref, src2)
        os.symlink(ref3, src3)
        util.fs.mkzip(dst[0])
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'file': ref}, {'file': dst2})
        self.assert_file_equal({'file': ref2}, {'file': dst3})
        self.assert_file_equal({'file': ref3}, {'file': dst4})

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    def test_disk_to_zip_symlink_to_nonexist_deep2(self):
        """Raise for broken symlinks, which are not copied."""
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'subdir')
        src2 = os.path.join(root, 'subdir', 'symlink')
        src3 = os.path.join(root, 'subdir', 'file.txt')
        dst = [os.path.join(root, 'archive.zip'), 'deep/newdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/newdir/symlink']
        dst3 = [os.path.join(root, 'archive.zip'), 'deep/newdir/symlink/file.txt']
        util.fs.mkdir(src)
        os.symlink(os.path.join(root, 'nonexist'), src2)
        util.fs.mkzip(dst[0])
        util.fs.save(src3, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSPartialError):
            util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'stat': None, 'bytes': None}, {'file': dst2})
        self.assert_file_equal({'stat': None, 'bytes': None}, {'file': dst3})

    def test_zip_to_disk_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/nonexist']
        dst = os.path.join(root, 'deep', 'subpath')
        util.fs.mkzip(src[0])
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.copy(src, dst)

    def test_zip_to_disk_file_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = os.path.join(root, 'deep2', 'file2.txt')
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})

    def test_zip_to_disk_dir_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        dst = os.path.join(root, 'deep', 'newdir')
        dst2 = os.path.join(root, 'deep', 'newdir', 'file.txt')
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'file': src2}, {'file': dst2})

    def test_zip_to_disk_dir_root_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), '']
        src2 = [os.path.join(root, 'archive.zip'), 'subdir/file.txt']
        dst = os.path.join(root, 'deep', 'newdir')
        util.fs.mkzip(src[0])
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.copy(src, dst)

    def test_zip_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/nonexist']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir/target']
        util.fs.mkzip(src[0])
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.copy(src, dst)

    def test_zip_file_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir/file2.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})

    def test_zip_file_to_nonexist_nested(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subarchive.zip', 'deep/file.txt']
        dst = [os.path.join(root, 'archive2.zip'), 'deep/subarchive2.zip', 'deep/file2.txt']
        util.fs.mkzip(src[:1])
        util.fs.mkzip(src[:2])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkzip(dst[:1])
        util.fs.mkzip(dst[:2])
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})

    def test_zip_file_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir/file2.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.save(dst, b'')
        with self.assertRaises(util.fs.FSFileExistsError):
            util.fs.copy(src, dst)

    def test_zip_file_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkdir(dst)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst2})

    def test_zip_file_to_dir_with_same_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.save(dst2, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_zip_file_to_dir_with_same_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        util.fs.mkzip(src[0])
        util.fs.save(src, DUMMY_BYTES)
        util.fs.mkdir(dst2)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_zip_dir_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        src3 = [os.path.join(root, 'archive.zip'), 'deep/subdir/explicit_dir']
        src4 = [os.path.join(root, 'archive.zip'), 'deep/subdir/implicit_dir/subfile.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir3']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir3/file.txt']
        dst3 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir3/explicit_dir']
        dst4 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir3/implicit_dir/subfile.txt']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkdir(src3)
        util.fs.save(src4, DUMMY_BYTES2)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'file': src2}, {'file': dst2})
        self.assert_file_equal({'file': src3}, {'file': dst3})
        self.assert_file_equal({'file': src4}, {'file': dst4})

    def test_zip_dir_to_nonexist_nested(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subarchive.zip', 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subarchive.zip', 'deep/subdir/file.txt']
        dst = [os.path.join(root, 'archive2.zip'), 'deep/subarchive2.zip', 'deep/subdir2']
        dst2 = [os.path.join(root, 'archive2.zip'), 'deep/subarchive2.zip', 'deep/subdir2/file.txt']
        util.fs.mkzip(src[:1])
        util.fs.mkzip(src[:2])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkzip(dst[:1])
        util.fs.mkzip(dst[:2])
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst})
        self.assert_file_equal({'file': src2}, {'file': dst2})

    def test_zip_dir_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2/file.txt']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(dst, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSFileExistsError):
            util.fs.copy(src, dst)

    def test_zip_dir_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        src2 = [os.path.join(root, 'archive.zip'), 'deep/subdir/file.txt']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir']
        dst3 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir/file.txt']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.save(src2, DUMMY_BYTES)
        util.fs.mkdir(dst)
        util.fs.copy(src, dst)
        self.assert_file_equal({'file': src}, {'file': dst2})
        self.assert_file_equal({'file': src2}, {'file': dst3})

    def test_zip_dir_to_dir_with_same_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.mkdir(dst)
        util.fs.save(dst2, b'')
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_zip_dir_to_dir_with_same_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), 'deep/subdir']
        dst = [os.path.join(root, 'archive.zip'), 'deep/subdir2']
        dst2 = [os.path.join(root, 'archive.zip'), 'deep/subdir2/subdir']
        util.fs.mkzip(src[0])
        util.fs.mkdir(src)
        util.fs.mkdir(dst)
        util.fs.mkdir(dst2)
        with self.assertRaises(util.fs.FSEntryExistsError):
            util.fs.copy(src, dst)

    def test_zip_dir_root_to_nonexist(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = [os.path.join(root, 'archive.zip'), '']
        src2 = [os.path.join(root, 'archive.zip'), 'subdir/file.txt']
        dst = [os.path.join(root, 'archive2.zip'), 'deep/subdir2']
        util.fs.mkzip(src[0])
        util.fs.save(src2, DUMMY_BYTES)
        with self.assertRaises(util.fs.FSEntryNotFoundError):
            util.fs.copy(src, dst)

    # inherited
    def test_bad_parent(self):
        super().test_bad_parent(exc=util.fs.FSEntryNotFoundError)

    def test_bad_parent_grand(self):
        super().test_bad_parent_grand(exc=util.fs.FSEntryNotFoundError)


class TestOpenArchivePath(unittest.TestCase):
    def test_open_archive_path_read(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w') as zh2:
                    zh2.writestr('subdir/index.html', 'Hello World!')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        # normal read
        with util.fs.open_archive_path([zfile, 'entry1.zip', 'entry2.zip', 'subdir/index.html']) as zh:
            self.assertEqual(zh.read('subdir/index.html').decode('UTF-8'), 'Hello World!')

        # path length must > 1
        with self.assertRaises(ValueError):
            with util.fs.open_archive_path([zfile]) as zh:
                pass

    def test_open_archive_path_write(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.comment = 'test zip comment 測試'.encode('UTF-8')
            zinfo = zipfile.ZipInfo('entry1.zip', DUMMY_ZIP_DT)
            zinfo.compress_type = zipfile.ZIP_BZIP2
            zinfo.external_attr = 0o700 << 16
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w') as zh1:
                zh1.comment = 'test zip comment 1 測試'.encode('UTF-8')
                zh1.writestr('subdir/index.html', 'Hello World!')
            zh.writestr(zinfo, buf.getvalue())

        with util.fs.open_archive_path([zfile, 'entry1.zip', 'subdir/index.html'], 'a') as zh:
            # replace
            util.fs.zip_remove(zh, 'subdir/index.html')
            zh.writestr('subdir/index.html', 'rewritten 測試')

            # new
            zh.writestr('newdir/test.txt', 'new file 測試')

        with zipfile.ZipFile(zfile) as zh:
            # zip comment should be kept
            self.assertEqual(zh.comment.decode('UTF-8'), 'test zip comment 測試')

            # for a nested archive file, force date and compress_type, keep others
            zinfo = zh.getinfo('entry1.zip')
            self.assertAlmostEqual(zip_timestamp(zinfo), datetime.now().timestamp(), delta=5)
            self.assertEqual(zinfo.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(oct(zip_mode(zinfo)), oct(0o700))

            with zh.open(zinfo) as fh1:
                with zipfile.ZipFile(fh1) as zh1:
                    self.assertEqual(zh1.comment.decode('UTF-8'), 'test zip comment 1 測試')

                    # replace
                    self.assertEqual(zh1.read('subdir/index.html').decode('UTF-8'), 'rewritten 測試')

                    # new
                    self.assertEqual(zh1.read('newdir/test.txt').decode('UTF-8'), 'new file 測試')


class TestHelpers(unittest.TestCase):
    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_isjunction1(self):
        # junction (target exists)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'target')
        dst = os.path.join(root, 'junction')
        os.makedirs(ref)
        util.fs.junction(ref, dst)
        self.assertTrue(util.fs.isjunction(dst))

        # junction (target nonexist)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        dst = os.path.join(root, 'junction')
        with test_file_cleanup(dst):
            util.fs.junction(ref, dst)
            self.assertTrue(util.fs.isjunction(dst))

        # directory
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'folder')
        os.makedirs(dst)
        self.assertFalse(util.fs.isjunction(dst))

        # file
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'file.txt')
        with open(dst, 'wb'):
            pass
        self.assertFalse(util.fs.isjunction(dst))

        # non-exist
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'nonexist')
        self.assertFalse(util.fs.isjunction(dst))

    @unittest.skipUnless(SYMLINK_SUPPORTED, 'requires symlink creation support')
    @unittest.skipUnless(platform.system() == 'Windows', 'requires Windows')
    def test_isjunction2(self):
        # symlink (directory, target exists)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'target')
        dst = os.path.join(root, 'symlink')
        os.makedirs(ref)
        os.symlink(ref, dst)
        self.assertFalse(util.fs.isjunction(dst))

        # symlink (file, target exists)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'file.txt')
        dst = os.path.join(root, 'symlink')
        with open(ref, 'wb'):
            pass
        os.symlink(ref, dst)
        self.assertFalse(util.fs.isjunction(dst))

        # symlink (directory, target nonexist)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'target')
        dst = os.path.join(root, 'symlink')
        os.symlink(ref, dst, True)
        self.assertFalse(util.fs.isjunction(dst))

        # symlink (file, target nonexist)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'file.txt')
        dst = os.path.join(root, 'symlink')
        os.symlink(ref, dst, False)
        self.assertFalse(util.fs.isjunction(dst))

    def test_zip_timestamp(self):
        # zinfo
        self.assertEqual(
            util.fs.zip_timestamp(zipfile.ZipInfo('dummy', DUMMY_ZIP_DT)),
            DUMMY_TS,
        )

        # tuple
        self.assertEqual(
            util.fs.zip_timestamp(DUMMY_ZIP_DT),
            DUMMY_TS,
        )

    def test_zip_mode(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        file = os.path.join(root, 'file.txt')
        with open(file, 'wb'):
            pass
        mode = os.stat(file).st_mode & 0xFFFF
        zinfo = zipfile.ZipInfo.from_file(file)

        # zinfo
        self.assertEqual(util.fs.zip_mode(zinfo), mode)

        # external_attr
        self.assertEqual(util.fs.zip_mode(zinfo.external_attr), mode)

    def test_zip_check_subpath(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', '123456')
            zh.writestr('explicit_folder/', '')
            zh.writestr('implicit_folder/.gitkeep', '1234')

        self.assertEqual(util.fs.zip_check_subpath(zfile, ''), util.fs.ZIP_SUBPATH_DIR_ROOT)
        self.assertEqual(util.fs.zip_check_subpath(zfile, '/'), util.fs.ZIP_SUBPATH_DIR_ROOT)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'file.txt'), util.fs.ZIP_SUBPATH_FILE)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'file.txt/'), util.fs.ZIP_SUBPATH_FILE)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'explicit_folder'), util.fs.ZIP_SUBPATH_DIR)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'explicit_folder/'), util.fs.ZIP_SUBPATH_DIR)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'implicit_folder'), util.fs.ZIP_SUBPATH_DIR_IMPLICIT)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'implicit_folder/'), util.fs.ZIP_SUBPATH_DIR_IMPLICIT)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'implicit_folder/.gitkeep'), util.fs.ZIP_SUBPATH_FILE)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'implicit_folder/.gitkeep/'), util.fs.ZIP_SUBPATH_FILE)

        self.assertEqual(util.fs.zip_check_subpath(zfile, 'nonexist'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'nonexist/'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'explicit_folder/nonexist'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'explicit_folder/nonexist/'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'implicit_folder/nonexist'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'implicit_folder/nonexist/'), util.fs.ZIP_SUBPATH_NONE)

        self.assertEqual(util.fs.zip_check_subpath(zfile, 'file.txt/nonexist'), util.fs.ZIP_SUBPATH_INVALID)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'file.txt/nonexist/'), util.fs.ZIP_SUBPATH_INVALID)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'implicit_folder/.gitkeep/nonexist'), util.fs.ZIP_SUBPATH_INVALID)
        self.assertEqual(util.fs.zip_check_subpath(zfile, 'implicit_folder/.gitkeep/nonexist/'), util.fs.ZIP_SUBPATH_INVALID)

    def test_zip_check_subpath_allow_invalid(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', '123456')
            zh.writestr('explicit_folder/', '')
            zh.writestr('implicit_folder/.gitkeep', '1234')
            zh.writestr('file.txt/badsubfile.txt', '123456')

        zip_check_subpath = functools.partial(util.fs.zip_check_subpath, allow_invalid=True)

        self.assertEqual(zip_check_subpath(zfile, ''), util.fs.ZIP_SUBPATH_DIR_ROOT)
        self.assertEqual(zip_check_subpath(zfile, '/'), util.fs.ZIP_SUBPATH_DIR_ROOT)
        self.assertEqual(zip_check_subpath(zfile, 'file.txt'), util.fs.ZIP_SUBPATH_FILE)
        self.assertEqual(zip_check_subpath(zfile, 'file.txt/'), util.fs.ZIP_SUBPATH_FILE)
        self.assertEqual(zip_check_subpath(zfile, 'explicit_folder'), util.fs.ZIP_SUBPATH_DIR)
        self.assertEqual(zip_check_subpath(zfile, 'explicit_folder/'), util.fs.ZIP_SUBPATH_DIR)
        self.assertEqual(zip_check_subpath(zfile, 'implicit_folder'), util.fs.ZIP_SUBPATH_DIR_IMPLICIT)
        self.assertEqual(zip_check_subpath(zfile, 'implicit_folder/'), util.fs.ZIP_SUBPATH_DIR_IMPLICIT)
        self.assertEqual(zip_check_subpath(zfile, 'implicit_folder/.gitkeep'), util.fs.ZIP_SUBPATH_FILE)
        self.assertEqual(zip_check_subpath(zfile, 'implicit_folder/.gitkeep/'), util.fs.ZIP_SUBPATH_FILE)

        self.assertEqual(zip_check_subpath(zfile, 'nonexist'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'nonexist/'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'explicit_folder/nonexist'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'explicit_folder/nonexist/'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'implicit_folder/nonexist'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'implicit_folder/nonexist/'), util.fs.ZIP_SUBPATH_NONE)

        self.assertEqual(zip_check_subpath(zfile, 'file.txt/nonexist'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'file.txt/nonexist/'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'implicit_folder/.gitkeep/nonexist'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'implicit_folder/.gitkeep/nonexist/'), util.fs.ZIP_SUBPATH_NONE)
        self.assertEqual(zip_check_subpath(zfile, 'file.txt/badsubfile.txt'), util.fs.ZIP_SUBPATH_FILE)

    def test_zip_compress_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'folder')
        src2 = os.path.join(root, 'folder', 'subfolder')
        src3 = os.path.join(root, 'folder', 'subfolder', 'subfolderfile.txt')
        src4 = os.path.join(root, 'folder', 'subfile.txt')
        src5 = os.path.join(root, 'file.txt')
        zfile = os.path.join(root, 'archive.zip')
        os.makedirs(src, exist_ok=True)
        os.makedirs(src2, exist_ok=True)
        with open(src3, 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF')
        with open(src4, 'w', encoding='UTF-8') as fh:
            fh.write('123456')
        with open(src5, 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')
        os.utime(src, (0, DUMMY_TS))
        os.utime(src2, (0, DUMMY_TS2))
        os.utime(src3, (0, DUMMY_TS3))
        os.utime(src3, (0, DUMMY_TS4))
        os.utime(src4, (0, DUMMY_TS5))
        os.utime(src5, (0, DUMMY_TS6))

        util.fs.zip_compress(zfile, src, 'myfolder')

        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'myfolder/',
                    'myfolder/subfolder/',
                    'myfolder/subfolder/subfolderfile.txt',
                    'myfolder/subfile.txt',
                },
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('myfolder/')),
                os.path.getmtime(src),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('myfolder/'))),
                oct(os.stat(src).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('myfolder/subfolder/')),
                os.path.getmtime(src2),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('myfolder/subfolder/'))),
                oct(os.stat(src2).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('myfolder/subfolder/subfolderfile.txt')),
                os.path.getmtime(src3),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('myfolder/subfolder/subfolderfile.txt'))),
                oct(os.stat(src3).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zh.read('myfolder/subfolder/subfolderfile.txt').decode('UTF-8'),
                'ABCDEF'
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('myfolder/subfile.txt')),
                os.path.getmtime(src4),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('myfolder/subfile.txt'))),
                oct(os.stat(src4).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zh.read('myfolder/subfile.txt').decode('UTF-8'),
                '123456',
            )

    def test_zip_compress_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'folder')
        src2 = os.path.join(root, 'folder', 'subfolder')
        src3 = os.path.join(root, 'folder', 'subfolder', 'subfolderfile.txt')
        src4 = os.path.join(root, 'folder', 'subfile.txt')
        src5 = os.path.join(root, 'file.txt')
        zfile = os.path.join(root, 'archive.zip')
        os.makedirs(src, exist_ok=True)
        os.makedirs(src2, exist_ok=True)
        with open(src3, 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF')
        with open(src4, 'w', encoding='UTF-8') as fh:
            fh.write('123456')
        with open(src5, 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')
        os.utime(src, (0, DUMMY_TS))
        os.utime(src2, (0, DUMMY_TS2))
        os.utime(src3, (0, DUMMY_TS3))
        os.utime(src3, (0, DUMMY_TS4))
        os.utime(src4, (0, DUMMY_TS5))
        os.utime(src5, (0, DUMMY_TS6))

        util.fs.zip_compress(zfile, src, '')

        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'subfolder/',
                    'subfolder/subfolderfile.txt',
                    'subfile.txt',
                },
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('subfolder/')),
                os.path.getmtime(src2),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('subfolder/'))),
                oct(os.stat(src2).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('subfolder/subfolderfile.txt')),
                os.path.getmtime(src3),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('subfolder/subfolderfile.txt'))),
                oct(os.stat(src3).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zh.read('subfolder/subfolderfile.txt').decode('UTF-8'),
                'ABCDEF'
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('subfile.txt')),
                os.path.getmtime(src4),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('subfile.txt'))),
                oct(os.stat(src4).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zh.read('subfile.txt').decode('UTF-8'),
                '123456',
            )

    def test_zip_compress_dir_filter(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'folder')
        src2 = os.path.join(root, 'folder', 'subfolder')
        src3 = os.path.join(root, 'folder', 'subfolder', 'subfolderfile.txt')
        src4 = os.path.join(root, 'folder', 'subfile.txt')
        src5 = os.path.join(root, 'file.txt')
        zfile = os.path.join(root, 'archive.zip')
        os.makedirs(src, exist_ok=True)
        os.makedirs(src2, exist_ok=True)
        with open(src3, 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF')
        with open(src4, 'w', encoding='UTF-8') as fh:
            fh.write('123456')
        with open(src5, 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')
        os.utime(src, (0, DUMMY_TS))
        os.utime(src2, (0, DUMMY_TS2))
        os.utime(src3, (0, DUMMY_TS3))
        os.utime(src3, (0, DUMMY_TS4))
        os.utime(src4, (0, DUMMY_TS5))
        os.utime(src5, (0, DUMMY_TS6))

        util.fs.zip_compress(zfile, src, 'myfolder', filter={'subfolder'})

        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'myfolder/',
                    'myfolder/subfolder/',
                    'myfolder/subfolder/subfolderfile.txt',
                },
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('myfolder/')),
                os.path.getmtime(src),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('myfolder/'))),
                oct(os.stat(src).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('myfolder/subfolder/')),
                os.path.getmtime(src2),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('myfolder/subfolder/'))),
                oct(os.stat(src2).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('myfolder/subfolder/subfolderfile.txt')),
                os.path.getmtime(src3),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('myfolder/subfolder/subfolderfile.txt'))),
                oct(os.stat(src3).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zh.read('myfolder/subfolder/subfolderfile.txt').decode('UTF-8'),
                'ABCDEF'
            )

    def test_zip_compress_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'file.txt')
        zfile = os.path.join(root, 'zipfile.zip')
        with open(src, 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')
        os.utime(src, (0, DUMMY_TS))

        util.fs.zip_compress(zfile, src, 'myfile.txt')

        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'myfile.txt',
                },
            )
            self.assertEqual(
                zip_timestamp(zh.getinfo('myfile.txt')),
                os.path.getmtime(src),
            )
            self.assertEqual(
                oct(zip_mode(zh.getinfo('myfile.txt'))),
                oct(os.stat(src).st_mode & 0xFFFF),
            )
            self.assertEqual(
                zh.read('myfile.txt').decode('UTF-8'),
                'ABC中文'
            )

    def test_zip_compress_file_to_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'file.txt')
        zfile = os.path.join(root, 'zipfile.zip')
        with open(src, 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')

        with self.assertRaises(ValueError):
            util.fs.zip_compress(zfile, src, '')

    def test_zip_compress_auto_compress_type(self):
        """Auto determime compress type"""
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'folder')
        src2 = os.path.join(root, 'folder', 'image.jpg')
        src3 = os.path.join(root, 'folder', 'text.txt')
        zfile = os.path.join(root, 'archive.zip')
        os.makedirs(src)
        with open(src2, 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF 中文')
        with open(src3, 'w', encoding='UTF-8') as fh:
            fh.write('123456 中文')

        util.fs.zip_compress(zfile, src, '')

        with zipfile.ZipFile(zfile) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'image.jpg',
                    'text.txt',
                },
            )
            self.assertEqual(
                zh.getinfo('image.jpg').compress_type,
                zipfile.ZIP_STORED,
            )
            self.assertEqual(
                zh.getinfo('text.txt').compress_type,
                zipfile.ZIP_DEFLATED,
            )

    def test_zip_compress_dir_stream(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        src = os.path.join(root, 'folder')
        src2 = os.path.join(root, 'folder', 'subfolder')
        src3 = os.path.join(root, 'folder', 'subfolder', 'subfolderfile.txt')
        src4 = os.path.join(root, 'folder', 'subfile.txt')
        src5 = os.path.join(root, 'file.txt')
        os.makedirs(src, exist_ok=True)
        os.makedirs(src2, exist_ok=True)
        with open(src3, 'w', encoding='UTF-8') as fh:
            fh.write('ABCDEF')
        with open(src4, 'w', encoding='UTF-8') as fh:
            fh.write('123456')
        with open(src5, 'w', encoding='UTF-8') as fh:
            fh.write('ABC中文')

        buf = io.BytesIO()
        for chunk in util.fs.zip_compress(None, src, 'myfolder'):
            buf.write(chunk)

        with zipfile.ZipFile(buf) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'myfolder/',
                    'myfolder/subfolder/',
                    'myfolder/subfolder/subfolderfile.txt',
                    'myfolder/subfile.txt',
                },
            )
            self.assertEqual(
                zh.getinfo('myfolder/subfolder/subfolderfile.txt').compress_type,
                zipfile.ZIP_STORED,
            )
            self.assertEqual(
                zh.getinfo('myfolder/subfile.txt').compress_type,
                zipfile.ZIP_STORED,
            )

    def test_zip_copy_dir_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        zfile2 = os.path.join(root, 'archive2.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir/', b'')
            zh.writestr('deep/subdir/file.txt', b'abc')
            zh.writestr('deep/subdir/explicit_dir/', b'')
            zh.writestr('deep/subdir/implicit_dir/subfile.txt', b'xyz')

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2, 'a') as zh:
            copied = util.fs.zip_copy(zi, 'deep/subdir', zh, 'deep/subdir2')

        self.assertEqual(
            copied,
            {
                'deep/subdir/',
                'deep/subdir/file.txt',
                'deep/subdir/explicit_dir/',
                'deep/subdir/implicit_dir/subfile.txt',
            },
        )

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'deep/subdir2/',
                    'deep/subdir2/file.txt',
                    'deep/subdir2/explicit_dir/',
                    'deep/subdir2/implicit_dir/subfile.txt',
                },
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/').date_time,
                zh.getinfo('deep/subdir2/').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/file.txt').date_time,
                zh.getinfo('deep/subdir2/file.txt').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/explicit_dir/').date_time,
                zh.getinfo('deep/subdir2/explicit_dir/').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/implicit_dir/subfile.txt').date_time,
                zh.getinfo('deep/subdir2/implicit_dir/subfile.txt').date_time,
            )

    def test_zip_copy_dir_to_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        zfile2 = os.path.join(root, 'archive2.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir/', b'')
            zh.writestr('deep/subdir/file.txt', b'abc')
            zh.writestr('deep/subdir/explicit_dir/', b'')
            zh.writestr('deep/subdir/implicit_dir/subfile.txt', b'xyz')

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2, 'a') as zh:
            copied = util.fs.zip_copy(zi, 'deep/subdir', zh, '')

        self.assertEqual(
            copied,
            {
                'deep/subdir/file.txt',
                'deep/subdir/explicit_dir/',
                'deep/subdir/implicit_dir/subfile.txt',
            },
        )

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'file.txt',
                    'explicit_dir/',
                    'implicit_dir/subfile.txt',
                },
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/file.txt').date_time,
                zh.getinfo('file.txt').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/explicit_dir/').date_time,
                zh.getinfo('explicit_dir/').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/implicit_dir/subfile.txt').date_time,
                zh.getinfo('implicit_dir/subfile.txt').date_time,
            )

    def test_zip_copy_root_to_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        zfile2 = os.path.join(root, 'archive2.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir/', b'')
            zh.writestr('deep/subdir/file.txt', b'abc')
            zh.writestr('deep/subdir/explicit_dir/', b'')
            zh.writestr('deep/subdir/implicit_dir/subfile.txt', b'xyz')

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2, 'a') as zh:
            copied = util.fs.zip_copy(zi, '', zh, 'newdir')

        self.assertEqual(
            copied,
            {
                'deep/subdir/',
                'deep/subdir/file.txt',
                'deep/subdir/explicit_dir/',
                'deep/subdir/implicit_dir/subfile.txt',
            },
        )

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'newdir/deep/subdir/',
                    'newdir/deep/subdir/file.txt',
                    'newdir/deep/subdir/explicit_dir/',
                    'newdir/deep/subdir/implicit_dir/subfile.txt',
                },
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/').date_time,
                zh.getinfo('newdir/deep/subdir/').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/file.txt').date_time,
                zh.getinfo('newdir/deep/subdir/file.txt').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/explicit_dir/').date_time,
                zh.getinfo('newdir/deep/subdir/explicit_dir/').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/implicit_dir/subfile.txt').date_time,
                zh.getinfo('newdir/deep/subdir/implicit_dir/subfile.txt').date_time,
            )

    def test_zip_copy_root_to_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        zfile2 = os.path.join(root, 'archive2.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir/', b'')
            zh.writestr('deep/subdir/file.txt', b'abc')
            zh.writestr('deep/subdir/explicit_dir/', b'')
            zh.writestr('deep/subdir/implicit_dir/subfile.txt', b'xyz')

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2, 'a') as zh:
            copied = util.fs.zip_copy(zi, '', zh, '')

        self.assertEqual(
            copied,
            {
                'deep/subdir/',
                'deep/subdir/file.txt',
                'deep/subdir/explicit_dir/',
                'deep/subdir/implicit_dir/subfile.txt',
            },
        )

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'deep/subdir/',
                    'deep/subdir/file.txt',
                    'deep/subdir/explicit_dir/',
                    'deep/subdir/implicit_dir/subfile.txt',
                },
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/').date_time,
                zh.getinfo('deep/subdir/').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/file.txt').date_time,
                zh.getinfo('deep/subdir/file.txt').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/explicit_dir/').date_time,
                zh.getinfo('deep/subdir/explicit_dir/').date_time,
            )
            self.assertEqual(
                zi.getinfo('deep/subdir/implicit_dir/subfile.txt').date_time,
                zh.getinfo('deep/subdir/implicit_dir/subfile.txt').date_time,
            )

    def test_zip_copy_dir_to_dir_filter(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        zfile2 = os.path.join(root, 'archive2.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/file.txt', b'abc')
            zh.writestr('deep/subdir/', b'')
            zh.writestr('deep/subdir/subfile.txt', b'abc')
            zh.writestr('deep/subdir/explicit_dir/', b'')
            zh.writestr('deep/subdir/implicit_dir/subfile.txt', b'xyz')

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2, 'a') as zh:
            copied = util.fs.zip_copy(zi, 'deep', zh, 'newdir', filter={'subdir'})

        self.assertEqual(
            copied,
            {
                'deep/subdir/',
                'deep/subdir/subfile.txt',
                'deep/subdir/explicit_dir/',
                'deep/subdir/implicit_dir/subfile.txt',
            },
        )

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'newdir/subdir/',
                    'newdir/subdir/subfile.txt',
                    'newdir/subdir/explicit_dir/',
                    'newdir/subdir/implicit_dir/subfile.txt',
                },
            )

    def test_zip_copy_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        zfile2 = os.path.join(root, 'archive2.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', b'abc')
            zh.writestr('file.txt/badsubfile.txt', b'abc')
            zh.writestr('subdir/', b'')
            zh.writestr('subdir/subfile.txt', b'abc')

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2, 'a') as zh:
            copied = util.fs.zip_copy(zi, 'file.txt', zh, 'newdir/file2.txt')

        self.assertEqual(
            copied,
            {
                'file.txt',
            },
        )

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'newdir/file2.txt',
                },
            )
            self.assertEqual(
                zi.getinfo('file.txt').date_time,
                zh.getinfo('newdir/file2.txt').date_time,
            )

    def test_zip_copy_file_to_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        zfile2 = os.path.join(root, 'archive2.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('file.txt', b'abc')
            zh.writestr('file.txt/badsubfile.txt', b'abc')
            zh.writestr('subdir/', b'')
            zh.writestr('subdir/subfile.txt', b'abc')

        with zipfile.ZipFile(zfile) as zi,\
             zipfile.ZipFile(zfile2, 'a') as zh:
            with self.assertRaises(ValueError):
                util.fs.zip_copy(zi, 'file.txt', zh, '')

    def test_zip_copy_dir_stream(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'archive.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr('deep/subdir/', b'')
            zh.writestr('deep/subdir/file.txt', b'abc', compress_type=zipfile.ZIP_BZIP2)
            zh.writestr('deep/subdir/explicit_dir/', b'')
            zh.writestr('deep/subdir/implicit_dir/subfile.txt', b'xyz', compress_type=zipfile.ZIP_BZIP2)

        buf = io.BytesIO()
        with zipfile.ZipFile(zfile) as zi:
            for chunk in util.fs.zip_copy(zi, 'deep/subdir', None, 'deep/subdir2'):
                buf.write(chunk)

        with zipfile.ZipFile(buf) as zh:
            self.assertEqual(
                set(zh.namelist()),
                {
                    'deep/subdir2/',
                    'deep/subdir2/file.txt',
                    'deep/subdir2/explicit_dir/',
                    'deep/subdir2/implicit_dir/subfile.txt',
                },
            )
            self.assertEqual(
                zh.getinfo('deep/subdir2/file.txt').compress_type,
                zipfile.ZIP_STORED,
            )
            self.assertEqual(
                zh.getinfo('deep/subdir2/implicit_dir/subfile.txt').compress_type,
                zipfile.ZIP_STORED,
            )

    def test_zip_extract_root(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        dst = os.path.join(root, 'zipfile')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', DUMMY_ZIP_DT), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', DUMMY_ZIP_DT2), '')
            zh.writestr(zipfile.ZipInfo('folder/subfile.txt', DUMMY_ZIP_DT3), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/subfile.txt', DUMMY_ZIP_DT4), 'abc')

        util.fs.zip_extract(zfile, dst)

        self.assertEqual(
            glob_files(dst),
            {
                os.path.join(dst, ''),
                os.path.join(dst, 'file.txt'),
                os.path.join(dst, 'folder'),
                os.path.join(dst, 'folder', 'subfile.txt'),
                os.path.join(dst, 'implicit_folder'),
                os.path.join(dst, 'implicit_folder', 'subfile.txt'),
            },
        )
        self.assertEqual(
            os.stat(os.path.join(dst, 'file.txt')).st_mtime,
            DUMMY_TS,
        )
        self.assertEqual(
            os.stat(os.path.join(dst, 'folder')).st_mtime,
            DUMMY_TS2,
        )
        self.assertEqual(
            os.stat(os.path.join(dst, 'folder', 'subfile.txt')).st_mtime,
            DUMMY_TS3,
        )
        self.assertEqual(
            os.stat(os.path.join(dst, 'implicit_folder', 'subfile.txt')).st_mtime,
            DUMMY_TS4,
        )

    def test_zip_extract_dir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        dst = os.path.join(root, 'folder')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', DUMMY_ZIP_DT), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', DUMMY_ZIP_DT2), '')
            zh.writestr(zipfile.ZipInfo('folder/subfile.txt', DUMMY_ZIP_DT3), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/subfile.txt', DUMMY_ZIP_DT4), 'abc')

        util.fs.zip_extract(zfile, dst, 'folder')

        self.assertEqual(
            glob_files(dst),
            {
                os.path.join(dst, ''),
                os.path.join(dst, 'subfile.txt'),
            },
        )
        self.assertEqual(
            os.stat(dst).st_mtime,
            DUMMY_TS2,
        )
        self.assertEqual(
            os.stat(os.path.join(dst, 'subfile.txt')).st_mtime,
            DUMMY_TS3,
        )

    def test_zip_extract_dir_implicit(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        dst = os.path.join(root, 'implicit_folder')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', DUMMY_ZIP_DT), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', DUMMY_ZIP_DT2), '')
            zh.writestr(zipfile.ZipInfo('folder/subfile.txt', DUMMY_ZIP_DT3), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/subfile.txt', DUMMY_ZIP_DT4), 'abc')

        util.fs.zip_extract(zfile, dst, 'implicit_folder')

        self.assertEqual(
            glob_files(dst),
            {
                os.path.join(dst, ''),
                os.path.join(dst, 'subfile.txt'),
            },
        )
        self.assertEqual(
            os.stat(os.path.join(dst, 'subfile.txt')).st_mtime,
            DUMMY_TS4,
        )

    def test_zip_extract_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        dst = os.path.join(root, 'zipfile.txt')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', DUMMY_ZIP_DT), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', DUMMY_ZIP_DT2), '')
            zh.writestr(zipfile.ZipInfo('folder/subfile.txt', DUMMY_ZIP_DT3), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/subfile.txt', DUMMY_ZIP_DT4), 'abc')

        util.fs.zip_extract(zfile, dst, 'file.txt')

        self.assertEqual(
            glob_files(dst),
            {
                os.path.join(dst, ''),
            },
        )
        self.assertEqual(
            os.stat(dst).st_mtime,
            DUMMY_TS,
        )

    def test_zip_extract_file_to_file(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        dst = os.path.join(root, 'subdir')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', DUMMY_ZIP_DT), 'ABC中文')
            zh.writestr(zipfile.ZipInfo('folder/', DUMMY_ZIP_DT2), '')
            zh.writestr(zipfile.ZipInfo('folder/subfile.txt', DUMMY_ZIP_DT3), '123456')
            zh.writestr(zipfile.ZipInfo('implicit_folder/subfile.txt', DUMMY_ZIP_DT4), 'abc')
        os.makedirs(dst)

        with self.assertRaises(FileExistsError):
            util.fs.zip_extract(zfile, dst, '')

        self.assertEqual(
            glob_files(dst),
            {
                os.path.join(dst, ''),
            },
        )

    def test_zip_extract_timezone(self):
        """Verify timezone adjustment"""
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        dst = os.path.join(root, 'zipfile')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', DUMMY_ZIP_DT), 'ABC中文')

        test_offset = -12345  # use a timezone offset which is unlikely really used
        util.fs.zip_extract(zfile, dst, tzoffset=test_offset)
        delta = datetime.now().astimezone().utcoffset().total_seconds()

        self.assertEqual(
            glob_files(dst),
            {
                os.path.join(dst, ''),
                os.path.join(dst, 'file.txt'),
            },
        )
        self.assertEqual(
            os.stat(os.path.join(dst, 'file.txt')).st_mtime,
            DUMMY_TS - test_offset + delta,
        )


class TestZipRemove(unittest.TestCase):
    def setUp(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        self.TESTFN = os.path.join(root, f'@test_{os.getpid()}_tmp')

    def _test_removing_indexes(self, test_files, indexes):
        """Test underlying _zip_remove_members() for removing members at given
        indexes."""
        # calculate the expected results
        expected_files = []
        with zipfile.ZipFile(self.TESTFN, 'w') as zh:
            for i, (file, data) in enumerate(test_files):
                if i not in indexes:
                    zh.writestr(file, data)
                    expected_files.append(file)
        expected_size = os.path.getsize(self.TESTFN)

        # prepare the test zip
        with zipfile.ZipFile(self.TESTFN, 'w') as zh:
            for file, data in test_files:
                zh.writestr(file, data)

        # do the removal and check the result
        with zipfile.ZipFile(self.TESTFN, 'a') as zh:
            members = {zh.infolist()[i] for i in indexes}
            util.fs._zip_remove_members(zh, members)

            # make sure internal caches have reflected the change
            # and are consistent
            self.assertEqual(zh.namelist(), expected_files)
            for file, _ in test_files:
                if file in zh.namelist():
                    self.assertEqual(zh.getinfo(file).filename, file)
                else:
                    with self.assertRaises(KeyError):
                        zh.getinfo(file)

            self.assertIsNone(zh.testzip())
        self.assertEqual(os.path.getsize(self.TESTFN), expected_size)

    def _test_removing_combinations(self, test_files, n=None):
        """Test underlying _zip_remove_members() for removing random combinations
        of members."""
        ln = len(test_files)
        if n is None:
            # iterate n from 1 to all
            for n in range(1, ln + 1):
                for indexes in itertools.combinations(range(ln), n):
                    with self.subTest(remove=indexes):
                        self._test_removing_indexes(test_files, indexes)
        else:
            for indexes in itertools.combinations(range(ln), n):
                with self.subTest(remove=indexes):
                    self._test_removing_indexes(test_files, indexes)

    def test_basic(self):
        # Test underlying _remove_members() for removing random combinations of members.
        test_files = [
            ('file0.txt', b'Lorem ipsum dolor sit amet, consectetur adipiscing elit'),
            ('file1.txt', b'Duis aute irure dolor in reprehenderit in voluptate velit esse'),
            ('file2.txt', b'Sed ut perspiciatis unde omnis iste natus error sit voluptatem'),
        ]

        self._test_removing_combinations(test_files)

    def test_duplicated_arcname(self):
        # Test underlying _remove_members() for removing any one of random duplicated members.

        # suppress duplicate name warning
        warnings.simplefilter('ignore', category=UserWarning)

        dupl_file = 'file.txt'
        test_files = [
            ('file0.txt', b'Lorem ipsum dolor sit amet, consectetur adipiscing elit'),
            ('file1.txt', b'Duis aute irure dolor in reprehenderit in voluptate velit esse'),
            ('file2.txt', b'Sed ut perspiciatis unde omnis iste natus error sit voluptatem'),
        ]

        ln = len(test_files)
        for n in range(2, ln + 1):
            for dups in itertools.combinations(range(ln), n):
                files = []
                for i, (file, data) in enumerate(test_files):
                    file_ = dupl_file if i in dups else file
                    files.append((file_, data))

                for index in dups:
                    indexes = [index]
                    with self.subTest(dups=dups, indexes=indexes):
                        self._test_removing_indexes(files, indexes)

    def test_non_physical(self):
        # Test underlying _remove_members() for non-physical removing.
        test_files = [
            ('file0.txt', b'Lorem ipsum dolor sit amet, consectetur adipiscing elit'),
            ('file1.txt', b'Duis aute irure dolor in reprehenderit in voluptate velit esse'),
            ('file2.txt', b'Sed ut perspiciatis unde omnis iste natus error sit voluptatem'),
        ]

        ln = len(test_files)
        for n in range(1, ln + 1):
            for indexes in itertools.combinations(range(ln), n):
                with self.subTest(remove=indexes):
                    # prepare the test zip
                    expected = {}
                    with zipfile.ZipFile(self.TESTFN, 'w') as zh:
                        for i, (file, data) in enumerate(test_files):
                            zh.writestr(file, data)
                            if i not in indexes:
                                expected[file] = zh.getinfo(file).header_offset

                    # do the removal and check the result
                    with zipfile.ZipFile(self.TESTFN, 'a') as zh:
                        members = {zh.infolist()[i] for i in indexes}
                        util.fs._zip_remove_members(zh, members, remove_physical=False)
                        self.assertEqual(zh.namelist(), list(expected))
                        for file, offset in expected.items():
                            self.assertEqual(zh.getinfo(file).header_offset, offset)
                        self.assertIsNone(zh.testzip())

    def test_verify(self):
        # Test if params are passed to underlying _remove_members() correctly,
        # or never passed if conditions not met.
        file0 = 'file0.txt'
        file = 'datafile.txt'
        data = b'Sed ut perspiciatis unde omnis iste natus error sit voluptatem'

        # closed: error and do nothing
        with zipfile.ZipFile(self.TESTFN, 'w') as zh:
            zh.writestr(file, data)
        with zipfile.ZipFile(self.TESTFN, 'a') as zh:
            zh.close()
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                with self.assertRaises(ValueError):
                    util.fs.zip_remove(zh, file)
                mock_fn.assert_not_called()

        # writing: error and do nothing
        with zipfile.ZipFile(self.TESTFN, 'w') as zh:
            zh.writestr(file, data)
        with zipfile.ZipFile(self.TESTFN, 'a') as zh:
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                with zh.open(file0, 'w'):
                    with self.assertRaises(ValueError):
                        util.fs.zip_remove(zh, file)
                mock_fn.assert_not_called()

        # mode 'r': error and do nothing
        with zipfile.ZipFile(self.TESTFN, 'r') as zh:
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                with self.assertRaises(ValueError):
                    util.fs.zip_remove(zh, file)
                mock_fn.assert_not_called()

        # mode 'a': the most general use case
        with zipfile.ZipFile(self.TESTFN, 'w') as zh:
            zh.writestr(file, data)

        # -- remove with arcname
        with zipfile.ZipFile(self.TESTFN, 'a') as zh:
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                util.fs.zip_remove(zh, file)
                mock_fn.assert_called_once_with(zh, (zh.getinfo(file),))

        # -- remove with zinfo
        with zipfile.ZipFile(self.TESTFN, 'a') as zh:
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                zinfo = zh.getinfo(file)
                util.fs.zip_remove(zh, zinfo)
                mock_fn.assert_called_once_with(zh, (zinfo,))

        # -- remove with nonexist arcname
        with zipfile.ZipFile(self.TESTFN, 'a') as zh:
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                with self.assertRaises(KeyError):
                    util.fs.zip_remove(zh, 'nonexist.file')
                mock_fn.assert_not_called()

        # -- remove with nonexist zinfo (even if same name)
        with zipfile.ZipFile(self.TESTFN, 'a') as zh:
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                zinfo = zipfile.ZipInfo(file)
                with self.assertRaises(KeyError):
                    util.fs.zip_remove(zh, zinfo)
                mock_fn.assert_not_called()

        # mode 'w': like 'a'; allows removing a just written member
        with zipfile.ZipFile(self.TESTFN, 'w') as zh:
            zh.writestr(file, data)
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                util.fs.zip_remove(zh, file)
                mock_fn.assert_called_once_with(zh, (zh.getinfo(file),))

        # mode 'x': like 'w'
        os.remove(self.TESTFN)
        with zipfile.ZipFile(self.TESTFN, 'x') as zh:
            zh.writestr(file, data)
            with mock.patch('webscrapbook.util.fs._zip_remove_members') as mock_fn:
                util.fs.zip_remove(zh, file)
                mock_fn.assert_called_once_with(zh, (zh.getinfo(file),))


if __name__ == '__main__':
    unittest.main()
