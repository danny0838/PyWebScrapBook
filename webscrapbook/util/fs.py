"""Virtual filesystem for complex file operation."""
import functools
import io
import mimetypes
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import namedtuple
from contextlib import contextmanager, nullcontext
from datetime import datetime

from . import util


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
        return CPath(self._path)

    @property
    def path(self):
        return self._path

    @property
    def file(self):
        return self._path[0]

    @staticmethod
    def resolve(plainpath, resolver=None):
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
        for m in reversed(list(re.finditer(r'!/', plainpath, flags=re.I))):
            archivepath = plainpath[:m.start(0)]
            if resolver:
                archivepath = CPath._resolve_tidy_subpath(archivepath)
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
                CPath._resolve_add_subpath(paths, zh, plainpath[m.end(0):])
                return CPath(paths)

        archivepath = plainpath
        if resolver:
            archivepath = CPath._resolve_tidy_subpath(archivepath)
        else:
            archivepath = os.path.normpath(archivepath)
        paths.append(archivepath)
        return CPath(paths)

    @staticmethod
    def _resolve_add_subpath(paths, zh, subpath):
        for m in reversed(list(re.finditer(r'!/', subpath, flags=re.I))):
            archivepath = CPath._resolve_tidy_subpath(subpath[:m.start(0)], True)
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
                    CPath._resolve_add_subpath(paths, zh1, subpath[m.end(0):])
                    return

        paths.append(CPath._resolve_tidy_subpath(subpath, True))

    @staticmethod
    def _resolve_tidy_subpath(path, striproot=False):
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


def _open_archive_path_filter(path, filters):
    for filter in filters:
        filter = filter.rstrip('/')
        if path == filter:
            return True
        if path.startswith(filter + ('/' if filter else '')):
            return True
    return False


@contextmanager
def open_archive_path(cpath, mode='r', filters=None):
    """Open the innermost zip handler for reading or writing.

    e.g. reading from ['/path/to/foo.zip', 'subdir/file.txt']:

        with open_archive_path(cpath) as zh:
            with zh.open(cpath[-1]) as fh:
                print(fh.read())

    e.g. writing to ['/path/to/foo.zip', 'subdir/file.txt']:

        with open_archive_path(cpath, 'w') as zh:
            zh.writestr(cpath[-1], 'foo')

    e.g. deleting ['/path/to/foo.zip', 'subdir/']:

        with open_archive_path(cpath, 'w', [cpath[-1]]) as zh:
            pass

    Args:
        cpath
        mode: 'r' for reading, 'w' for modifying
        filters: a list of file or folder to remove
    """
    cpath = CPath(cpath)

    last = len(cpath) - 1
    if last < 1:
        raise ValueError('length of paths must > 1')

    filtered = False
    stack = []
    try:
        zh = zipfile.ZipFile(cpath[0])
        stack.append(zh)
        for i in range(1, last):
            fh = zh.open(cpath[i])
            stack.append(fh)
            zh = zipfile.ZipFile(fh)
            stack.append(zh)

        if mode == 'r':
            yield zh

        elif mode == 'w':
            # create a buffer for writing
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as zh:
                yield zh

            # copy zip file
            for i in reversed(range(1, last + 1)):
                zh0 = stack.pop()
                with zipfile.ZipFile(buffer, 'a') as zh:
                    zh.comment = zh0.comment
                    for info in zh0.infolist():
                        if filters and i == last:
                            if _open_archive_path_filter(info.filename, filters):
                                filtered = True
                                continue

                        try:
                            zh.getinfo(info.filename)
                        except KeyError:
                            pass
                        else:
                            continue

                        zh.writestr(info, zh0.read(info),
                                    compress_type=info.compress_type,
                                    compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9,
                                    )

                if filters and not any(f == '' for f in filters) and not filtered:
                    raise KeyError('paths to filter do not exist')

                if i == 1:
                    break

                # writer to another buffer for the parent zip
                buffer2 = io.BytesIO()
                with zipfile.ZipFile(buffer2, 'w') as zh:
                    zh.writestr(cpath[i - 1], buffer.getvalue(), compress_type=zipfile.ZIP_STORED)
                buffer.close()
                buffer = buffer2

                # pop a file handler
                stack.pop()

            # write to the outermost zip
            # use 'r+b' as 'wb' causes PermissionError for hidden file in Windows
            buffer.seek(0)
            with open(cpath[0], 'r+b') as fw, buffer as fr:
                fw.truncate()
                for chunk in iter(functools.partial(fr.read, 8192), b''):
                    fw.write(chunk)
    finally:
        for fh in reversed(stack):
            fh.close()


