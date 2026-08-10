import os
import struct
import sys
import time
from datetime import datetime

from zipremove import *
from zipremove import __all__

from ..util import util
from . import mimetypes

try:
    from zipfile import _Extra
    _Extra.iter
except (ImportError, AttributeError):
    # polyfill for revised _Extra
    # ref: https://github.com/python/cpython/pull/152141
    class _Extra:
        FIELD_STRUCT = struct.Struct('<HH')

        @classmethod
        def iter(cls, data, validate=False):
            """Iter through and yield each (field, id)."""
            # early return for empty extra data
            if not data:
                return

            pos, data_len = 0, len(data)
            while pos < data_len:
                try:
                    xid, xlen = cls.FIELD_STRUCT.unpack_from(data, pos)
                except struct.error:
                    xid, xlen = None, 0
                else:
                    if validate and pos + 4 + xlen > data_len:
                        raise BadZipFile(
                            "Corrupt extra field %04x (size=%d)" % (xid, xlen))
                yield data[pos:pos + 4 + xlen], xid
                pos += 4 + xlen

        @classmethod
        def strip(cls, data, xids):
            """Remove Extra fields with specified IDs."""
            return b''.join(
                ex
                for ex, xid in cls.iter(data)
                if xid not in xids
            )

        @classmethod
        def update(cls, data, extra):
            """Insert fields from extra and strip duplicates."""
            # early return for empty data
            if not data:
                return extra

            extras = {
                xid: ex
                for ex, xid in cls.iter(extra)
                if xid is not None
            }
            # New fields first since data may have a corrupted tail that renders
            # following fields inaccessible.  (The caller is responsible for making
            # sure that extra is valid.)
            return b''.join(extras.values()) + cls.strip(data, extras)


# subclasses with modified or extended features
_ZipInfo = ZipInfo
_ZipFile = ZipFile

# Windows ticks (100 ns each) from Windows epoch (1601-01-01T00:00:00Z) to
# Unix epoch (1970-01-01T00:00:00Z)
WIN_TICKS_FROM_EPOCH = 116444736_000_000_000


def autocompressor_deflate_compressible(archive, zinfo):
    mimetype = mimetypes.guess_type(zinfo.filename)[0]
    compressible = util.is_compressible(mimetype)
    if compressible:
        return ZIP_DEFLATED, 9 if (lv := archive.compresslevel) is None else lv
    else:
        return ZIP_STORED, None


class ZipExtractorBase:
    debug = 0
    allowed_mode = 0o7777

    def __init__(self, archive, path=None, pwd=None):
        self.archive = archive
        if path is None:
            self.target_path = os.getcwd()
        else:
            self.target_path = os.fspath(path)
        self.pwd = pwd
        self._dirs = {}

    def _debug(self, level, *msg, file=sys.stderr):
        if level <= self.debug:
            print(*msg, file=file)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.finalize(exc_type, exc_value, traceback)

    def __call__(self, zinfo):
        targetpath = self.archive._extract_member(zinfo, self.target_path, self.pwd)

        # Delay restoring attributes for directories since permissions
        # can interfere with extraction and extracting contents can
        # reset mtime.
        if zinfo.is_dir():
            self._dirs[zinfo] = targetpath
        else:
            self.restore_attributes(targetpath, zinfo)

        return targetpath

    def finalize(self, exc_type=None, exc_value=None, traceback=None):
        # restore attributes for directories from bottom to top
        items = sorted(self._dirs.items(), key=lambda i: i[0].filename, reverse=True)
        for zinfo, targetpath in items:
            # skip if directory missing
            if not os.path.isdir(targetpath):
                continue

            self.restore_attributes(targetpath, zinfo)

    def restore_attributes(self, targetpath, zinfo):
        pass

    def utime(self, targetpath, zinfo):
        dt = zinfo._get_datetime()
        os.utime(targetpath, ns=dt)

    def chmod(self, targetpath, zinfo):
        mode = (zinfo.external_attr >> 16) & self.allowed_mode
        mode = os.stat(targetpath).st_mode & ~self.allowed_mode | mode
        os.chmod(targetpath, mode)


