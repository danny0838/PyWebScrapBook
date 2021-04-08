"""Miscellaneous utilities
"""
import sys
import os
import importlib
import stat
import subprocess
import collections
from collections import namedtuple
import shutil
import zipfile
import tempfile
import math
import re
import hashlib
import time
import mimetypes
import binascii
import codecs
from base64 import b64decode
from urllib.parse import quote, unquote_to_bytes
from urllib.request import pathname2url
from ipaddress import IPv6Address, AddressValueError
from datetime import datetime, timezone
from lxml import etree
import lxml.html
from .html import HTMLParser
from .._compat.contextlib import nullcontext


#########################################################################
# Common classes and objects handling
#########################################################################

# common namedtuple for yielded messages for certain classes
Info = namedtuple('Info', ['type', 'msg', 'data', 'exc'])
Info.__new__.__defaults__ = (None, None)


class frozendict(collections.abc.Mapping):
    """Implementation of a frozen dict, which is hashable if all values
       are hashable.
    """
    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __repr__(self):
        return f'{type(self).__name__}({self._d.__repr__()})'

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __reversed__(self):
        try:
            return reversed(self._d)
        except TypeError:
            # reversed(dict) not supported in Python < 3.8
            # shim via reversing a list
            return reversed(list(self._d))

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(frozenset(self.items()))
        return self._hash

    def copy(self):
        return self.__class__(self._d.copy())


def make_hashable(obj):
    if isinstance(obj, collections.abc.Hashable):
        return obj

    if isinstance(obj, collections.abc.Set):
        return frozenset(make_hashable(v) for v in obj)

    if isinstance(obj, collections.abc.Sequence):
        return tuple(make_hashable(v) for v in obj)

    if isinstance(obj, collections.abc.Mapping):
        return frozendict((k, make_hashable(v)) for k, v in obj.items())

    raise TypeError(f"unable to make '{type(obj).__name__}' hashable")


