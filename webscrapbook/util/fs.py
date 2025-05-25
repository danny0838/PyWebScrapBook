"""Virtual filesystem for complex file operation."""
import copy as _copy
import functools
import io
import itertools
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager, nullcontext
from datetime import datetime

from .._polyfill import mimetypes, zipfile
from . import util

ZIP_SUBPATH_NONE = 0
ZIP_SUBPATH_INVALID = 1
ZIP_SUBPATH_FILE = 2
ZIP_SUBPATH_DIR = 3
ZIP_SUBPATH_DIR_IMPLICIT = 4
ZIP_SUBPATH_DIR_ROOT = 5
ZIP_SUBPATH_MIXED = 6


class FSError(Exception):
    def __init__(self, cpath):
        self.cpath = cpath
        self.msg = 'Unexpected error'

    def __str__(self):
        return f'{self.msg}: {self.cpath}'

    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.msg)})'


class FSPermissionError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Permission denied'


class FSEntryExistsError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Entry already exists'


class FSFileExistsError(FSEntryExistsError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'File already exists'


class FSDirExistsError(FSEntryExistsError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Directory already exists'


class FSEntryNotFoundError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Entry is not found'


class FSFileNotFoundError(FSEntryNotFoundError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'File is not found'


class FSDirNotFoundError(FSEntryNotFoundError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Directory is not found'


class FSNotADirectoryError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Entry is not a directory'


class FSIsADirectoryError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Entry is a directory'


class FSBadParentError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Parent directory is not available'


class FSBadZipFileError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'ZIP file is corrupted'


class FSMoveInsideError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Unable to move into self'


class FSMoveAcrossZipError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Unable to move across a zip'


class FSPartialError(FSError):
    def __init__(self, cpath):
        super().__init__(cpath)
        self.msg = 'Some subentries are not operated correctly'


def _map_exc(exc, cpath=None):
    """Get a general exception type from a standard exception."""
    if isinstance(exc, PermissionError):
        return FSPermissionError(cpath)

    elif isinstance(exc, FileNotFoundError):
        return FSEntryNotFoundError(cpath)

    elif isinstance(exc, NotADirectoryError):
        # This usually happens on most POSIX platforms when an ancestor
        # directory cannot be traversed (e.g. occupied by a file).
        # Treat as entry not found in general.
        return FSEntryNotFoundError(cpath)

    elif isinstance(exc, FileExistsError):
        return FSEntryExistsError(cpath)

    elif isinstance(exc, zipfile.BadZipFile):
        return FSBadZipFileError(cpath)

    # unexpected error
    return FSError(cpath)


class CPath:
    """A complex path object representing filesystem path and ZIP subpaths."""
    def __new__(cls, pathlike, *subpaths):
        """Get a singleton new CPath from pathlike."""
        if isinstance(pathlike, cls) and not subpaths:
            return pathlike
        self = super().__new__(cls)
        self.__init__(pathlike, *subpaths)
        return self

    def __init__(self, pathlike, *subpaths):
        if isinstance(pathlike, str):
            self._path = [pathlike]
        elif isinstance(pathlike, CPath):
            self._path = pathlike.path.copy()
        elif isinstance(pathlike, list):
            self._path = pathlike.copy()
        elif isinstance(pathlike, tuple):
            self._path = list(pathlike)
        elif isinstance(pathlike, dict):
            self._path = list(pathlike)
        else:  # pathlib.Path etc.
            self._path = [str(pathlike)]

        if subpaths:
            self._path.extend(str(s) for s in subpaths)

    def __str__(self):
        return '!/'.join(self._path)

    def __repr__(self):
        path = ', '.join(repr(p) for p in self._path)
        return f'{self.__class__.__name__}({path})'

    def __len__(self):
        return len(self._path)

    def __getitem__(self, key):
        return self._path[key]

    def __eq__(self, other):
        return self._path == other

    def copy(self):
        return self.__class__(self._path)

    @property
    def path(self):
        return self._path

    @property
    def file(self):
        return self._path[0]

    @classmethod
    def resolve(cls, plainpath, resolver=None):
        """Resolves a plainpath with '!/' to a CPath.

        - Priority:
          entry.zip!/entry1.zip!/ = entry.zip!/entry1.zip! >
          entry.zip!/entry1.zip >
          entry.zip!/ = entry.zip! >
          entry.zip

        - If resolver is provided, the result file path (first segment) will
          only be tidied; otherwise it will be normalized.

        Args:
            plainpath: a path string that may contain '!/'
            resolver: a function that resolves a path to real filesystem path

        Returns:
            CPath
        """
        paths = []
        for start, end in cls._resolve_iter_sep(plainpath):
            archivepath = plainpath[:start]
            if resolver:
                archivepath = cls._resolve_tidy_subpath(archivepath)
                archivefile = resolver(archivepath)
            else:
                archivepath = archivefile = os.path.normpath(archivepath)
            conflicting = archivefile + '!'

            if os.path.lexists(conflicting):
                break

            # if parent directory does not exist, FileNotFoundError is raised on
            # Windows, while NotADirectoryError is raised on Linux
            try:
                zh = zipfile.ZipFile(archivefile, 'r')
            except (zipfile.BadZipFile, FileNotFoundError, NotADirectoryError):
                continue

            with zh as zh:
                paths.append(archivepath)
                cls._resolve_add_subpath(paths, zh, plainpath[end:])
                return cls(paths)

        archivepath = plainpath
        if resolver:
            archivepath = cls._resolve_tidy_subpath(archivepath)
        else:
            archivepath = os.path.normpath(archivepath)
        paths.append(archivepath)
        return cls(paths)

    @classmethod
    def _resolve_add_subpath(cls, paths, zh, subpath):
        for start, end in cls._resolve_iter_sep(subpath):
            archivepath = cls._resolve_tidy_subpath(subpath[:start], True)
            conflicting = archivepath + '!/'

            if any(i.startswith(conflicting) for i in zh.namelist()):
                break

            try:
                fh = zh.open(archivepath)
            except KeyError:
                continue

            with fh as fh:
                try:
                    zh1 = zipfile.ZipFile(fh)
                except zipfile.BadZipFile:
                    continue

                with zh1 as zh1:
                    paths.append(archivepath)
                    cls._resolve_add_subpath(paths, zh1, subpath[end:])
                    return

        paths.append(cls._resolve_tidy_subpath(subpath, True))

    @classmethod
    def _resolve_iter_sep(cls, path):
        pos = None
        while True:
            try:
                pos = path.rindex('!/', 0, pos)
            except ValueError:
                break
            yield pos, pos + 2

    @classmethod
    def _resolve_tidy_subpath(cls, path, striproot=False):
        """Tidy a subpath with possible '.', '..', '//', etc."""
        has_initial_slash = path.startswith('/')
        comps = path.split('/')
        new_comps = []
        for comp in comps:
            if comp in ('', '.'):
                continue
            if comp == '..':
                if new_comps:
                    new_comps.pop()
                continue
            new_comps.append(comp)
        return ('/' if has_initial_slash and not striproot else '') + '/'.join(new_comps)


def launch(cpath):
    """Launch a file or open a directory in the explorer.
    """
    cpath = CPath(cpath)

    if len(cpath) > 1:
        raise ValueError('Launching inside a ZIP is not supported')

    path = cpath.file

    if sys.platform == 'win32':
        os.startfile(path)
    elif sys.platform == 'darwin':
        subprocess.run(['open', path])
    else:
        subprocess.run(['xdg-open', path])


def view_in_explorer(cpath):
    """Open the parent directory of a file or directory in the explorer."""
    cpath = CPath(cpath)

    if len(cpath) > 1:
        raise ValueError('Viewing inside a ZIP is not supported')

    path = cpath.file

    if sys.platform == 'win32':
        subprocess.run(['explorer', '/select,', path])
    elif sys.platform == 'darwin':
        try:
            subprocess.run(['open', '-R', path])
        except OSError:
            # fallback for older OS X
            launch(os.path.dirname(path))
    else:
        try:
            subprocess.run(['nautilus', '--select', path])
        except OSError:
            # fallback if no nautilus
            launch(os.path.dirname(path))


def mkdir(cpath, mode=0o777, exist_ok=True):
    """Create a directory at target."""
    cpath = CPath(cpath)
    try:
        if len(cpath) == 1:
            try:
                os.makedirs(cpath.file, mode, exist_ok)
            except (FileNotFoundError, NotADirectoryError) as exc:
                raise FSBadParentError(cpath) from exc

        else:
            # 'r' mode to check if zip is valid
            with open_archive_path(cpath) as zh:
                cur = zip_check_subpath(zh, cpath[-1])
                if cur == ZIP_SUBPATH_INVALID:
                    raise FSBadParentError(cpath)
                elif cur == ZIP_SUBPATH_FILE:
                    raise FSFileExistsError(cpath)
                elif cur in (ZIP_SUBPATH_DIR, ZIP_SUBPATH_DIR_ROOT):
                    if exist_ok:
                        return
                    raise FSDirExistsError(cpath)

            with open_archive_path(cpath, 'a') as zh:
                zinfo = zipfile.ZipInfo(cpath[-1] + '/', time.localtime())
                zinfo.external_attr = ((0o40000 | mode) & 0xFFFF) << 16  # Unix attributes
                zinfo.external_attr |= 0x10  # MS-DOS directory flag
                zinfo.compress_type = zipfile.ZIP_STORED
                zh.writestr(zinfo, b'')
    except FSError:
        raise
    except Exception as exc:
        raise _map_exc(exc, cpath) from exc


def mkzip(cpath):
    """Create a ZIP file at target."""
    cpath = CPath(cpath)
    try:
        if len(cpath) == 1:
            dst = cpath.file
            if os.path.lexists(dst) and not os.path.isfile(dst):
                raise FSIsADirectoryError(cpath)

            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
            except OSError as exc:
                raise FSBadParentError(cpath) from exc

            with zipfile.ZipFile(dst, 'w'):
                pass

        else:
            # 'r' mode to check if zip is valid
            with open_archive_path(cpath) as zh:
                cur = zip_check_subpath(zh, cpath[-1])
                if cur == ZIP_SUBPATH_INVALID:
                    raise FSBadParentError(cpath)
                elif cur in (ZIP_SUBPATH_DIR, ZIP_SUBPATH_DIR_IMPLICIT, ZIP_SUBPATH_DIR_ROOT):
                    raise FSIsADirectoryError(cpath)

            with open_archive_path(cpath, 'a') as zh:
                if cur == ZIP_SUBPATH_FILE:
                    zinfo = zh.getinfo(cpath[-1])
                    zip_remove(zh, zinfo)
                    zinfo.date_time = time.localtime()
                else:
                    zinfo = zipfile.ZipInfo(cpath[-1], time.localtime())
                zinfo.compress_type = zipfile.ZIP_STORED
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w'):
                    pass
                zh.writestr(zinfo, buf.getvalue())
    except FSError:
        raise
    except Exception as exc:
        raise _map_exc(exc, cpath) from exc


def save(cpath, src, *, buffer_size=None):
    """Write content to the target.

    Args:
        src: bytes or a stream object (with callble 'read' attribute)
    """
    cpath = CPath(cpath)
    try:
        if len(cpath) == 1:
            dst = cpath.file
            if os.path.lexists(dst) and not os.path.isfile(dst):
                raise FSIsADirectoryError(cpath)

            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
            except OSError as exc:
                raise FSBadParentError(cpath) from exc

            with open(dst, 'wb') as fh:
                _save_write(fh, src, buffer_size=buffer_size)

        else:
            # 'r' mode to check if zip is valid
            with open_archive_path(cpath) as zh:
                cur = zip_check_subpath(zh, cpath[-1])
                if cur == ZIP_SUBPATH_INVALID:
                    raise FSBadParentError(cpath)
                elif cur in (ZIP_SUBPATH_DIR, ZIP_SUBPATH_DIR_IMPLICIT, ZIP_SUBPATH_DIR_ROOT):
                    raise FSIsADirectoryError(cpath)

            with open_archive_path(cpath, 'a') as zh:
                if cur == ZIP_SUBPATH_FILE:
                    zinfo = zh.getinfo(cpath[-1])
                    zip_remove(zh, zinfo)
                    zinfo.date_time = time.localtime()
                else:
                    zinfo = zipfile.ZipInfo(cpath[-1], time.localtime())
                    comp = zip_compression_params(mimetypes.guess_type(cpath[-1])[0])
                    zinfo.compress_type = comp['compress_type']
                    zinfo._compresslevel = comp['compresslevel']

                with zh.open(zinfo, 'w') as fh:
                    _save_write(fh, src, buffer_size=buffer_size)

    except FSError:
        raise
    except Exception as exc:
        raise _map_exc(exc, cpath) from exc


def _save_write(fh, src, *, buffer_size=None):
    if isinstance(src, bytes):
        fh.write(src)
        return

    try:
        assert callable(src.read)
    except (AssertionError, AttributeError):
        pass
    else:
        shutil.copyfileobj(src, fh, buffer_size)
        return

    raise ValueError('src must be bytes or a stream')


def delete(cpath):
    """Delete the target."""
    cpath = CPath(cpath)
    try:
        if len(cpath) == 1:
            dst = cpath.file

            if not os.path.lexists(dst):
                raise FSEntryNotFoundError(cpath)

            try:
                os.remove(dst)
            except OSError:
                shutil.rmtree(dst)

        else:
            # 'r' mode to check if zip is valid
            with open_archive_path(cpath):
                pass

            with open_archive_path(cpath, 'a') as zh:
                base = cpath[-1]
                base_dir = base + ('/' if base else '')
                zinfos = {i for i in zh.infolist() if i.filename == base or i.filename.startswith(base_dir)}

                # fail if nothing to delete
                if not zinfos:
                    raise FSEntryNotFoundError(cpath)

                _zip_remove_members(zh, zinfos)
    except FSError:
        raise
    except Exception as exc:
        raise _map_exc(exc, cpath) from exc


def _check_move_copy(csrc, cdst):
    """Common checks for a move or copy.

    Returns:
        cdst: the possibly changed cdst
        zstsrc: path stat in the zip of csrc
        zstdst: path stat in the zip of cdst
    """
    zstsrc = None
    zstdst = None

    if len(csrc) == 1:
        if not os.path.lexists(csrc.file):
            raise FSEntryNotFoundError(csrc)
    else:
        with open_archive_path(csrc) as zh:
            cur = zip_check_subpath(zh, csrc[-1])
            if cur in (ZIP_SUBPATH_NONE, ZIP_SUBPATH_DIR_ROOT):
                raise FSEntryNotFoundError(csrc)
            elif cur == ZIP_SUBPATH_INVALID:
                raise FSBadParentError(csrc)
            zstsrc = cur

    if len(cdst) == 1:
        if os.path.lexists(cdst.file):
            if os.path.isdir(cdst.file):
                # target is an existing directory, treat as to target/<basename>
                cdst = CPath(os.path.join(cdst.file, os.path.basename(csrc[-1])))

                # recheck if target exists
                if os.path.lexists(cdst.file):
                    raise FSEntryExistsError(cdst)
            else:
                raise FSEntryExistsError(cdst)
    else:
        with open_archive_path(cdst) as zh:
            cur = zip_check_subpath(zh, cdst[-1])
            if cur == ZIP_SUBPATH_INVALID:
                raise FSBadParentError(cdst)
            elif cur == ZIP_SUBPATH_FILE:
                raise FSFileExistsError(cdst)
            elif cur in (ZIP_SUBPATH_DIR, ZIP_SUBPATH_DIR_IMPLICIT, ZIP_SUBPATH_DIR_ROOT):
                # target is an existing directory, treat as to target/<basename>
                cdst = CPath([
                    *cdst[:-1],
                    cdst[-1] + ('/' if cdst[-1] else '') + os.path.basename(csrc[-1]),
                ])

                # recheck if target exists
                if zip_check_subpath(zh, cdst[-1]) in (ZIP_SUBPATH_FILE, ZIP_SUBPATH_DIR, ZIP_SUBPATH_DIR_IMPLICIT):
                    raise FSEntryExistsError(cdst)
            zstdst = cur

    return cdst, zstsrc, zstdst


def _check_move(csrc, cdst):
    if not _dstinsrc(csrc.file, cdst.file):
        return True

    # ['some/path'] => ['some/path']
    # ['some/path'] => ['some/path/deeper']
    # ['some/archive.zip'] => ['some/archive.zip', ...]
    # ['some/archive.zip', ...] => ['some/archive.zip']
    for i in range(1, len(cdst)):
        dst = cdst[i] + '/'
        try:
            src = csrc[i] + '/'
        except IndexError:
            # [..., 'some/archive.zip'] => [..., 'some/archive.zip', ...]
            return False

        if not dst.startswith(src):
            return True

        if len(dst) > len(src):
            # [..., 'some/path'] => [..., 'some/path/subpath']
            return False

    return False


def _dstinsrc(src, dst):
    """Check if dst is inside src.

    Revised version of official shutil._dstinsrc.
    """
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)

    src_chk = os.path.normcase(src).lower()
    dst_chk = os.path.normcase(dst).lower()
    if not src_chk.endswith(os.path.sep):
        src_chk += os.path.sep
    if not dst_chk.endswith(os.path.sep):
        dst_chk += os.path.sep
    if not dst_chk.startswith(src_chk):
        return False

    try:
        return os.lstat(src) == os.lstat(dst[:len(src)])
    except OSError:
        return False


def move(csrc, cdst):
    """Move the source to the target."""
    csrc = CPath(csrc)
    cdst = CPath(cdst)
    try:
        cdst, zstsrc, zstdst = _check_move_copy(csrc, cdst)

        if not _check_move(csrc, cdst):
            raise FSMoveInsideError(cdst)

        if len(csrc) == 1:
            if len(cdst) == 1:
                try:
                    os.makedirs(os.path.dirname(cdst.file), exist_ok=True)
                except OSError as exc:
                    raise FSBadParentError(cdst) from exc

                try:
                    shutil.move(csrc.file, cdst.file)
                except shutil.Error as exc:
                    if exc.args and isinstance(exc.args[0], list):
                        raise FSPartialError(cdst) from exc
                    raise

            else:
                # Moving a file into a zip is actually copying-deleting, and
                # is eror-prone as not all metadata can be preserved.
                # Especially that copying a symlink/junction causes the
                # referenced file/directory rather than the entity itself be
                # copied.  Forbid such operation to prevent a misuse and
                # confusion.
                raise FSMoveAcrossZipError(cdst)

        else:
            if len(cdst) == 1:
                # Moving a file from zip to disk is actually copying-deleting,
                # and is eror-prone as not all metadata can be preserved.
                # Especially that entries in a ZIP could have invalid or
                # duplicated filename and can hardly be mirrored to the disk.
                raise FSMoveAcrossZipError(cdst)

            else:
                with open_archive_path(csrc) as zh, \
                     open_archive_path(cdst, 'a') as zh2:
                    copied = zip_copy(zh, csrc[-1], zh2, cdst[-1])

                with open_archive_path(csrc, 'a') as zh:
                    # go through infolist as zinfo may have same name
                    zinfos = {i for i in zh.infolist() if i.filename in copied}
                    _zip_remove_members(zh, zinfos)

    except FSError:
        raise
    except Exception as exc:
        raise _map_exc(exc, cdst) from exc


def copy(csrc, cdst):
    """Copy the source to the target."""
    csrc = CPath(csrc)
    cdst = CPath(cdst)
    try:
        cdst, zstsrc, zstdst = _check_move_copy(csrc, cdst)

        if len(csrc) == 1:
            if len(cdst) == 1:
                try:
                    os.makedirs(os.path.dirname(cdst.file), exist_ok=True)
                except OSError as exc:
                    raise FSBadParentError(cdst) from exc

                try:
                    shutil.copytree(csrc.file, cdst.file)
                except NotADirectoryError:
                    shutil.copy2(csrc.file, cdst.file)
                except shutil.Error as exc:
                    if exc.args and isinstance(exc.args[0], list):
                        raise FSPartialError(cdst) from exc
                    raise

            else:
                _exc = None
                with open_archive_path(cdst, 'a') as zh:
                    try:
                        zip_compress(zh, csrc.file, cdst[-1])
                    except shutil.Error as exc:
                        # don't raise here so that zh writeback not interrupted
                        _exc = exc
                if _exc:
                    exc = _exc
                    if exc.args and isinstance(exc.args[0], list):
                        raise FSPartialError(cdst) from exc
                    raise exc

        else:
            if len(cdst) == 1:
                try:
                    os.makedirs(os.path.dirname(cdst.file), exist_ok=True)
                except OSError as exc:
                    raise FSBadParentError(cdst) from exc

                with open_archive_path(csrc) as zh:
                    zip_extract(zh, cdst.file, csrc[-1])

            else:
                with open_archive_path(csrc) as zh, \
                     open_archive_path(cdst, 'a') as zh2:
                    zip_copy(zh, csrc[-1], zh2, cdst[-1])

    except FSError:
        raise
    except Exception as exc:
        raise _map_exc(exc, cdst) from exc


@contextmanager
def open_archive_path(cpath, mode='r', *, buffer_size=None):
    """Open the innermost zip handler for reading or writing.

    In-memory buffers will be generated for nested ZIPs (len(cpath) > 2),

    e.g. reading from ['/path/to/foo.zip', 'subdir/file.txt']:

        with open_archive_path(cpath) as zh:
            with zh.open(cpath[-1]) as fh:
                print(fh.read())

    e.g. writing to ['/path/to/foo.zip', 'subdir/file.txt']:

        with open_archive_path(cpath, 'a') as zh:
            zh.writestr(cpath[-1], 'foo')

    e.g. deleting ['/path/to/foo.zip', 'subdir/']:

        with open_archive_path(cpath, 'a') as zh:
            zip_remove(zh, cpath[-1])

    Args:
        cpath
        mode: 'r' for reading, 'a' for modifying
        buffer_size: the buffer size for the reading stream when generating an
            internal buffer
    """
    cpath = CPath(cpath)

    last = len(cpath) - 1
    if last < 1:
        raise ValueError('length of paths must > 1')

    stack = []
    if mode == 'r':
        try:
            zh = zipfile.ZipFile(cpath[0])
            stack.append(zh)

            for i in range(1, last):
                fh = zh.open(cpath[i])
                stack.append(fh)
                zh = zipfile.ZipFile(fh)
                stack.append(zh)

            yield zh
        finally:
            for fh in reversed(stack):
                fh.close()

    elif mode == 'a':
        try:
            zh = zipfile.ZipFile(cpath[0], mode)
            stack.append(zh)

            for i in range(1, last):
                # make writable by copying bytes to a buffer
                fh = io.BytesIO()
                with zh.open(cpath[i]) as fr:
                    shutil.copyfileobj(fr, fh, buffer_size)
                stack.append(fh)
                zh = zipfile.ZipFile(fh, mode)
                stack.append(zh)

            yield zh

            fh = None
            for i in reversed(range(last)):
                zh = stack.pop()
                if fh:
                    zinfo = zh.getinfo(cpath[i + 1])
                    zip_remove(zh, zinfo)
                    zinfo.date_time = time.localtime()
                    zinfo.compress_type = zipfile.ZIP_STORED
                    with zh.open(zinfo, 'w') as fw:
                        fh.seek(0)
                        shutil.copyfileobj(fh, fw, buffer_size)
                    fh.close()
                zh.close()
                if i:
                    fh = stack.pop()
        finally:
            for fh in reversed(stack):
                fh.close()

    else:
        raise ValueError(f'Unsupported mode: {mode}')


#########################################################################
# Filesystem handling
#########################################################################

def isjunction(path):
    """Test whether a path is a junction

    - os.path.isjunction is built-in since Python 3.12
    - stat.st_reparse_tag is supported since Python 3.8
    """
    try:
        st = os.lstat(path)
    except (OSError, ValueError, AttributeError):
        return False

    try:
        # True for symlink or directory junction
        assert st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    except (AttributeError, AssertionError):
        return False

    return not stat.S_ISLNK(st.st_mode)


def junction(src, dst):
    """Create a directory junction. (Windows only)
    """
    subprocess.run(
        ['mklink', '/j', dst, src],
        shell=True, capture_output=True, check=True,
    )


#########################################################################
# ZIP handling
#########################################################################

def zip_compression_params(mimetype=None, compress_type=None, compresslevel=None, autodetector=util.is_compressible):
    """A helper for determining compress type and level.
    """
    if compress_type is None and compresslevel is None and autodetector is not None:
        compressible = autodetector(mimetype)
        compress_type = zipfile.ZIP_DEFLATED if compressible else zipfile.ZIP_STORED
        compresslevel = 9 if compressible else None

    return {
        'compress_type': compress_type,
        'compresslevel': compresslevel,
    }


def zip_timestamp(zinfo_or_tuple):
    """Get a compatible timestamp from a ZipInfo.

    Args:
        zinfo_or_tuple: ZipInfo or a tuple as ZipInfo.date_time

    Returns:
        float: timestamp compatible with os.stat_result.st_mtime
    """
    if isinstance(zinfo_or_tuple, zipfile.ZipInfo):
        tuple_ = zinfo_or_tuple.date_time
    else:
        tuple_ = zinfo_or_tuple

    return time.mktime(tuple_ + (0, 0, -1))


def zip_mode(zinfo_or_attr):
    """Get a compatible mode from a ZipInfo.

    Args:
        zinfo_or_attr: ZipInfo or ZipInfo.external_attr

    Returns:
        int: mode compatible with os.stat_result.st_mode
    """
    if isinstance(zinfo_or_attr, zipfile.ZipInfo):
        value = zinfo_or_attr.external_attr
    else:
        value = zinfo_or_attr

    return value >> 16


def zip_check_subpath(zip, subpath, allow_invalid=False):
    """Check what is at the subpath in the ZIP.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        subpath: the subpath in the ZIP, with or without trailing slash
    """
    base = subpath.rstrip('/')

    # treat root as directory
    if base == '':
        return ZIP_SUBPATH_DIR_ROOT

    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
        # check if an ancestor is a file
        if not allow_invalid:
            parts = base.split('/')
            for i in range(len(parts) - 1):
                chk = '/'.join(parts[:i + 1])
                try:
                    zh.getinfo(chk)
                except KeyError:
                    pass
                else:
                    return ZIP_SUBPATH_INVALID

        # check file
        try:
            zh.getinfo(base)
        except KeyError:
            pass
        else:
            return ZIP_SUBPATH_FILE

        # check explicit directory
        base += '/'
        try:
            zh.getinfo(base)
        except KeyError:
            pass
        else:
            return ZIP_SUBPATH_DIR

        # check descendants for an implicit directory
        for path in zh.namelist():
            if path.startswith(base):
                return ZIP_SUBPATH_DIR_IMPLICIT

    return ZIP_SUBPATH_NONE


def zip_compress(zip, filename, subpath, filter=None, *,
                 stream=None, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """Compress src to be the subpath in the zip.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        filename: path of the source file or directory
        subpath: internal path to a file or folder (without trailing slash)
        filter: an iterable of permitted subentries if filename is a directory
            (with normcase'd absolute path)
        stream: a ZipStream for streaming output

    Raises:
        shutil.Error: if any child file cannot be added to the zip
    """
    filename = os.path.abspath(filename)

    if isinstance(zip, zipfile.ZipFile):
        cm = nullcontext(zip)
    else:
        cm = zipfile.ZipFile(zip, 'w')

    gen = _zip_compress_gen(cm, filename, subpath, filter,
                            stream=stream, buffer_size=buffer_size)

    if stream is not None:
        return gen

    for _ in gen:
        pass


def _zip_compress_gen(zh, filename, subpath, filter, *,
                      stream=None, buffer_size=io.DEFAULT_BUFFER_SIZE):
    with zh as zh:
        errors = []

        for src, dst in _zip_compress_iter(filename, subpath, filter):
            try:
                zinfo = zipfile.ZipInfo.from_file(src, dst)
                if zinfo.is_dir():
                    zh.writestr(zinfo, b'')
                    if stream:
                        yield stream.get()
                else:
                    if not stream:
                        comp = zip_compression_params(mimetypes.guess_type(dst)[0])
                        zinfo.compress_type = comp['compress_type']
                        zinfo._compresslevel = comp['compresslevel']
                    with open(src, 'rb') as ih, zh.open(zinfo, 'w') as oh:
                        for chunk in iter(functools.partial(ih.read, buffer_size), b''):
                            oh.write(chunk)
                            if stream:
                                yield stream.get()
            except OSError as why:
                errors.append((src, dst, why))

        if errors:
            raise shutil.Error(errors)

    if stream:
        yield stream.get()


def _zip_compress_iter(filename, subpath, filter=None):
    if os.path.isfile(filename):
        if not subpath:
            raise ValueError("Unable to add a file at ''")

        yield filename, subpath
        return

    if subpath:
        yield filename, subpath

    subpath = subpath + '/' if subpath else ''
    cut = len(os.path.join(filename, ''))
    filter = {os.path.normcase(os.path.join(filename, f)) for f in (filter or ())}
    filter_d = {os.path.join(f, '') for f in filter}

    for root, dirs, files in os.walk(filename, followlinks=True):
        for entry in itertools.chain(dirs, files):
            src = os.path.join(root, entry)

            # apply the filter
            if filter:
                src_nc = os.path.normcase(src)
                if src_nc not in filter:
                    if not any(src_nc.startswith(f) for f in filter_d):
                        continue

            # determine target subpath as dst
            dst = util.unify_pathsep(src[cut:])
            dst = subpath + dst

            yield src, dst


def zip_copy(zsrc, base, zdst, subpath, filter=None, *,
             stream=None, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """Coopy entries from zsrc to be the subpath in zdst.

    Args:
        zsrc: path, file-like object, or zipfile.ZipFile
        base: internal path to a file or folder (without trailing slash)
        zdst: path, file-like object, or zipfile.ZipFile
        subpath: internal path to a file or folder (without trailing slash)
        filter: an iterable of permitted subentries if zsrcpath is a directory
            (without trailing slash)
        stream: a ZipStream for streaming output

    Returns:
        set: names that are copied
    """
    base = base.rstrip('/')

    if isinstance(zdst, zipfile.ZipFile):
        cm = nullcontext(zdst)
    else:
        cm = zipfile.ZipFile(zdst, 'w')

    gen = _zip_copy_gen(zsrc, base, cm, subpath, filter,
                        stream=stream, buffer_size=buffer_size)

    if stream is not None:
        return gen

    try:
        while True:
            next(gen)
    except StopIteration as exc:
        return exc.value


def _zip_copy_gen(zsrc, base, zdst, subpath, filter=None, *,
                  stream=None, buffer_size=io.DEFAULT_BUFFER_SIZE):
    copied = set()
    with nullcontext(zsrc) if isinstance(zsrc, zipfile.ZipFile) else zipfile.ZipFile(zsrc) as zi, \
         zdst as zh:
        for zinfo, dst in _zip_copy_iter(zi, base, subpath, filter):
            copied.add(zinfo.filename)
            zinfo2 = _copy.copy(zinfo)
            zinfo2.filename = dst
            if zinfo.is_dir():
                zh.writestr(zinfo2, b'')
                if stream:
                    yield stream.get()
            else:
                if stream:
                    zinfo2.compress_type = zipfile.ZIP_STORED
                with zi.open(zinfo) as ih, zh.open(zinfo2, 'w') as oh:
                    for chunk in iter(functools.partial(ih.read, buffer_size), b''):
                        oh.write(chunk)
                        if stream:
                            yield stream.get()

    if stream:
        yield stream.get()

    return copied


def _zip_copy_iter(zh, base, subpath, filter=None):
    if base:
        try:
            zinfo = zh.getinfo(base)
        except KeyError:
            pass
        else:
            if not subpath:
                raise ValueError("Unable to add a file at ''")

            yield zinfo, subpath
            return

    base = base + '/' if base else ''
    subpath = subpath + '/' if subpath else ''
    cut = len(base)
    filter = {base + f for f in (filter or ())}
    filter_d = {f + '/' for f in filter}

    for zinfo in zh.infolist():
        src = zinfo.filename
        if not src.startswith(base):
            continue

        # apply the filter
        if filter:
            if src not in filter:
                if not any(src.startswith(f) for f in filter_d):
                    continue

        # determine target subpath as dst
        dst = subpath + src[cut:]
        if dst:
            yield zinfo, dst


def zip_extract(zip, dst, subpath='', tzoffset=None):
    """Extract zip subpath to dst and preserve metadata.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        dst: path where the extracted file or directory will be placed at.
        subpath: internal path to a file or folder (without trailing slash), or
            '' or None to extract the whole zip
        tzoffset: known timezone offset (in seconds) the ZIP file has been
            created at, to adjust mtime of the internal files, which are
            recorded using local timestamp

    Raises:
        FileExistsError: if dst already exists
    """
    if os.path.lexists(dst):
        # trigger FileExistsError
        os.mkdir(dst)

    tempdir = tempfile.mkdtemp()
    try:
        with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
            if not subpath:
                entries = zh.namelist()
            else:
                try:
                    zh.getinfo(subpath)
                except KeyError:
                    entries = [e for e in zh.namelist() if e.startswith(subpath + '/')]
                else:
                    entries = [subpath]

            # extract entries and recover mtime
            zh.extractall(tempdir, entries)
            for entry in entries:
                file = os.path.join(tempdir, entry)
                zinfo = zh.getinfo(entry)

                # @FIXME: utcoffset may be different across timestamps when DST
                #         is used
                ts = zip_timestamp(zinfo)
                if tzoffset is not None:
                    utcoffset = datetime.fromtimestamp(ts).astimezone().utcoffset().total_seconds()
                    ts = ts + utcoffset - tzoffset
                os.utime(file, (ts, ts))

                # @TODO: recover mode?
                # It may be ignored in some OS and setting the mode for a file
                # can prevent another file from being set.

        # move to target path
        if not subpath:
            shutil.move(tempdir, dst)
        else:
            shutil.move(os.path.join(tempdir, subpath), dst)
    finally:
        try:
            shutil.rmtree(tempdir)
        except OSError:
            pass


def zip_remove(zip, zinfo_or_arcname):
    """Remove a member from the archive.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
    """
    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip, 'a') as self:
        if self.mode != 'a':
            raise ValueError("remove() requires mode 'a'")
        if not self.fp:
            raise ValueError(
                'Attempt to write to ZIP archive that was already closed')
        if self._writing:
            raise ValueError(
                "Can't write to ZIP archive while an open writing handle exists"
            )

        # Make sure we have an existing info object
        if isinstance(zinfo_or_arcname, zipfile.ZipInfo):
            zinfo = zinfo_or_arcname
            # make sure zinfo exists
            if zinfo not in self.filelist:
                raise KeyError(
                    'There is no item %r in the archive' % zinfo.filename)
        else:
            # get the info object
            zinfo = self.getinfo(zinfo_or_arcname)

        return _zip_remove_members(self, (zinfo,))


def _zip_remove_members(zip, members, *, remove_physical=True, buffer_size=2**20):
    """Remove members in a zip file.

    All members (as zinfo) should exist in the zip; otherwise the zip file
    will erroneously end in an inconsistent state.
    """
    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip, 'a') as self:
        with self._lock:
            fp = self.fp
            entry_offset = 0
            member_seen = False

            # get a sorted filelist by header offset, in case the dir order
            # doesn't match the actual entry order
            filelist = sorted(self.filelist, key=lambda x: x.header_offset)
            for i in range(len(filelist)):
                info = filelist[i]
                is_member = info in members

                if not (member_seen or is_member):
                    continue

                # get the total size of the entry
                try:
                    offset = filelist[i + 1].header_offset
                except IndexError:
                    offset = self.start_dir
                entry_size = offset - info.header_offset

                if is_member:
                    member_seen = True
                    entry_offset += entry_size

                    # update caches
                    self.filelist.remove(info)
                    try:
                        del self.NameToInfo[info.filename]
                    except KeyError:
                        pass
                    continue

                # update the header and move entry data to the new position
                if remove_physical:
                    old_header_offset = info.header_offset
                    info.header_offset -= entry_offset
                    read_size = 0
                    while read_size < entry_size:
                        fp.seek(old_header_offset + read_size)
                        data = fp.read(min(entry_size - read_size, buffer_size))
                        fp.seek(info.header_offset + read_size)
                        fp.write(data)
                        fp.flush()
                        read_size += len(data)

            # Avoid missing entry if entries have a duplicated name.
            # Reverse the order as NameToInfo normally stores the last added one.
            for info in reversed(self.filelist):
                self.NameToInfo.setdefault(info.filename, info)

            # update state
            if remove_physical:
                self.start_dir -= entry_offset
            self._didModify = True

            # seek to the start of the central dir
            fp.seek(self.start_dir)


class ZipStream(io.RawIOBase):
    """A class for a streaming ZIP output."""
    def __init__(self):
        self._buffer = b''
        self._size = 0

    def writable(self):
        return True

    def write(self, b):
        if self.closed:
            raise RuntimeError('ZipStream has been closed')
        self._buffer += b
        return len(b)

    def get(self):
        chunk = self._buffer
        self._buffer = b''
        self._size += len(chunk)
        return chunk

    def size(self):
        return self._size
