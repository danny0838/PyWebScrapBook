import io
import os
import platform
import subprocess
import tempfile
import time
import unittest
import zipfile
from datetime import datetime

from webscrapbook import util
from webscrapbook.util.fs import zip_tuple_timestamp

from . import ROOT_DIR, SYMLINK_SUPPORTED, TEMP_DIR

test_root = os.path.join(ROOT_DIR, 'test_util_fs')


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


class TestHelpers(unittest.TestCase):
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
            self.assertTrue(util.fs.file_is_link(entry))
        finally:
            # prevent tree cleanup issue for junction in Python 3.7
            os.remove(entry)

        # directory
        entry = os.path.join(test_root, 'file_info', 'folder')
        self.assertFalse(util.fs.file_is_link(entry))

        # file
        entry = os.path.join(test_root, 'file_info', 'file.txt')
        self.assertFalse(util.fs.file_is_link(entry))

        # non-exist
        entry = os.path.join(test_root, 'file_info', 'nonexist')
        self.assertFalse(util.fs.file_is_link(entry))

    @unittest.skipIf(platform.system() == 'Windows' and not SYMLINK_SUPPORTED,
                     'requires administrator or Developer Mode on Windows')
    def test_file_is_link2(self):
        # symlink
        entry = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'symlink')

        os.symlink(
            os.path.join(test_root, 'file_info', 'file.txt'),
            entry,
        )

        self.assertTrue(util.fs.file_is_link(entry))

    def test_file_info_nonexist(self):
        entry = os.path.join(test_root, 'file_info', 'nonexist.file')
        self.assertEqual(
            util.fs.file_info(entry),
            ('nonexist.file', None, None, None),
        )

    def test_file_info_file(self):
        entry = os.path.join(test_root, 'file_info', 'file.txt')
        self.assertEqual(
            util.fs.file_info(entry),
            ('file.txt', 'file', 3, os.stat(entry).st_mtime),
        )

    def test_file_info_dir(self):
        entry = os.path.join(test_root, 'file_info', 'folder')
        self.assertEqual(
            util.fs.file_info(entry),
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
                util.fs.file_info(entry),
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
                util.fs.file_info(entry),
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
            util.fs.file_info(entry),
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
            util.fs.file_info(entry),
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
            util.fs.file_info(entry),
            ('symlink', 'link', None, os.lstat(entry).st_mtime),
        )

    def test_listdir(self):
        entry = os.path.join(test_root, 'listdir')
        self.assertEqual(set(util.fs.listdir(entry)), {
            ('file.txt', 'file', 3, os.stat(os.path.join(entry, 'file.txt')).st_mtime),
            ('folder', 'dir', None, os.stat(os.path.join(entry, 'folder')).st_mtime),
        })
        self.assertEqual(set(util.fs.listdir(entry, recursive=True)), {
            ('file.txt', 'file', 3, os.stat(os.path.join(entry, 'file.txt')).st_mtime),
            ('folder', 'dir', None, os.stat(os.path.join(entry, 'folder')).st_mtime),
            ('folder/.gitkeep', 'file', 0, os.stat(os.path.join(entry, 'folder', '.gitkeep')).st_mtime),
        })

    def test_zip_fix_subpath(self):
        subpath = 'abc/def/測試.txt'
        self.assertEqual(util.fs.zip_fix_subpath(subpath), subpath)

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_fix_subpath_altsep(self):
        self.assertEqual(util.fs.zip_fix_subpath('abc\\def\\測試.txt'), 'abc/def/測試.txt')

    def test_zip_tuple_timestamp(self):
        self.assertEqual(
            util.fs.zip_tuple_timestamp((1987, 1, 1, 0, 0, 0)),
            time.mktime((1987, 1, 1, 0, 0, 0, 0, 0, -1)),
        )

    def test_zip_timestamp(self):
        self.assertEqual(
            util.fs.zip_timestamp(zipfile.ZipInfo('dummy', (1987, 1, 1, 0, 0, 0))),
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
            util.fs.zip_file_info(zip_filename, 'file.txt'),
            ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'folder'),
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'folder/'),
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'folder/.gitkeep'),
            ('.gitkeep', 'file', 3, zip_tuple_timestamp((1989, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, ''),
            ('', None, None, None),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'implicit_folder'),
            ('implicit_folder', None, None, None),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'implicit_folder/'),
            ('implicit_folder', None, None, None),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, '', check_implicit_dir=True),
            ('', 'dir', None, None),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'implicit_folder', check_implicit_dir=True),
            ('implicit_folder', 'dir', None, None),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'implicit_folder/', check_implicit_dir=True),
            ('implicit_folder', 'dir', None, None),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'implicit_folder/.gitkeep'),
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0))),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'nonexist'),
            ('nonexist', None, None, None),
        )

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'nonexist/'),
            ('nonexist', None, None, None),
        )

        # take zipfile.ZipFile
        with zipfile.ZipFile(zip_filename, 'r') as zh:
            self.assertEqual(
                util.fs.zip_file_info(zh, 'file.txt'),
                ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
            )

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_file_info_altsep(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('implicit_folder\\.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

        self.assertEqual(
            util.fs.zip_file_info(zip_filename, 'implicit_folder\\.gitkeep'),
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0))),
        )

    def test_zip_listdir(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), '123456')
            zh.writestr(zipfile.ZipInfo('folder/', (1988, 1, 1, 0, 0, 0)), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', (1989, 1, 1, 0, 0, 0)), '123')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

        self.assertEqual(set(util.fs.zip_listdir(zip_filename, '')), {
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
            ('implicit_folder', 'dir', None, None),
            ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
        })

        self.assertEqual(set(util.fs.zip_listdir(zip_filename, '/')), {
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
            ('implicit_folder', 'dir', None, None),
            ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
        })

        self.assertEqual(set(util.fs.zip_listdir(zip_filename, '', recursive=True)), {
            ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
            ('folder/.gitkeep', 'file', 3, zip_tuple_timestamp((1989, 1, 1, 0, 0, 0))),
            ('implicit_folder', 'dir', None, None),
            ('implicit_folder/.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0))),
            ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
        })

        self.assertEqual(set(util.fs.zip_listdir(zip_filename, 'folder')), {
            ('.gitkeep', 'file', 3, zip_tuple_timestamp((1989, 1, 1, 0, 0, 0)))
        })

        self.assertEqual(set(util.fs.zip_listdir(zip_filename, 'folder/')), {
            ('.gitkeep', 'file', 3, zip_tuple_timestamp((1989, 1, 1, 0, 0, 0)))
        })

        self.assertEqual(set(util.fs.zip_listdir(zip_filename, 'implicit_folder')), {
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0)))
        })

        self.assertEqual(set(util.fs.zip_listdir(zip_filename, 'implicit_folder/')), {
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0)))
        })

        with self.assertRaises(util.fs.ZipDirNotFoundError):
            set(util.fs.zip_listdir(zip_filename, 'nonexist'))

        with self.assertRaises(util.fs.ZipDirNotFoundError):
            set(util.fs.zip_listdir(zip_filename, 'nonexist/'))

        with self.assertRaises(util.fs.ZipDirNotFoundError):
            set(util.fs.zip_listdir(zip_filename, 'file.txt'))

        # take zipfile.ZipFile
        with zipfile.ZipFile(zip_filename, 'r') as zh:
            self.assertEqual(set(util.fs.zip_listdir(zh, '')), {
                ('folder', 'dir', None, zip_tuple_timestamp((1988, 1, 1, 0, 0, 0))),
                ('implicit_folder', 'dir', None, None),
                ('file.txt', 'file', 6, zip_tuple_timestamp((1987, 1, 1, 0, 0, 0))),
            })

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_listdir_altsep(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo(r'implicit_folder\.gitkeep', (1990, 1, 1, 0, 0, 0)), '1234')

        self.assertEqual(set(util.fs.zip_listdir(zip_filename, 'implicit_folder\\')), {
            ('.gitkeep', 'file', 4, zip_tuple_timestamp((1990, 1, 1, 0, 0, 0)))
        })

    def test_zip_has(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr('file.txt', '123456')
            zh.writestr('explicit_folder/', '')
            zh.writestr('implicit_folder/.gitkeep', '1234')

        self.assertTrue(util.fs.zip_has(zip_filename, '', type='dir'))
        self.assertTrue(util.fs.zip_has(zip_filename, '/', type='dir'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'file.txt', type='dir'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'file.txt/', type='dir'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'explicit_folder', type='dir'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'explicit_folder/', type='dir'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder', type='dir'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder/', type='dir'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'implicit_folder/.gitkeep', type='dir'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'implicit_folder/.gitkeep/', type='dir'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'nonexist.foo', type='dir'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'nonexist/', type='dir'))

        self.assertFalse(util.fs.zip_has(zip_filename, '', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, '/', type='file'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'file.txt', type='file'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'file.txt/', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'explicit_folder', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'explicit_folder/', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'implicit_folder', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'implicit_folder/', type='file'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder/.gitkeep', type='file'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder/.gitkeep/', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'nonexist.foo', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'nonexist/', type='file'))

        self.assertTrue(util.fs.zip_has(zip_filename, '', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, '/', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'file.txt', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'file.txt/', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'explicit_folder', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'explicit_folder/', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder/', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder/.gitkeep', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder/.gitkeep/', type='any'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'nonexist.foo', type='any'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'nonexist/', type='any'))

    @unittest.skipUnless(os.sep != '/', 'requires os.sep != "/"')
    def test_zip_has_altsep(self):
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr('implicit_folder\\.gitkeep', '1234')

        self.assertTrue(util.fs.zip_has(zip_filename, '', type='dir'))
        self.assertTrue(util.fs.zip_has(zip_filename, '\\', type='dir'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder', type='dir'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder\\', type='dir'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'implicit_folder\\.gitkeep', type='dir'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'implicit_folder\\.gitkeep\\', type='dir'))

        self.assertFalse(util.fs.zip_has(zip_filename, '', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, '\\', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'implicit_folder', type='file'))
        self.assertFalse(util.fs.zip_has(zip_filename, 'implicit_folder\\', type='file'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder\\.gitkeep', type='file'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder\\.gitkeep\\', type='file'))

        self.assertTrue(util.fs.zip_has(zip_filename, '', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, '\\', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder\\', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder\\.gitkeep', type='any'))
        self.assertTrue(util.fs.zip_has(zip_filename, 'implicit_folder\\.gitkeep\\', type='any'))

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

        util.fs.zip_compress(zip_filename, os.path.join(temp_dir, 'folder'), 'myfolder')

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

        util.fs.zip_compress(zip_filename, os.path.join(temp_dir, 'folder'), '')

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

        util.fs.zip_compress(zip_filename, os.path.join(temp_dir, 'folder'), 'myfolder', filter={'subfolder'})

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

        util.fs.zip_compress(zip_filename, os.path.join(temp_dir, 'file.txt'), 'myfile.txt')

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

        util.fs.zip_compress(zip_filename, os.path.join(temp_dir, 'folder'), 'sub\\folder')

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

        util.fs.zip_extract(zip_filename, os.path.join(temp_dir, 'zipfile'))

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

        util.fs.zip_extract(zip_filename, os.path.join(temp_dir, 'folder'), 'folder')

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

        util.fs.zip_extract(zip_filename, os.path.join(temp_dir, 'implicit_folder'), 'implicit_folder')

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

        util.fs.zip_extract(zip_filename, os.path.join(temp_dir, 'zipfile.txt'), 'file.txt')

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
            util.fs.zip_extract(zip_filename, temp_dir, '')

    def test_zip_extract06(self):
        """timezone adjust"""
        temp_dir = tempfile.mkdtemp(dir=tmpdir)
        zip_filename = os.path.join(tempfile.mkdtemp(dir=tmpdir), 'zipfile.zip')

        with zipfile.ZipFile(zip_filename, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', (1987, 1, 1, 0, 0, 0)), 'ABC中文')

        test_offset = -12345  # use a timezone offset which is unlikely really used
        util.fs.zip_extract(zip_filename, os.path.join(temp_dir, 'zipfile'), tzoffset=test_offset)
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

        util.fs.zip_extract(zip_filename, os.path.join(temp_dir, 'folder'), 'sub\\folder')

        self.assertEqual(
            os.stat(os.path.join(temp_dir, 'folder', '.gitkeep')).st_mtime,
            zip_tuple_timestamp((1987, 1, 4, 0, 0, 0)),
        )

    def test_open_archive_path_read(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zip_file = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zip_file, 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                buf11 = io.BytesIO()
                with zipfile.ZipFile(buf11, 'w') as zh2:
                    zh2.writestr('subdir/index.html', 'Hello World!')
                zh1.writestr('entry2.zip', buf11.getvalue())
            zh.writestr('entry1.zip', buf1.getvalue())

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'entry2.zip', 'subdir/index.html']) as zh:
            self.assertEqual(zh.read('subdir/index.html').decode('UTF-8'), 'Hello World!')

        with self.assertRaises(ValueError):
            with util.fs.open_archive_path([zip_file]) as zh:
                pass

    def test_open_archive_path_write(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zip_file = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zip_file, 'w') as zh:
            zh.comment = 'test zip comment 測試'.encode('UTF-8')
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                zh1.comment = 'test zip comment 1 測試'.encode('UTF-8')
                zh1.writestr('subdir/index.html', 'Hello World!')
            zh.writestr('entry1.zip', buf1.getvalue())

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html'], 'w') as zh:
            # existed
            zh.writestr('subdir/index.html', 'rewritten 測試')

            # new
            zh.writestr('newdir/test.txt', 'new file 測試')

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html']) as zh:
            # existed
            self.assertEqual(zh.read('subdir/index.html').decode('UTF-8'), 'rewritten 測試')

            # new
            self.assertEqual(zh.read('newdir/test.txt').decode('UTF-8'), 'new file 測試')

        # check comments are kept
        with util.fs.open_archive_path([zip_file, '']) as zh:
            self.assertEqual(zh.comment.decode('UTF-8'), 'test zip comment 測試')

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html']) as zh:
            self.assertEqual(zh.comment.decode('UTF-8'), 'test zip comment 1 測試')

    def test_open_archive_path_delete(self):
        # file
        root = tempfile.mkdtemp(dir=tmpdir)
        zip_file = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zip_file, 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                zh1.writestr('subdir/', '')
                zh1.writestr('subdir/index.html', 'Hello World!')
                zh1.writestr('subdir2/test.txt', 'dummy')
            zh.writestr('entry1.zip', buf1.getvalue())

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html'], 'w', ['subdir/index.html']):
            pass

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html']) as zh:
            self.assertEqual(zh.namelist(), ['subdir/', 'subdir2/test.txt'])

        # explicit directory
        root = tempfile.mkdtemp(dir=tmpdir)
        zip_file = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zip_file, 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                zh1.writestr('subdir/', '')
                zh1.writestr('subdir/index.html', 'Hello World!')
                zh1.writestr('subdir2/test.txt', 'dummy')
            zh.writestr('entry1.zip', buf1.getvalue())

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html'], 'w', ['subdir']):
            pass

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html']) as zh:
            self.assertEqual(zh.namelist(), ['subdir2/test.txt'])

        # implicit directory
        root = tempfile.mkdtemp(dir=tmpdir)
        zip_file = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zip_file, 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                zh1.writestr('subdir/', '')
                zh1.writestr('subdir/index.html', 'Hello World!')
                zh1.writestr('subdir2/test.txt', 'dummy')
            zh.writestr('entry1.zip', buf1.getvalue())

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html'], 'w', ['subdir2']):
            pass

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html']) as zh:
            self.assertEqual(zh.namelist(), ['subdir/', 'subdir/index.html'])

        # root (as an implicit directory)
        root = tempfile.mkdtemp(dir=tmpdir)
        zip_file = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zip_file, 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                zh1.writestr('subdir/', '')
                zh1.writestr('subdir/index.html', 'Hello World!')
                zh1.writestr('subdir2/test.txt', 'dummy')
            zh.writestr('entry1.zip', buf1.getvalue())

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html'], 'w', ['']):
            pass

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html']) as zh:
            self.assertEqual(zh.namelist(), [])

        # multiple
        root = tempfile.mkdtemp(dir=tmpdir)
        zip_file = os.path.join(root, 'entry.zip')
        with zipfile.ZipFile(zip_file, 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                zh1.writestr('subdir/', '')
                zh1.writestr('subdir/index.html', 'Hello World!')
                zh1.writestr('subdir2/test.txt', 'dummy')
            zh.writestr('entry1.zip', buf1.getvalue())

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html'], 'w', ['subdir', 'subdir2']):
            pass

        with util.fs.open_archive_path([zip_file, 'entry1.zip', 'subdir/index.html']) as zh:
            self.assertEqual(zh.namelist(), [])


if __name__ == '__main__':
    unittest.main()
