#!/usr/bin/env python3
"""Miscellaneous utilities
"""
import sys, os
import stat
import subprocess
import collections
from collections import namedtuple
from lxml import etree
import zipfile
import math
import re
import hashlib
import time
from urllib.parse import quote, unquote
from ipaddress import IPv6Address, AddressValueError
from secrets import token_urlsafe
from ._compat.contextlib import nullcontext


#########################################################################
# Abstract classes
#########################################################################

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


#########################################################################
# Objects handling
#########################################################################

def make_hashable(obj):
    if isinstance(obj, collections.abc.Hashable):
        return obj
    elif isinstance(obj, collections.abc.Set):
        return frozenset(make_hashable(v) for v in obj)
    elif isinstance(obj, collections.abc.Sequence):
        return tuple(make_hashable(v) for v in obj)
    elif isinstance(obj, collections.abc.Mapping):
        return frozendict((k, make_hashable(v)) for k, v in obj.items())
    else:
        raise TypeError(f"unable to make '{type(obj).__name__}' hashable")


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
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def view_in_explorer(path):
    """Open the parent directory of a file or directory
       in the explorer.
    """
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", path])
    elif sys.platform == "darwin":
        try:
            subprocess.Popen(["open", "-R", path])
        except OSError:
            # fallback for older OS X
            launch(os.path.dirname(path))
    else:
        try:
            subprocess.Popen(["nautilus", "--select", path])
        except OSError:
            # fallback if no nautilus
            launch(os.path.dirname(path))


def checksum(file, method='sha1', chunk_size=4096):
    """Calculate the checksum of a file.
    """
    h = hashlib.new(method)
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
        f.close()
    return h.hexdigest()


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


#########################################################################
# ZIP handling
#########################################################################

class ZipDirNotFoundError(Exception):
    pass


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
            lm = info.date_time
            epoch = int(time.mktime((lm[0], lm[1], lm[2], lm[3], lm[4], lm[5], 0, 0, -1)))
            return FileInfo(name=name, type='file', size=info.file_size, last_modified=epoch)

        try:
            info = zh.getinfo(subpath + '/')
        except KeyError:
            pass
        else:
            lm = info.date_time
            epoch = int(time.mktime((lm[0], lm[1], lm[2], lm[3], lm[4], lm[5], 0, 0, -1)))
            return FileInfo(name=name, type='dir', size=None, last_modified=epoch)

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

        if not len(entries) and not dir_exist:
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


#########################################################################
# HTML manipulation
#########################################################################

MetaRefreshInfo = namedtuple('MetaRefreshInfo', ['time', 'target'])


def parse_meta_refresh(file):
    """Retrieve meta refresh target from a file.

    Args:
        file: str, path-like, or file-like object
    """
    try:
        fh = open(file, 'rb')
    except TypeError:
        fh = file
    except FileNotFoundError:
        fh = None

    if fh:
        try:
            for event, elem in etree.iterparse(fh, html=True, events=('end',), tag='meta'):
                if elem.attrib.get('http-equiv', '').lower() == 'refresh':
                    time, _, content = elem.attrib.get('content', '').partition(';')

                    try:
                        time = int(time)
                    except ValueError:
                        time = 0

                    m = re.match(r'^\s*url\s*=\s*(.*?)\s*$', content, flags=re.I)
                    target = m.group(1) if m else None

                    if time == 0 and target is not None:
                        return MetaRefreshInfo(time=time, target=target)

                # clean up to save memory
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
        finally:
            if fh != file:
                fh.close()

    return MetaRefreshInfo(time=None, target=None)


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


class TokenHandler():
    """Handle security token validation to avoid XSRF attack.
    """
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.last_purge = 0

    def acquire(self, now=None):
        if now is None:
            now = int(time.time())

        self.check_delete_expire(now)

        token = token_urlsafe()
        token_file = os.path.join(self.cache_dir, token)
        while os.path.lexists(token_file):
            token = token_urlsafe()
            token_file = os.path.join(self.cache_dir, token)

        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        with open(token_file, 'w', encoding='UTF-8') as f:
            f.write(str(now + self.DEFAULT_EXPIRY))

        return token

    def validate(self, token, now=None):
        if now is None:
            now = int(time.time())

        token_file = os.path.join(self.cache_dir, token)

        try:
            with open(token_file, 'r', encoding='UTF-8') as f:
                expire = int(f.read())
        except (FileNotFoundError, IsADirectoryError):
            return False

        if now >= expire:
            os.remove(token_file)
            return False

        return True

    def delete(self, token):
        token_file = os.path.join(self.cache_dir, token)

        try:
            os.remove(token_file)
        except OSError:
            pass

    def delete_expire(self, now=None):
        if now is None:
            now = int(time.time())

        try:
            token_files = os.scandir(self.cache_dir)
        except FileNotFoundError:
            pass
        else:
            for token_file in token_files:
                try:
                    with open(token_file, 'r', encoding='UTF-8') as f:
                        expire = int(f.read())
                except (OSError, ValueError):
                    continue
                if now >= expire:
                    os.remove(token_file)

    def check_delete_expire(self, now=None):
        if now is None:
            now = int(time.time())

        if now >= self.last_purge + self.PURGE_INTERVAL:
            self.last_purge = now
            self.delete_expire(now)

    PURGE_INTERVAL = 3600  # in seconds
    DEFAULT_EXPIRY = 1800  # in seconds