class ZipExtractor(ZipExtractorBase):
    allowed_mode = 0o777

    def restore_attributes(self, targetpath, zinfo):
        try:
            self.utime(targetpath, zinfo)
            self.chmod(targetpath, zinfo)
        except OSError as exc:
            self._debug(1, f'zipfile: {exc}')


class ZipInfoExt(_ZipInfo):
    __slots__ = ()

    def __init__(self, filename="NoName", date_time=None, *, mode=0o777,
                 dmask=0o002, fmask=0o177):
        """Provide suitable default attributes.

        Works mostly like native ZipInfo._for_archive(), but with more
        parameters.
        """
        super().__init__(filename)

        self._set_datetime(date_time)

        if self.is_dir():
            self.external_attr = (0o40000 | (mode & 0o7777 & ~dmask)) << 16  # Unix attributes
            self.external_attr |= 0x10  # MS-DOS directory flag
        else:
            self.external_attr = (0o100000 | (mode & 0o7777 & ~fmask)) << 16

    @classmethod
    def _transform(cls, zinfo):
        """Transform native ZipInfo into ZipInfoExt in-place."""
        zinfo.__class__ = cls
        return zinfo

    @classmethod
    def from_file(cls, filename, *args, strict_timestamps=False, **kwargs):
        zinfo = super().from_file(filename, *args, strict_timestamps=False, **kwargs)
        if isinstance(filename, os.PathLike):
            filename = os.fspath(filename)
        return zinfo._set_datetime(os.stat(filename))

    def _for_archive(self, *args, **kwargs):
        raise NotImplementedError('This method should not be called.')

    def _get_datetime(self):
        # Well-known extra fields:
        # ref: https://libzip.org/specifications/extrafld.txt
        prio_list = (0x000a, 0x5455, 0x5855, 0x000d)

        prio, atime, mtime = None, None, None
        for extra, tp in _Extra.iter(self.extra, True):
            # skip a field with undefined or lower priority
            try:
                new_prio = prio_list.index(tp)
                assert prio is None or new_prio <= prio
            except (ValueError, AssertionError):
                continue

            pos = 4
            if tp == 0x000a:
                # NTFS Extra Field (0x000a)
                ntfs_fmt = '<LHH'
                ntfs_fmt_size = struct.calcsize(ntfs_fmt)
                while True:
                    try:
                        _, ntfs_id, ntfs_len = struct.unpack_from(ntfs_fmt, extra, pos)
                    except struct.error:
                        break

                    pos += ntfs_fmt_size

                    if ntfs_id == 0x0001:
                        try:
                            ft_mtime, ft_atime, ft_ctime = struct.unpack_from('<QQQ', extra, pos)
                        except struct.error:
                            break

                        prio, atime, mtime = (
                            new_prio,
                            (ft_atime - WIN_TICKS_FROM_EPOCH) * 100,
                            (ft_mtime - WIN_TICKS_FROM_EPOCH) * 100,
                        )

                    pos += ntfs_len

            elif tp == 0x5455:
                # Extended timestamp (0x5455)
                try:
                    ut_bits, ut_mtime = struct.unpack_from('<Bl', extra, pos)
                    assert ut_bits & 0x01
                except (struct.error, AssertionError):
                    pass
                else:
                    ut = ut_mtime * 10 ** 9
                    prio, atime, mtime = (new_prio, ut, ut)

            elif tp == 0x5855:
                # Unix1 (0x5855)
                try:
                    ux_atime, ux_mtime = struct.unpack_from('<ll', extra, pos)
                except struct.error:
                    pass
                else:
                    prio, atime, mtime = (new_prio, ux_atime * 10 ** 9, ux_mtime * 10 ** 9)

            elif tp == 0x000d:
                # Unix0 (0x000d)
                try:
                    ux_atime, ux_mtime = struct.unpack_from('<ll', extra, pos)
                except struct.error:
                    pass
                else:
                    prio, atime, mtime = (new_prio, ux_atime * 10 ** 9, ux_mtime * 10 ** 9)

        if prio is not None:
            return atime, mtime

        lt = int(time.mktime(self.date_time + (0, 0, -1))) * 10 ** 9
        return lt, lt

    def _set_datetime(self, dt=None):
        mtime = atime = ctime = None

        if dt is None:
            # take current time
            mtime = time.time_ns()
        elif isinstance(dt, float):
            # time.time()
            mtime = int(dt * 10 ** 9)
        elif isinstance(dt, int):
            # time.time_ns()
            mtime = dt
        elif isinstance(dt, os.stat_result):
            # os.stat_result is a subclass of tuple
            mtime = dt.st_mtime_ns
            atime = dt.st_atime_ns
            ctime = dt.st_ctime_ns
        elif isinstance(dt, tuple):
            # native zipfile date_time tuple
            # allow an additional microseconds as the 7th element
            mtime = int(datetime(*dt[:7]).timestamp() * 10 ** 9)

        if atime is None:
            atime = mtime
        if ctime is None:
            ctime = mtime

        extras = {tp: extra for extra, tp in _Extra.iter(self.extra)}

        # Extended timestamp (UT) (0x5455)
        # Prefer this as supported by most tools like Info-ZIP, 7Zip, and Windows native tar.
        ut_mtime = mtime // 10 ** 9
        try:
            extras[0x5455] = struct.pack('<HHBl', 0x5455, 5, 0x01, ut_mtime)
        except (struct.error, ValueError):
            # unable to pack due to overflow/underflow
            # some platform (such as PyPy) may raise ValueError instead
            extras.pop(0x5455, None)

        # NTFS Extra Field (0x000a)
        # Supported by 7Zip but not by Info-ZIP and Windows native tar, explorer, and powershell.
        # Use this only when UT is unavailable or it's already used.
        if 0x000a in extras or 0x5455 not in extras:
            ft_mtime = mtime // 100 + WIN_TICKS_FROM_EPOCH
            ft_atime = atime // 100 + WIN_TICKS_FROM_EPOCH
            ft_ctime = ctime // 100 + WIN_TICKS_FROM_EPOCH
            try:
                ntfs_tag = struct.pack('<LHHQQQ', 0, 0x0001, 24, ft_mtime, ft_atime, ft_ctime)
            except (struct.error, ValueError):
                # unable to pack due to overflow/underflow
                # some platform (such as PyPy) may raise ValueError instead
                extras.pop(0x000a, None)
            else:
                extras[0x000a] = struct.pack('<HH', 0x000a, len(ntfs_tag)) + ntfs_tag
        else:
            extras.pop(0x000a, None)

        # Unix1 (0x5855)
        # Legacy. Clear it since the central version contains only atime and mtime.
        extras.pop(0x5855, None)

        # Unix0 (0x000d)
        # Legacy. Update atime/mtime since it may contain UID, GID, and other info.
        if 0x000d in extras:
            try:
                _, ux_len, ux_atime, ux_mtime, ux_uid, ux_gid = struct.unpack_from('<HHllHH', extras[0x000d])
                ux_var = extras[0x000d][16:]
                ux_mtime = mtime // 10 ** 9
                ux_atime = atime // 10 ** 9
                extras[0x000d] = struct.pack(f'<HHllHH{ux_len - 12}s', 0x000d,
                                             ux_len, ux_atime, ux_mtime, ux_uid, ux_gid, ux_var)
            except (struct.error, ValueError):
                # unable to pack due to overflow/underflow
                # some platform (such as PyPy) may raise ValueError instead
                extras.pop(0x000d, None)

        # @TODO: update or clear other subfields containing datetime information

        # move invalid tail to the end if exists
        try:
            extras[None] = extras.pop(None)
        except KeyError:
            pass

        self.extra = b''.join(extras.values())

        # date_time
        ts = mtime // 10 ** 9
        try:
            date_time = time.localtime(ts)[:6]
        except (OSError, OverflowError, ValueError):
            if ts < 0:
                date_time = (1980, 1, 1, 0, 0, 0)
            else:
                date_time = (2107, 12, 31, 23, 59, 58)
        else:
            if date_time[0] < 1980:
                date_time = (1980, 1, 1, 0, 0, 0)
            elif date_time[0] > 2107:
                date_time = (2107, 12, 31, 23, 59, 58)
        self.date_time = date_time

        return self

    def _get_mode(self):
        """Get a compatible mode.

        Returns:
            int: mode compatible with os.stat_result.st_mode
        """
        return self.external_attr >> 16