def import_module_file(ns, file):
    spec = importlib.util.spec_from_file_location(ns, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#########################################################################
# ScrapBook related path/file/string/etc handling
#########################################################################

REGEX_ID_TO_DATETIME = re.compile(r'^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{3})$')
REGEX_ID_TO_DATETIME_LEGACY = re.compile(r'^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{0,9})$')

def datetime_to_id(t=None):
    """Convert a datetime to webscrapbook ID.

    Args:
        t: datetime. Create an ID for now if None.
    """
    if t is None:
        t = datetime.now(timezone.utc)
    else:
        # convert to UTC datetime
        t = t.astimezone(timezone.utc)

    return (f'{t.year}{t.month:02}{t.day:02}{t.hour:02}{t.minute:02}'
        f'{t.second:02}{int(t.microsecond * 0.001):03}')


def id_to_datetime(id):
    """Convert a webscrapbook ID to datetime.
    """
    m = REGEX_ID_TO_DATETIME.search(id)
    if m:
        try:
            return datetime(
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                int(m.group(6)),
                int(m.group(7)) * 1000,
                timezone.utc,
                )
        except ValueError:
            pass
    return None


def datetime_to_id_legacy(t=None):
    """Convert a datetime to legacy ScrapBook ID.

    Args:
        t: datetime. Create an ID for now if None.
    """
    if t is None:
        t = datetime.now()
    else:
        # convert to local datetime
        t = t.astimezone()

    return f'{t.year}{t.month:02}{t.day:02}{t.hour:02}{t.minute:02}{t.second:02}'


def id_to_datetime_legacy(id):
    """Convert a legacy ScrapBook ID to datetime.
    """
    m = REGEX_ID_TO_DATETIME_LEGACY.search(id)
    if m:
        try:
            ms = m.group(7)
            try:
                ms = int(ms) * 10 ** (6 - len(ms))
            except ValueError:
                ms = 0

            return datetime(
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                int(m.group(6)),
                int(ms),
                )
        except ValueError:
            pass
    return None


def validate_filename(filename, force_ascii=False):
    """Transliterates the given string to be a safe filename

    See also: scrapbook.validateFilename of WebScrapBook.
    """
    fn = filename

    # control chars are bad for filename
    fn = re.sub(r'[\x00-\x1F\x7F]+', '', fn)

    # leading/trailing spaces and dots are not allowed on Windows
    fn = re.sub(r'^\.', '_.', fn)
    fn = re.sub(r'^ +', '', fn)
    fn = re.sub(r'[. ]+$', '', fn)

    # bad chars on most OS
    fn = re.sub(r'[:"?*\\/|]', '_', fn)

    # bad chars on Windows, replace with adequate direction
    fn = fn.replace('<', '(').replace('>', ')')

    # "~" is not allowed by browser.downloads
    fn = fn.replace('~', '-')

    if force_ascii:
        fn = quote(fn, safe="""!_#$&'()*+,-./:;<=>?@[\\]^_`{|}~""")

    # prevent empty filename
    fn = fn or "_"

    return fn


#########################################################################
# String handling
#########################################################################

def crop(text, width=70, ellipsis='...'):
    if len(text) > width:
        return text[:max(width - len(ellipsis), 0)] + ellipsis
    return text


REGEX_FORMAT_STRING = re.compile(r'%(\w*)%')

def format_string(text, mapping):
    """A very simple implementation for string formatting with placeholders.

    - Only single special char '%' is used, making it easy to implement for
      both Python and JavaScript.
    - Special char itself can be easily escaped.
    - Does not raise an exception if not formatted correctly.
    - Good for user-provided strings.
    """
    def formatter(m):
        k = m.group(1)
        if k == '':
            return '%'
        return mapping.get(k, '')

    return REGEX_FORMAT_STRING.sub(formatter, text)


REGEX_COMPRESS_CODE = re.compile(r'[^\S　]+')

def compress_code(code):
    return REGEX_COMPRESS_CODE.sub(' ', code)


#########################################################################
# Codecs and text encoding
#########################################################################

# ref: https://encoding.spec.whatwg.org/#names-and-labels
LABEL_ENCODING_MAPPING = {
    'unicode-1-1-utf-8': 'UTF-8',
    'unicode11utf8': 'UTF-8',
    'unicode20utf8': 'UTF-8',
    'utf-8': 'UTF-8',
    'utf8': 'UTF-8',
    'x-unicode20utf8': 'UTF-8',
    '866': 'IBM866',
    'cp866': 'IBM866',
    'csibm866': 'IBM866',
    'ibm866': 'IBM866',
    'csisolatin2': 'ISO-8859-2',
    'iso-8859-2': 'ISO-8859-2',
    'iso-ir-101': 'ISO-8859-2',
    'iso8859-2': 'ISO-8859-2',
    'iso88592': 'ISO-8859-2',
    'iso_8859-2': 'ISO-8859-2',
    'iso_8859-2:1987': 'ISO-8859-2',
    'l2': 'ISO-8859-2',
    'latin2': 'ISO-8859-2',
    'csisolatin3': 'ISO-8859-3',
    'iso-8859-3': 'ISO-8859-3',
    'iso-ir-109': 'ISO-8859-3',
    'iso8859-3': 'ISO-8859-3',
    'iso88593': 'ISO-8859-3',
    'iso_8859-3': 'ISO-8859-3',
    'iso_8859-3:1988': 'ISO-8859-3',
    'l3': 'ISO-8859-3',
    'latin3': 'ISO-8859-3',
    'csisolatin4': 'ISO-8859-4',
    'iso-8859-4': 'ISO-8859-4',
    'iso-ir-110': 'ISO-8859-4',
    'iso8859-4': 'ISO-8859-4',
    'iso88594': 'ISO-8859-4',
    'iso_8859-4': 'ISO-8859-4',
    'iso_8859-4:1988': 'ISO-8859-4',
    'l4': 'ISO-8859-4',
    'latin4': 'ISO-8859-4',
    'csisolatincyrillic': 'ISO-8859-5',
    'cyrillic': 'ISO-8859-5',
    'iso-8859-5': 'ISO-8859-5',
    'iso-ir-144': 'ISO-8859-5',
    'iso8859-5': 'ISO-8859-5',
    'iso88595': 'ISO-8859-5',
    'iso_8859-5': 'ISO-8859-5',
    'iso_8859-5:1988': 'ISO-8859-5',
    'arabic': 'ISO-8859-6',
    'asmo-708': 'ISO-8859-6',
    'csiso88596e': 'ISO-8859-6',
    'csiso88596i': 'ISO-8859-6',
    'csisolatinarabic': 'ISO-8859-6',
    'ecma-114': 'ISO-8859-6',
    'iso-8859-6': 'ISO-8859-6',
    'iso-8859-6-e': 'ISO-8859-6',
    'iso-8859-6-i': 'ISO-8859-6',
    'iso-ir-127': 'ISO-8859-6',
    'iso8859-6': 'ISO-8859-6',
    'iso88596': 'ISO-8859-6',
    'iso_8859-6': 'ISO-8859-6',
    'iso_8859-6:1987': 'ISO-8859-6',
    'csisolatingreek': 'ISO-8859-7',
    'ecma-118': 'ISO-8859-7',
    'elot_928': 'ISO-8859-7',
    'greek': 'ISO-8859-7',
    'greek8': 'ISO-8859-7',
    'iso-8859-7': 'ISO-8859-7',
    'iso-ir-126': 'ISO-8859-7',
    'iso8859-7': 'ISO-8859-7',
    'iso88597': 'ISO-8859-7',
    'iso_8859-7': 'ISO-8859-7',
    'iso_8859-7:1987': 'ISO-8859-7',
    'sun_eu_greek': 'ISO-8859-7',
    'csiso88598e': 'ISO-8859-8',
    'csisolatinhebrew': 'ISO-8859-8',
    'hebrew': 'ISO-8859-8',
    'iso-8859-8': 'ISO-8859-8',
    'iso-8859-8-e': 'ISO-8859-8',
    'iso-ir-138': 'ISO-8859-8',
    'iso8859-8': 'ISO-8859-8',
    'iso88598': 'ISO-8859-8',
    'iso_8859-8': 'ISO-8859-8',
    'iso_8859-8:1988': 'ISO-8859-8',
    'visual': 'ISO-8859-8',
    'csiso88598i': 'ISO-8859-8-I',
    'iso-8859-8-i': 'ISO-8859-8-I',
    'logical': 'ISO-8859-8-I',
    'csisolatin6': 'ISO-8859-10',
    'iso-8859-10': 'ISO-8859-10',
    'iso-ir-157': 'ISO-8859-10',
    'iso8859-10': 'ISO-8859-10',
    'iso885910': 'ISO-8859-10',
    'l6': 'ISO-8859-10',
    'latin6': 'ISO-8859-10',
    'iso-8859-13': 'ISO-8859-13',
    'iso8859-13': 'ISO-8859-13',
    'iso885913': 'ISO-8859-13',
    'iso-8859-14': 'ISO-8859-14',
    'iso8859-14': 'ISO-8859-14',
    'iso885914': 'ISO-8859-14',
    'csisolatin9': 'ISO-8859-15',
    'iso-8859-15': 'ISO-8859-15',
    'iso8859-15': 'ISO-8859-15',
    'iso885915': 'ISO-8859-15',
    'iso_8859-15': 'ISO-8859-15',
    'l9': 'ISO-8859-15',
    'iso-8859-16': 'ISO-8859-16',
    'cskoi8r': 'KOI8-R',
    'koi': 'KOI8-R',
    'koi8': 'KOI8-R',
    'koi8-r': 'KOI8-R',
    'koi8_r': 'KOI8-R',
    'koi8-ru': 'KOI8-U',
    'koi8-u': 'KOI8-U',
    'csmacintosh': 'macintosh',
    'mac': 'macintosh',
    'macintosh': 'macintosh',
    'x-mac-roman': 'macintosh',
    'dos-874': 'windows-874',
    'iso-8859-11': 'windows-874',
    'iso8859-11': 'windows-874',
    'iso885911': 'windows-874',
    'tis-620': 'windows-874',
    'windows-874': 'windows-874',
    'cp1250': 'windows-1250',
    'windows-1250': 'windows-1250',
    'x-cp1250': 'windows-1250',
    'cp1251': 'windows-1251',
    'windows-1251': 'windows-1251',
    'x-cp1251': 'windows-1251',
    'ansi_x3.4-1968': 'windows-1252',
    'ascii': 'windows-1252',
    'cp1252': 'windows-1252',
    'cp819': 'windows-1252',
    'csisolatin1': 'windows-1252',
    'ibm819': 'windows-1252',
    'iso-8859-1': 'windows-1252',
    'iso-ir-100': 'windows-1252',
    'iso8859-1': 'windows-1252',
    'iso88591': 'windows-1252',
    'iso_8859-1': 'windows-1252',
    'iso_8859-1:1987': 'windows-1252',
    'l1': 'windows-1252',
    'latin1': 'windows-1252',
    'us-ascii': 'windows-1252',
    'windows-1252': 'windows-1252',
    'x-cp1252': 'windows-1252',
    'cp1253': 'windows-1253',
    'windows-1253': 'windows-1253',
    'x-cp1253': 'windows-1253',
    'cp1254': 'windows-1254',
    'csisolatin5': 'windows-1254',
    'iso-8859-9': 'windows-1254',
    'iso-ir-148': 'windows-1254',
    'iso8859-9': 'windows-1254',
    'iso88599': 'windows-1254',
    'iso_8859-9': 'windows-1254',
    'iso_8859-9:1989': 'windows-1254',
    'l5': 'windows-1254',
    'latin5': 'windows-1254',
    'windows-1254': 'windows-1254',
    'x-cp1254': 'windows-1254',
    'cp1255': 'windows-1255',
    'windows-1255': 'windows-1255',
    'x-cp1255': 'windows-1255',
    'cp1256': 'windows-1256',
    'windows-1256': 'windows-1256',
    'x-cp1256': 'windows-1256',
    'cp1257': 'windows-1257',
    'windows-1257': 'windows-1257',
    'x-cp1257': 'windows-1257',
    'cp1258': 'windows-1258',
    'windows-1258': 'windows-1258',
    'x-cp1258': 'windows-1258',
    'x-mac-cyrillic': 'x-mac-cyrillic',
    'x-mac-ukrainian': 'x-mac-cyrillic',
    'chinese': 'GBK',
    'csgb2312': 'GBK',
    'csiso58gb231280': 'GBK',
    'gb2312': 'GBK',
    'gb_2312': 'GBK',
    'gb_2312-80': 'GBK',
    'gbk': 'GBK',
    'iso-ir-58': 'GBK',
    'x-gbk': 'GBK',
    'gb18030': 'gb18030',
    'big5': 'Big5',
    'big5-hkscs': 'Big5',
    'cn-big5': 'Big5',
    'csbig5': 'Big5',
    'x-x-big5': 'Big5',
    'cseucpkdfmtjapanese': 'EUC-JP',
    'euc-jp': 'EUC-JP',
    'x-euc-jp': 'EUC-JP',
    'csiso2022jp': 'ISO-2022-JP',
    'iso-2022-jp': 'ISO-2022-JP',
    'csshiftjis': 'Shift_JIS',
    'ms932': 'Shift_JIS',
    'ms_kanji': 'Shift_JIS',
    'shift-jis': 'Shift_JIS',
    'shift_jis': 'Shift_JIS',
    'sjis': 'Shift_JIS',
    'windows-31j': 'Shift_JIS',
    'x-sjis': 'Shift_JIS',
    'cseuckr': 'EUC-KR',
    'csksc56011987': 'EUC-KR',
    'euc-kr': 'EUC-KR',
    'iso-ir-149': 'EUC-KR',
    'korean': 'EUC-KR',
    'ks_c_5601-1987': 'EUC-KR',
    'ks_c_5601-1989': 'EUC-KR',
    'ksc5601': 'EUC-KR',
    'ksc_5601': 'EUC-KR',
    'windows-949': 'EUC-KR',
    'unicodefffe': 'UTF-16BE',
    'utf-16be': 'UTF-16BE',
    'csunicode': 'UTF-16LE',
    'iso-10646-ucs-2': 'UTF-16LE',
    'ucs-2': 'UTF-16LE',
    'unicode': 'UTF-16LE',
    'unicodefeff': 'UTF-16LE',
    'utf-16': 'UTF-16LE',
    'utf-16le': 'UTF-16LE',
    'csiso2022kr': 'replacement',
    'hz-gb-2312': 'replacement',
    'iso-2022-cn': 'replacement',
    'iso-2022-cn-ext': 'replacement',
    'iso-2022-kr': 'replacement',
    'replacement': 'replacement',
    'x-user-defined': 'x-user-defined',
    }

# all lower-case
CODECS_MAPPING = {
    'big5': 'big5hkscs',
    'x-mac-cyrillic': 'mac_cyrillic',
    'replacement': None,
    'x-user-defined': None,
    }

def fix_codec(name):
    """Remap codec name

    Map a browser-supported encoding label to the corresponding encoding.

    Some codecs are widely used and de-facto standard for web browsers. For
    example, most browsers display cp950 extended chars correctly even if the
    charset of the web page is defined as 'big5'. To prevent unexpected
    gibberish when we try to parse text in Python, we need to remap the codec
    name of a web page from 'big5' to 'big5hkscs' using this first.
    """
    try:
        name = LABEL_ENCODING_MAPPING[name.lower()]
    except KeyError:
        pass

    try:
        return CODECS_MAPPING[name.lower()]
    except KeyError:
        return name


# starting of BOM32 is equal to BOM16, so check the former first
BOM_DETECTORS = [
    ('UTF-8-SIG', codecs.BOM_UTF8),
    ('UTF-32-LE', codecs.BOM_UTF32_LE),
    ('UTF-32-BE', codecs.BOM_UTF32_BE),
    ('UTF-16-LE', codecs.BOM_UTF16_LE),
    ('UTF-16-BE', codecs.BOM_UTF16_BE),
    ]

def sniff_bom(fh):
    """Sniff a possibly existing BOM

    Args:
        fh: an opened file handler, must be seekable.

    Return:
        str: corresponding codec name for a found BOM if a BOM is found (and
            sets pointer at the position after the BOM), or None otherwise.
    """
    # will read less if the file is smaller
    raw = fh.read(4)

    for enc, bom in BOM_DETECTORS:
        if raw.startswith(bom):
            fh.seek(len(bom))
            return enc

    fh.seek(0)
    return None


#########################################################################
# URL and string
#########################################################################

def is_nullhost(host):
    """Determine if given host is 0.0.0.0 equivalent.
    """
    if host == '0.0.0.0':
        return True

    try:
        if IPv6Address(host) == IPv6Address('::'):
            return True
    except AddressValueError:
        pass

    return False


def is_localhost(host):
    """Determine if given host is localhost equivalent.
    """
    if host in ('localhost', '127.0.0.1'):
        return True

    try:
        if IPv6Address(host) == IPv6Address('::1'):
            return True
    except AddressValueError:
        pass

    return False


def get_breadcrumbs(paths, base='', topname='.'):
    """Generate (label, subpath, sep, is_last) tuples.
    """
    base = base.rstrip('/') + '/'
    paths = paths.copy()
    paths[0] = paths[0].strip('/')

    if not paths[0]:
        yield (topname, base, '/', True)
        return

    yield (topname, base, '/', False)

    # handle zip root, which is something like /archive.zip!/
    is_zip_root = False
    if paths[-1] == '':
        paths.pop()
        is_zip_root = True

    paths_max = len(paths) - 1
    pathlist = []
    for path_idx, path in enumerate(paths):
        pathlist.append([])
        parts = path.split('/')
        parts_max = len(parts) - 1
        for part_idx, part in enumerate(parts):
            pathlist[-1].append(part)
            subpath = '!/'.join('/'.join(p) for p in pathlist)
            sep = '!/' if part_idx == parts_max and (path_idx < paths_max or is_zip_root) else '/'
            is_last = path_idx == paths_max and part_idx == parts_max
            yield (part, base + subpath + sep, sep, is_last)


def get_relative_url(path, start, path_is_dir=True, start_is_dir=True):
    """Get a relative URL (quoted) from filesystem start to path
    """
    if not start_is_dir:
        start = os.path.dirname(start)
    rel_path = os.path.relpath(path, start)
    if path_is_dir:
        rel_path = os.path.join(rel_path, '')
    return pathname2url(rel_path)  # this quotes URL


#########################################################################
# Filesystem related manipulation
#########################################################################

FileInfo = namedtuple('FileInfo', ['name', 'type', 'size', 'last_modified'])


def launch(path):
    """Launch a file or open a directory in the explorer.
    """
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])


