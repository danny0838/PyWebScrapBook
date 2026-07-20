import time

from zipremove import *
from zipremove import __all__

from ..util import util
from . import mimetypes

# subclasses with modified or extended features
_ZipInfo = ZipInfo
_ZipFile = ZipFile


def autocompressor_deflate_compressible(archive, zinfo):
    mimetype = mimetypes.guess_type(zinfo.filename)[0]
    compressible = util.is_compressible(mimetype)
    if compressible:
        return ZIP_DEFLATED, 9 if (lv := archive.compresslevel) is None else lv
    else:
        return ZIP_STORED, None


class ZipInfoExt(_ZipInfo):
    __slots__ = ()

    def __init__(self, filename="NoName", date_time=None, *, mode=0o775):
        """Provide suitable default attributes.

        Works mostly like native ZipInfo._for_archive(), but with more
        parameters.
        """
        super().__init__(filename)

        self._set_datetime(date_time)

        if self.is_dir():
            self.external_attr = (0o40000 | (mode & 0o7777)) << 16  # Unix attributes
            self.external_attr |= 0x10  # MS-DOS directory flag
        else:
            self.external_attr = 0o600 << 16  # ?rw-------

    @classmethod
    def _transform(cls, zinfo):
        """Transform native ZipInfo into ZipInfoExt in-place."""
        zinfo.__class__ = cls
        return zinfo

    def _for_archive(self, *args, **kwargs):
        raise NotImplementedError('This method should not be called.')

    def _set_datetime(self, date_time=None):
        if date_time is None:
            date_time = time.localtime(time.time())[:6]

        if date_time[0] < 1980:
            date_time = (1980, 1, 1, 0, 0, 0)
        elif date_time[0] > 2107:
            date_time = (2107, 12, 31, 23, 59, 58)

        self.date_time = date_time

        return self


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


# map general ZipFile and ZipInfo to be the extended classes
ZipInfo = ZipInfoExt
ZipFile = ZipFileExt