class ZipFileExt(_ZipFile):
    """Extended ZipFile.

    Should pass ZipInfoExt instead of native ZipInfo to methods.
    """
    _ZipInfo = ZipInfoExt
    _autocompressor = autocompressor_deflate_compressible

    def __init__(self, file, mode='r', compression=None, *args, **kwargs):
        """Extended method to allow compression=None for auto-detection."""
        # tweak passed value to bypass the check of native zipfile._check_compression()
        _compression = ZIP_STORED if compression is None else compression
        super().__init__(file, mode, _compression, *args, **kwargs)
        if compression is None:
            self.compression = None

    @property
    def _strict_timestamps(self):
        return False

    @_strict_timestamps.setter
    def _strict_timestamps(self, value):
        pass

    @_strict_timestamps.deleter
    def _strict_timestamps(self):
        pass

    def _RealGetContents(self):  # noqa: N802
        super()._RealGetContents()

        # Transform native ZipInfo into ZipInfoExt in-place.
        for zinfo in self.filelist:
            self._ZipInfo._transform(zinfo)

    def open(self, member, mode='r', *args, **kwargs):
        if isinstance(member, self._ZipInfo):
            zinfo = member
        elif mode == 'w':
            zinfo = self._ZipInfo(member)
        else:
            zinfo = self.getinfo(member)
        return super().open(zinfo, mode, *args, **kwargs)

    def writestr(self, member, *args, **kwargs):
        if isinstance(member, self._ZipInfo):
            zinfo = member
        else:
            zinfo = self._ZipInfo(member)
        return super().writestr(zinfo, *args, **kwargs)

    def write(self, *args, **kwargs):
        raise NotImplementedError('This method should not be called.')

    def mkdir(self, member, mode=0o777):
        if isinstance(member, self._ZipInfo):
            zinfo = member
            if not zinfo.is_dir():
                raise ValueError('The given ZipInfo does not describe a directory')
        elif isinstance(member, str):
            directory_name = member
            if not directory_name.endswith("/"):
                directory_name += "/"
            zinfo = self._ZipInfo(directory_name, mode=mode)
        else:
            raise TypeError("Expected type str or ZipInfo")

        # Fix bug gh-154174
        # https://github.com/python/cpython/issues/154174
        zinfo.CRC = zinfo.compress_size = zinfo.file_size = 0

        try:
            super().mkdir(zinfo)
        except AttributeError:
            # fallback for Python < 3.11
            super().writestr(zinfo, b'')

    def _set_compression(self, zinfo):
        """Assign proper compression type and level to zinfo."""
        if zinfo.is_dir():
            comp_tuple = ZIP_STORED, None
        elif self.compression is None:
            comp_tuple = self._autocompressor(zinfo)
        else:
            comp_tuple = self.compression, self.compresslevel

        # use _compresslevel for downward compatibility with Python < 3.13
        zinfo.compress_type, zinfo._compresslevel = comp_tuple

    def extract(self, member, path=None, pwd=None, *, extractor=ZipExtractor):
        zinfo = member if isinstance(member, self._ZipInfo) else self.getinfo(member)
        with extractor(self, path, pwd=pwd) as extr:
            return extr(zinfo)

    def extractall(self, path=None, members=None, pwd=None, *, extractor=ZipExtractor):
        if members is None:
            members = self.namelist()

        zinfos = [m if isinstance(m, self._ZipInfo) else self.getinfo(m) for m in members]
        with extractor(self, path, pwd=pwd) as extr:
            for zinfo in zinfos:
                extr(zinfo)


# map general ZipFile and ZipInfo to be the extended classes
ZipInfo = ZipInfoExt
ZipFile = ZipFileExt