def view_in_explorer(path):
    """Open the parent directory of a file or directory
       in the explorer.
    """
    if sys.platform == "win32":
        subprocess.run(["explorer", "/select,", path])
    elif sys.platform == "darwin":
        try:
            subprocess.run(["open", "-R", path])
        except OSError:
            # fallback for older OS X
            launch(os.path.dirname(path))
    else:
        try:
            subprocess.run(["nautilus", "--select", path])
        except OSError:
            # fallback if no nautilus
            launch(os.path.dirname(path))


def checksum(file, method='sha1', chunk_size=4096):
    """Calculate the checksum of a file.

    Args:
        file: str, path-like, or file-like bytes object
    """
    try:
        fh = open(file, 'rb')
    except TypeError:
        fh = file

    try:
        h = hashlib.new(method)
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)

        return h.hexdigest()
    finally:
        if fh != file:
            fh.close()


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
        name = file[len(base)+1:].replace('\\', '/')

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
                if info.type is None: continue
                yield info

    else:
        for root, dirs, files in os.walk(base):
            for dir in dirs:
                file = os.path.join(root, dir)
                info = file_info(file, base)
                if info.type is None: continue
                yield info
            for file in files:
                file = os.path.join(root, file)
                info = file_info(file, base)
                if info.type is None: continue
                yield info