#########################################################################
# Filesystem handling
#########################################################################

FileInfo = namedtuple('FileInfo', ('name', 'type', 'size', 'last_modified'))


def file_is_link(path, st=None):
    """Check if a path is a symlink or Windows directory junction

    Args:
        st: known stat for the path for better performance
    """
    if st is None:
        try:
            st = os.lstat(path)
        except (OSError, ValueError, AttributeError):
            return False

    if os.name == 'nt':
        if st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            # this is True for symlink or directory junction
            return True

    return stat.S_ISLNK(st.st_mode)


def file_info(file, base=None):
    """Read basic file information.
    """
    if base is None:
        name = os.path.basename(file)
    else:
        name = file[len(base) + 1:].replace('\\', '/')

    try:
        statinfo = os.lstat(file)
    except OSError:
        # unexpected error when getting stat info
        statinfo = None
        size = None
        last_modified = None
    else:
        size = statinfo.st_size
        last_modified = statinfo.st_mtime

    if not os.path.lexists(file):
        type = None
    elif file_is_link(file, statinfo):
        type = 'link'
    elif os.path.isdir(file):
        type = 'dir'
    elif os.path.isfile(file):
        type = 'file'
    else:
        type = 'unknown'

    if type != 'file':
        size = None

    return FileInfo(name=name, type=type, size=size, last_modified=last_modified)


def listdir(base, recursive=False):
    """Generates FileInfo(s) and omit invalid entries.
    """
    if not recursive:
        with os.scandir(base) as entries:
            for entry in entries:
                info = file_info(entry.path)
                if info.type is None:
                    continue
                yield info

    else:
        for root, dirs, files in os.walk(base):
            for dir in dirs:
                file = os.path.join(root, dir)
                info = file_info(file, base)
                if info.type is None:
                    continue
                yield info
            for file in files:
                file = os.path.join(root, file)
                info = file_info(file, base)
                if info.type is None:
                    continue
                yield info


#########################################################################
# ZIP handling
#########################################################################

class ZipDirNotFoundError(Exception):
    pass


def zip_fix_subpath(subpath):
    """Fix subpath to fit ZIP format specification.
    """
    if os.sep != '/' and os.sep in subpath:
        subpath = subpath.replace(os.sep, '/')
    return subpath


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


def zip_tuple_timestamp(zipinfodate):
    """Get timestamp from a ZipInfo.date_time.
    """
    return time.mktime(zipinfodate + (0, 0, -1))


def zip_timestamp(zipinfo):
    """Get timestamp from a ZipInfo.
    """
    return zip_tuple_timestamp(zipinfo.date_time)


def zip_file_info(zip, subpath, base=None, check_implicit_dir=False):
    """Read basic file information from ZIP.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        subpath: 'dir' and 'dir/' are both supported
    """
    subpath = zip_fix_subpath(subpath)

    subpath = subpath.rstrip('/')
    if base is None:
        name = os.path.basename(subpath)
    else:
        name = subpath[len(base):]

    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
        try:
            info = zh.getinfo(subpath)
        except KeyError:
            pass
        else:
            return FileInfo(name=name, type='file', size=info.file_size, last_modified=zip_timestamp(info))

        try:
            info = zh.getinfo(subpath + '/')
        except KeyError:
            pass
        else:
            return FileInfo(name=name, type='dir', size=None, last_modified=zip_timestamp(info))

        if check_implicit_dir:
            base = subpath + ('/' if subpath else '')
            for entry in zh.namelist():
                if entry.startswith(base):
                    return FileInfo(name=name, type='dir', size=None, last_modified=None)

    return FileInfo(name=name, type=None, size=None, last_modified=None)


def zip_listdir(zip, subpath, recursive=False):
    """Generates FileInfo(s) and omit invalid entries.

    Raise ZipDirNotFoundError if subpath does not exist.

    NOTE: It is possible that entry mydir/ does not exist while mydir/foo.bar
    exists. Check for matching subentries to make sure whether the implicit
    directory exists.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        subpath: the subpath in the ZIP, with or without trailing slash
    """
    subpath = zip_fix_subpath(subpath)

    base = subpath.rstrip('/')
    if base:
        base += '/'
    base_len = len(base)
    dir_exist = not base
    entries = {}

    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
        for filename in zh.namelist():
            if not filename.startswith(base):
                continue

            if filename == base:
                dir_exist = True
                continue

            entry = filename[base_len:]
            if not recursive:
                entry, _, _ = entry.partition('/')
                entries.setdefault(entry, True)
            else:
                parts = entry.rstrip('/').split('/')
                for i in range(0, len(parts)):
                    entry = '/'.join(parts[0:i + 1])
                    entries.setdefault(entry, True)

        if not entries and not dir_exist:
            raise ZipDirNotFoundError(f'Directory "{base}/" does not exist in the zip.')

        for entry in entries:
            info = zip_file_info(zh, base + entry, base)

            if info.type is None:
                yield FileInfo(name=entry, type='dir', size=None, last_modified=None)
            else:
                yield info


