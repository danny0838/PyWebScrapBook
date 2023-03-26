"""Virtual filesystem for complex file operation."""
import functools
import io
import mimetypes
import os
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


def launch(path):
    """Launch a file or open a directory in the explorer.
    """
    if sys.platform == 'win32':
        os.startfile(path)
    elif sys.platform == 'darwin':
        subprocess.run(['open', path])
    else:
        subprocess.run(['xdg-open', path])


def view_in_explorer(path):
    """Open the parent directory of a file or directory in the explorer."""
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