def format_filesize(bytes, si=False):
    """Convert file size from bytes to human readable presentation.
    """
    try:
        bytes = int(bytes)
    except (ValueError, TypeError):
        return ''

    if si:
        thresh = 1000
        units = ['B', 'kB','MB','GB','TB','PB','EB','ZB','YB']
    else:
        thresh = 1024
        units =  ['B', 'KB','MB','GB','TB','PB','EB','ZB','YB']

    e = math.floor(math.log(max(1, bytes)) / math.log(thresh))
    e = min(e, len(units) - 1)
    n = bytes / thresh ** e
    tpl = '{:.1f} {}' if (e >=1 and n < 10) else '{:.0f} {}'
    return tpl.format(n, units[e])


COMPRESSIBLE_TYPES = {
    'application/xml',

    # historical non-text/* javascript types
    # ref: https://mimesniff.spec.whatwg.org/
    'application/javascript',
    'application/ecmascript',
    'application/x-ecmascript',
    'application/x-javascript',

    'application/json',
    }

COMPRESSIBLE_SUFFIXES = {
    '+xml',
    '+json',
    }

def is_compressible(mimetype):
    """Guess if the given mimetype is compressible."""
    if not mimetype:
        return False

    if mimetype.startswith('text/'):
        return True

    if mimetype in COMPRESSIBLE_TYPES:
        return True

    for suffix in COMPRESSIBLE_SUFFIXES:
        if mimetype.endswith(suffix):
            return True

    return False