def zip_has(zip, subpath, type='any'):
    """Check if a directory or file exists in the ZIP.

    NOTE: It is possible that entry mydir/ does not exist while mydir/foo.bar
    exists. Check for matching subentries to make sure whether the implicit
    directory exists.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        subpath: the subpath in the ZIP, with or without trailing slash
        type: 'dir', 'file', or 'any'
    """
    subpath = zip_fix_subpath(subpath)

    if type not in ('dir', 'file', 'any'):
        raise ValueError(f'Invalid type: "{type}"')

    base = subpath.rstrip('/')
    if base == '':
        return True if type != 'file' else False

    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
        if type in ('file', 'any'):
            try:
                zh.getinfo(base)
            except KeyError:
                pass
            else:
                return True

        base += '/'
        if type in ('dir', 'any'):
            try:
                zh.getinfo(base)
            except KeyError:
                pass
            else:
                return True

            # check for an implicit directory
            for path in zh.namelist():
                if path.startswith(base):
                    return True

    return False


def zip_compress(zip, filename, subpath, filter=None):
    """Compress src to be the subpath in the zip.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        filename: path of the source file or directory
        subpath: internal path to a file or folder (without trailing slash)
        filter: an iterable of permitted subentries if filename is a directory
            (with normcase'd absolute path)

    Raises:
        shutil.Error: if any child file cannot be added to the zip
    """
    subpath = zip_fix_subpath(subpath)

    filename = os.path.abspath(filename)
    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip, 'w') as zh:
        if os.path.isdir(filename):
            errors = []

            subpath = subpath + '/' if subpath else ''
            src = filename
            dst = subpath
            if dst:
                try:
                    ts = time.localtime(os.stat(src).st_mtime)[:-3]
                    zh.writestr(zipfile.ZipInfo(dst, ts), '')
                except OSError as why:
                    errors.append((src, dst, str(why)))

            filter = {os.path.normcase(os.path.join(filename, f)) for f in (filter or [])}
            filter_d = {os.path.join(f, '') for f in filter}

            base_cut = len(os.path.join(filename, ''))
            for root, dirs, files in os.walk(filename, followlinks=True):
                for dir in dirs:
                    src = os.path.join(root, dir)

                    # apply the filter
                    if filter:
                        src_nc = os.path.normcase(src)
                        if src_nc not in filter:
                            if not any(src_nc.startswith(f) for f in filter_d):
                                continue

                    dst = src[base_cut:]
                    if os.sep != '/':
                        dst = dst.replace(os.sep, '/')
                    dst = subpath + dst + '/'
                    try:
                        ts = time.localtime(os.stat(src).st_mtime)[:-3]
                        zh.writestr(zipfile.ZipInfo(dst, ts), '')
                    except OSError as why:
                        errors.append((src, dst, str(why)))

                for file in files:
                    src = os.path.join(root, file)

                    # apply the filter
                    if filter:
                        src_nc = os.path.normcase(src)
                        if src_nc not in filter:
                            if not any(src_nc.startswith(f) for f in filter_d):
                                continue

                    dst = src[base_cut:]
                    if os.sep != '/':
                        dst = dst.replace(os.sep, '/')
                    dst = subpath + dst
                    try:
                        zh.write(src, dst, **zip_compression_params(mimetype=mimetypes.guess_type(dst)[0]))
                    except OSError as why:
                        errors.append((src, dst, str(why)))

            if errors:
                raise shutil.Error(errors)
        else:
            zh.write(filename, subpath, **zip_compression_params(mimetype=mimetypes.guess_type(subpath)[0]))


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
    subpath = zip_fix_subpath(subpath)

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

            # extract entries and keep datetime
            zh.extractall(tempdir, entries)
            for entry in entries:
                file = os.path.join(tempdir, entry)
                ts = zip_timestamp(zh.getinfo(entry))

                if tzoffset is not None:
                    delta = datetime.now().astimezone().utcoffset().total_seconds()
                    ts = ts - tzoffset + delta

                os.utime(file, (ts, ts))

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