def mime_is_html(mime):
    return mime in {'text/html', 'application/xhtml+xml'}


def mime_is_xhtml(mime):
    return mime == 'application/xhtml+xml'


def mime_is_archive(mime):
    return mime in {'application/html+zip', 'application/x-maff'}


def mime_is_htz(mime):
    return mime == 'application/html+zip'


def mime_is_maff(mime):
    return mime == 'application/x-maff'


def mime_is_markdown(mime):
    return mime in {'text/markdown'}


def mime_is_wsba(mime):
    return mime in {'application/wsba+zip'}


def is_html(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime_is_html(mime)


def is_xhtml(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime_is_xhtml(mime)


def is_archive(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime_is_archive(mime)


def is_htz(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime_is_htz(mime)


def is_maff(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime_is_maff(mime)


def is_markdown(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime_is_markdown(mime)


def is_wsba(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime_is_wsba(mime)


#########################################################################
# ZIP handling
#########################################################################

class ZipDirNotFoundError(Exception):
    pass


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
            base = subpath + '/'
            for entry in zh.namelist():
                if entry.startswith(base):
                    return FileInfo(name=name, type='dir', size=None, last_modified=None)

    return FileInfo(name=name, type=None, size=None, last_modified=None)


def zip_listdir(zip, subpath, recursive=False):
    """Generates FileInfo(s) and omit invalid entries.

    Raise ZipDirNotFoundError if subpath does not exist.

    NOTE: It is possible that entry mydir/ does not exist while
    mydir/foo.bar exists. Check for matching subentries to make sure whether
    the directory exists.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
    """
    base = subpath.rstrip('/')
    if base: base += '/'
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


def zip_hasdir(zip, subpath):
    """Check if a directory exists in the ZIP.

    NOTE: It is possible that entry mydir/ does not exist while
    mydir/foo.bar exists. Check for matching subentries to make sure whether
    the directory exists.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
    """
    base = subpath.rstrip('/') + '/'
    if base == '/':
        return True

    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
        # if directory entry exists, we are done
        try:
            zh.getinfo(base)
            return True
        except KeyError:
            pass

        # otherwise, look for an implicit directory
        for path in zh.namelist():
            if path.startswith(base):
                return True

    return False


def zip_compress(zip, filename, subpath):
    """Compress src to be the subpath in the zip.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        filename: path of the source file or directory
        subpath: internal path to a file or folder (without trailing slash)

    Raises:
        shutil.Error: if any child file cannot be added to the zip
    """
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

            base_cut = len(os.path.join(filename, ''))
            for root, dirs, files in os.walk(filename, followlinks=True):
                for dir in dirs:
                    src = os.path.join(root, dir)
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
                    dst = src[base_cut:]
                    if os.sep != '/':
                        dst = dst.replace(os.sep, '/')
                    dst = subpath + dst
                    compressible = is_compressible(mimetypes.guess_type(dst)[0])
                    compress_type = zipfile.ZIP_DEFLATED if compressible else zipfile.ZIP_STORED
                    compresslevel = 9 if compressible else None
                    try:
                        try:
                            zh.write(src, dst, compress_type, compresslevel)
                        except TypeError:
                            # compresslevel is supported since Python 3.7
                            zh.write(src, dst, compress_type)
                    except OSError as why:
                        errors.append((src, dst, str(why)))

            if errors:
                raise shutil.Error(errors)
        else:
            compressible = is_compressible(mimetypes.guess_type(subpath)[0])
            compress_type = zipfile.ZIP_DEFLATED if compressible else zipfile.ZIP_STORED
            compresslevel = 9 if compressible else None
            try:
                zh.write(filename, subpath, compress_type, compresslevel)
            except TypeError:
                # compresslevel is supported since Python 3.7
                zh.write(filename, subpath, compress_type)


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


#########################################################################
# HTTP manipulation
#########################################################################

ContentType = namedtuple('ContentType', ['type', 'parameters'])

PARSE_CONTENT_TYPE_REGEX_MIME = re.compile(r'^(.*?)(?=;|$)', re.I)
PARSE_CONTENT_TYPE_REGEX_FIELD = re.compile(r';((?:"(?:\\.|[^"])*(?:"|$)|[^"])*?)(?=;|$)', re.I)
PARSE_CONTENT_TYPE_REGEX_KEY_VALUE = re.compile(r'\s*(.*?)\s*=\s*("(?:\\.|[^"])*"|[^"]*?)\s*$', re.I)
PARSE_CONTENT_TYPE_REGEX_DQUOTE_VALUE = re.compile(r'^"(.*?)"$')

def parse_content_type(string):
    """Parse content type header.

    Return:
        ContentType: type and parameter keys are all lower case.
    """
    type = None
    parameters = {}

    if not string:
        return ContentType(type, parameters)

    match_mime = PARSE_CONTENT_TYPE_REGEX_MIME.search(string)
    if match_mime:
        string = string[match_mime.end():]
        type = match_mime.group(1).strip().lower()

        while True:
            match_field = PARSE_CONTENT_TYPE_REGEX_FIELD.search(string)
            if not match_field:
                break

            string = string[match_field.end():]
            parameter = match_field.group(1)
            match_key_value = PARSE_CONTENT_TYPE_REGEX_KEY_VALUE.search(parameter)

            if match_key_value:
                field = match_key_value.group(1).lower()
                value = match_key_value.group(2)

                # handle double quoted value
                match_dquote = PARSE_CONTENT_TYPE_REGEX_DQUOTE_VALUE.search(value)
                if match_dquote:
                    value = match_dquote.group(1)

                parameters[field] = value

    return ContentType(type, parameters)


DataUri = namedtuple('DataUri', ['bytes', 'mime', 'parameters'])

PARSE_DATAURI_REGEX_FIELDS = re.compile(r'^data:([^,]*?)(;base64)?,([^#]*)', re.I)
PARSE_DATAURI_REGEX_KEY_VALUE = re.compile(r'^(.*?)=(.*?)$')

class DataUriMalformedError(Exception):
    pass

def parse_datauri(datauri):
    """Parse a Data URI

    Args:
        datauri: the data URI string

    Returns:
        DataUri: a tuple containing information

    Raises:
        DataUriMalformedError
    """
    match_fields = PARSE_DATAURI_REGEX_FIELDS.search(datauri)
    if not match_fields:
        raise DataUriMalformedError('Malformed fields')

    mediatype = match_fields.group(1)
    base64 = bool(match_fields.group(2))
    data = match_fields.group(3)

    parts = mediatype.split(';')
    mime = parts.pop(0)
    parameters = {}
    for part in parts:
        match_key_value = PARSE_DATAURI_REGEX_KEY_VALUE.search(part)
        if match_key_value:
            parameters[match_key_value.group(1).lower()] = match_key_value.group(2)

    if base64:
        try:
            bytes_ = b64decode(data)
        except binascii.Error as exc:
            raise DataUriMalformedError(f'Malformed base64 sequence: {exc}') from exc
    else:
        # decode precent-encoding to corresponding byte
        # non-ASCII chars are encoded as UTF-8 bytes
        bytes_ = unquote_to_bytes(data)

    return DataUri(bytes_, mime, parameters)


#########################################################################
# HTML manipulation
#########################################################################

def _get_html_charset(fh, quickly=True):
    """Internal method to read a charset from meta charset.
    """
    try:
        for event, elem in etree.iterparse(fh, encoding='ISO-8859-1', html=True, events=('start',), tag=('meta', 'body')):
            if elem.tag == 'meta':
                charset = elem.attrib.get('charset')
                if charset:
                    return charset.strip()

                if elem.attrib.get('http-equiv', '').lower() == 'content-type':
                    _, params = parse_content_type(elem.attrib.get('content', ''))
                    charset = params.get('charset')
                    if charset:
                        return charset

            elif elem.tag == 'body':
                # presume that no <meta> will appear after <body> start
                # for a normal HTML to exit early
                if quickly:
                    return None

            # clean up to save memory
            elem.clear()
            while elem.getprevious() is not None:
                try:
                    del elem.getparent()[0]
                except TypeError:
                    # broken html may generate extra root elem
                    break
    except etree.Error:
        pass

    return None

def get_html_charset(file, default='UTF-8', none_from_bom=True, quickly=True):
    """Search for the correct charset to read an HTML file.

    Args:
        file: str, path-like, or file-like bytes object
        default: fallback encoding if not found
        none_from_bom: True to return None if charset is determined from BOM
            (to prevent error for lxml)
        quickly: True to exit early for normal HTML files
    """
    try:
        fh = open(file, 'rb')
    except TypeError:
        fh = file
    except FileNotFoundError:
        fh = None

    if fh:
        try:
            # Seek for the correct charset (encoding).
            # If a charset is not specified, lxml may select a wrong encoding for
            # the entire document if there is text before first meta charset.
            charset = sniff_bom(fh)
            if charset:
                if none_from_bom:
                    # lxml does not accept "UTF-16-LE" or so, but can auto-detect
                    # encoding from BOM if encoding is None
                    # ref: https://bugs.launchpad.net/lxml/+bug/1463610
                    return None

                return charset

            charset = _get_html_charset(fh, quickly=quickly)

            if charset is None:
                charset = default

            if charset is not None:
                charset = fix_codec(charset)

            return charset
        finally:
            if fh != file:
                fh.close()

    return default


def load_html_tree(file, options={}):
    """Load HTML document tree.

    Args:
        file: str, path-like, or file-like bytes object
        options: additional options for the HTML parser
    """
    try:
        fh = open(file, 'rb')
    except TypeError:
        fh = file
    except FileNotFoundError:
        fh = None

    if not fh:
        return None

    try:
        charset = get_html_charset(fh)
        fh.seek(0)

        try:
            return lxml.html.parse(fh, lxml.html.HTMLParser(encoding=charset, **options))
        except etree.Error:
            return None
    finally:
        if fh != file:
            fh.close()


def load_html_markups(file, parser=HTMLParser, **kwargs):
    """Load HTML document markups using native html.parser.

    Args:
        file: str, path-like, or file-like bytes object
    """
    try:
        fh = open(file, 'rb')
    except TypeError:
        fh = file
    except FileNotFoundError:
        fh = None

    if not fh:
        return None

    try:
        charset = get_html_charset(fh)
        fh.seek(0)

        p = parser(**kwargs)
        for s in codecs.iterdecode(fh, charset):
            if not s:
                break
            p.feed(s)
        p.close()

        setattr(load_html_markups, 'last_encoding', charset)
        return p._rv
    finally:
        if fh != file:
            fh.close()


MetaRefreshInfo = namedtuple('MetaRefreshInfo', ['time', 'target', 'context'])

META_REFRESH_REGEX_URL = re.compile(r'^\s*url\s*=\s*(.*?)\s*$', re.I)

# meta refresh in these tags does not always work
META_REFRESH_CONTEXT_TAGS = {
    'title',
    # 'style', 'script',  # not visible by lxml
    # 'frame',  # self-closing tag
    'iframe',
    # 'object', 'applet',  # refresh works in the browser
    # 'audio', 'video',  # refresh works in the browser
    # 'canvas',  # refresh works in the browser
    'noframes', 'noscript', 'noembed',
    'textarea',
    'template',
    # 'svg', 'math',  # refresh works in the browser
    'xmp',
    # 'parsererror',  # doesn't appear in lxml for xhtml
    }

# meta refresh in these tags should never work
META_REFRESH_FORBID_TAGS = {
    'title',
    'textarea',
    'template',
    'xmp',
    }

def iter_meta_refresh(file, encoding='ISO-8859-1'):
    """Iterate through meta refreshes from a file.

    Args:
        file: str, path-like, or file-like bytes object
        encoding: encoding for the HTML file
    """
    try:
        fh = open(file, 'rb')
    except TypeError:
        fh = file
    except FileNotFoundError:
        fh = None

    if not fh:
        return

    try:
        contexts = []
        for event, elem in etree.iterparse(fh, encoding=encoding, html=True, events=('start', 'end')):
            if event == 'start':
                if elem.tag in META_REFRESH_CONTEXT_TAGS:
                    contexts.append(elem.tag)
                    continue

                if (elem.tag == 'meta' and
                        elem.attrib.get('http-equiv', '').lower() == 'refresh'):
                    time, _, content = elem.attrib.get('content', '').partition(';')

                    try:
                        time = int(time)
                    except ValueError:
                        time = 0

                    match_url = META_REFRESH_REGEX_URL.search(content)
                    target = match_url.group(1) if match_url else None
                    context = contexts.copy() if contexts else None
                    yield MetaRefreshInfo(time=time, target=target, context=context)

            elif event == 'end':
                if contexts and elem.tag == contexts[-1]:
                    contexts.pop()
                    continue

                # clean up to save memory
                elem.clear()
                while elem.getprevious() is not None:
                    try:
                        del elem.getparent()[0]
                    except TypeError:
                        # broken html may generate extra root elem
                        break
    finally:
        if fh != file:
            fh.close()


def parse_meta_refresh(file):
    """Retrieve meta refresh target from a file.

    Args:
        file: str, path-like, or file-like bytes object
    """
    for info in iter_meta_refresh(file):
        if info.time == 0 and info.target is not None and not info.context:
            return info
    return MetaRefreshInfo(time=None, target=None, context=None)


#########################################################################
# MAFF manipulation
#########################################################################

MaffPageInfo = namedtuple('MaffPageInfo', ['title', 'originalurl', 'archivetime', 'indexfilename', 'charset'])

def get_maff_pages(zip):
    """Get a list of pages (MaffPageInfo).

    Args:
        zip: path, file-like object, or zipfile.ZipFile
    """
    pages = []
    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
        # get top folders and their content files
        topdirs = {}
        for entry in zh.namelist():
            topdir, sep, p = entry.partition('/')
            topdir = topdirs.setdefault(topdir + sep, [])
            if p: topdir.append(entry)

        # get index files
        for topdir in topdirs:
            rdf = topdir + 'index.rdf'
            try:
                with zh.open(rdf, 'r') as f:
                    meta = parse_maff_index_rdf(f)
            except Exception:
                pass
            else:
                if meta.indexfilename is not None:
                    pages.append(MaffPageInfo(
                            meta.title,
                            meta.originalurl,
                            meta.archivetime,
                            topdir + meta.indexfilename,
                            meta.charset,
                            ))
                    continue

            for entry in topdirs[topdir]:
                if entry.startswith(topdir + 'index.') and entry != topdir + 'index.rdf':
                    pages.append(MaffPageInfo(
                            None,
                            None,
                            None,
                            entry,
                            None,
                            ))

    return pages


def parse_maff_index_rdf(fh):
    """Read MAFF metadata from the given RDF file handler.
    """
    def load_attr(attr):
        try:
            node = root.find('./RDF:Description/MAF:' + attr, ns)
            return node.attrib['{' + ns['RDF'] + '}' + 'resource']
        except Exception:
            return None

    ns = {
        'MAF': "http://maf.mozdev.org/metadata/rdf#",
        'NC': "http://home.netscape.com/NC-rdf#",
        'RDF': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        }

    text = fh.read().decode('UTF-8')
    root = etree.XML(text)

    return MaffPageInfo(
            load_attr('title'),
            load_attr('originalurl'),
            load_attr('archivetime'),
            load_attr('indexfilename'),
            load_attr('charset'),
            )


#########################################################################
# Encrypt and security
#########################################################################

class Encrypt():
    """Simple hash encryption with salt.
    """
    def md5(self, text, salt=''):
        return hashlib.md5((text + salt).encode('UTF-8')).hexdigest()

    def sha1(self, text, salt=''):
        return hashlib.sha1((text + salt).encode('UTF-8')).hexdigest()

    def sha224(self, text, salt=''):
        return hashlib.sha224((text + salt).encode('UTF-8')).hexdigest()

    def sha256(self, text, salt=''):
        return hashlib.sha256((text + salt).encode('UTF-8')).hexdigest()

    def sha384(self, text, salt=''):
        return hashlib.sha384((text + salt).encode('UTF-8')).hexdigest()

    def sha512(self, text, salt=''):
        return hashlib.sha512((text + salt).encode('UTF-8')).hexdigest()

    def sha3_224(self, text, salt=''):
        return hashlib.sha3_224((text + salt).encode('UTF-8')).hexdigest()

    def sha3_256(self, text, salt=''):
        return hashlib.sha3_256((text + salt).encode('UTF-8')).hexdigest()

    def sha3_384(self, text, salt=''):
        return hashlib.sha3_384((text + salt).encode('UTF-8')).hexdigest()

    def sha3_512(self, text, salt=''):
        return hashlib.sha3_512((text + salt).encode('UTF-8')).hexdigest()

    def plain(self, text, salt=''):
        return text + salt

    def encrypt(self, text, salt='', method='plain'):
        fn = getattr(self, method, None)

        if not callable(fn):
            print(f'Encrypt method "{method}" not implemented, fallback to "plain".', file=sys.stderr)
            fn = self.plain

        return fn(text, salt)

encrypt = Encrypt().encrypt
