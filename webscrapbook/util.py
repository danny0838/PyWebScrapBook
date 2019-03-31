#!/usr/bin/env python3
"""Miscellaneous utilities
"""
import sys, os
import subprocess
from collections import namedtuple
from html.parser import HTMLParser
from lxml import etree
import zipfile
import math
import re
import hashlib
import time
from secrets import token_urlsafe
from urllib.parse import quote, unquote


#########################################################################
# URL and string
#########################################################################

def get_breadcrumbs(path, base='', topname='.', subarchivepath=None):
    """Generate (label, subpath, sep, is_last) tuples.
    """
    base = base.rstrip('/') + '/'
    subpathfull = path.strip('/')

    if subarchivepath is None:
        # /path/to/directory/
        archivepath = None
    elif subarchivepath == "":
        # /path/to/archive.ext!/
        archivepath = subpathfull
    else:
        # /path/to/archive.ext!/subarchivepath/
        archivepath = subpathfull[0:-(len(subarchivepath) + 1)]

    if subpathfull:
        yield (topname, base, '/', False)
        subpaths = []
        parts = subpathfull.split('/');
        parts_len = len(parts)
        for idx, part in enumerate(parts):
            subpaths.append(part)
            subpath = '/'.join(subpaths)
            if subpath == archivepath:
                yield (part[:-1], base + subpath + '/', '!/', idx == parts_len - 1)
            else:
                yield (part, base + subpath + '/', '/', idx == parts_len - 1)
    else:
        yield (topname, base, '/', True)


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
        except:
            # fallback for older OS X
            launch(os.path.dirname(path))
    else:
        try:
            subprocess.Popen(["nautilus", "--select", path])
        except:
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


def file_info(file):
    """Read basic file information.
    """
    name = os.path.basename(file)

    if not os.path.lexists(file):
        type = None
    elif os.path.islink(file):
        type = 'link'
    elif os.path.isdir(file):
        type = 'dir'
    elif os.path.isfile(file):
        type = 'file'
    else:
        type = 'unknown'

    try:
        statinfo = os.stat(file)
        size = statinfo.st_size if type is 'file' else None
        last_modified = statinfo.st_mtime
    except:
        # unexpected error when getting stat info
        size = None
        last_modified = None

    return FileInfo(name=name, type=type, size=size, last_modified=last_modified)


def listdir(root):
    """Generates FileInfo(s) and omit invalid entries.
    """
    for filename in os.listdir(root):
        file = os.path.join(root, filename)
        info = file_info(file)
        if info.type is None: continue
        yield info


def format_filesize(bytes, si=False):
    """Convert file size from bytes to human readable presentation.
    """
    try:
        bytes = int(bytes)
    except:
        return ''

    if si:
        thresh = 1000
        units = ['B', 'kB','MB','GB','TB','PB','EB','ZB','YB']
    else:
        thresh = 1024
        units =  ['B', 'KB','MB','GB','TB','PB','EB','ZB','YB']

    e = math.floor(math.log(bytes) / math.log(thresh))
    n = bytes / math.pow(thresh, e)
    tpl = '{:.1f} {}' if (e >=1 and n < 10) else '{:.0f} {}'
    return tpl.format(n, units[e])


#########################################################################
# ZIP handling
#########################################################################

class ZipDirNotFoundError(Exception):
    pass


def zip_file_info(zip, subpath, check_missing_dir=False):
    """Read basic file information from ZIP.

    subpath: 'dir' and 'dir/' are both supported
    """
    if not isinstance(zip, zipfile.ZipFile):
        zip = zipfile.ZipFile(zip)

    subpath = subpath.rstrip('/')
    basename = os.path.basename(subpath)

    try:
        info = zip.getinfo(subpath)
        lm = info.date_time
        epoch = int(time.mktime((lm[0], lm[1], lm[2], lm[3], lm[4], lm[5], 0, 0, -1)))
        return FileInfo(name=basename, type='file', size=info.file_size, last_modified=epoch)
    except KeyError:
        pass

    try:
        info = zip.getinfo(subpath + '/')
        lm = info.date_time
        epoch = int(time.mktime((lm[0], lm[1], lm[2], lm[3], lm[4], lm[5], 0, 0, -1)))
        return FileInfo(name=basename, type='dir', size=None, last_modified=epoch)
    except KeyError:
        pass

    if check_missing_dir:
        base = subpath + '/'
        for entry in zip.namelist():
            if entry.startswith(base):
                return FileInfo(name=basename, type='dir', size=None, last_modified=None)

    return FileInfo(name=basename, type=None, size=None, last_modified=None)


def zip_listdir(zip, subpath):
    """Generates FileInfo(s) and omit invalid entries.

    Raise ZipDirNotFoundError if subpath does not exist. 

    NOTE: It is possible that entry mydir/ does not exist while
    mydir/foo.bar exists. Check for matching subentries fo make sure whether
    the directory exists.
    """
    if not isinstance(zip, zipfile.ZipFile):
        zip = zipfile.ZipFile(zip)

    base = subpath.rstrip('/')
    if base: base += '/'
    base_len = len(base)
    dir_exist = not base
    entries = {}
    for filename in zip.namelist():
        if not filename.startswith(base):
            continue

        if filename == base:
            dir_exist = True
            continue

        subpath = filename[base_len:]
        entry, _, _ = subpath.partition('/')
        entries.setdefault(entry, True)

    if not len(entries) and not dir_exist:
        raise ZipDirNotFoundError('Directory "{}/" does not exist in the zip.'.format(base))

    for entry in entries:
        info = zip_file_info(zip, base + entry)

        if info.type is None:
            yield FileInfo(name=entry, type='dir', size=None, last_modified=None)
        else:
            yield info


#########################################################################
# HTML manipulation
#########################################################################

MetaRefreshInfo = namedtuple('MetaRefreshInfo', ['time', 'target'])


class MetaRefreshParser(HTMLParser):
    """Retrieve meta refresh target from HTML.
    """
    def __init__(self):
        self.meta_refresh_stack = []
        super().__init__()

    def handle_starttag(self, tag, attrs):
        if tag != 'meta':
            return

        attrs = dict(attrs)

        if attrs.get('http-equiv', '').lower().strip() != 'refresh':
            return

        time, _, content = attrs.get('content', '').partition(';')

        try:
            time = int(time)
        except ValueError:
            time = 0

        m = re.match(r'^\s*url\s*=\s*(.*?)\s*$', content)
        target = m.group(1) if m else None
        self.meta_refresh_stack.append(MetaRefreshInfo(time=time, target=target))


def parse_meta_refresh(fh):
    """Retrieve meta refresh target from a file.

    fh: a file or file handler.
    """
    if type(fh) is str:
        try:
            fh = open(fh, 'rb')
        except:
            fh = None

    if fh is not None:
        try:
            parser = MetaRefreshParser()
            parser.feed(fh.read().decode('UTF-8'))
            for mr in parser.meta_refresh_stack:
                if mr.time == 0 and mr.target is not None:
                    return mr
        except:
            pass

    return MetaRefreshInfo(time=None, target=None)


#########################################################################
# MAFF manipulation
#########################################################################

MaffPageInfo = namedtuple('MaffPageInfo', ['title', 'originalurl', 'archivetime', 'indexfilename', 'charset'])

def get_maff_pages(file):
    """Get a list of pages (MaffPageInfo).
    """
    pages = []
    with zipfile.ZipFile(file) as zip:
        # get top folders and their content files
        topdirs = {}
        for entry in zip.namelist():
            topdir, sep, p = entry.partition('/')
            topdir = topdirs.setdefault(topdir + sep, [])
            if p: topdir.append(entry)

        # get index files
        for topdir in topdirs:
            rdf = topdir + 'index.rdf'
            try:
                with zip.open(rdf, 'r') as f:
                    meta = parse_maff_index_rdf(f)
                    f.close()

                if meta.indexfilename is not None:
                    pages.append(MaffPageInfo(
                            meta.title,
                            meta.originalurl,
                            meta.archivetime,
                            topdir + meta.indexfilename,
                            meta.charset,
                            ))
                    continue
            except:
                pass

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
        except:
            raise
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
        fn = getattr(self, method)

        if not callable(fn):
            print('Encrypt method "{}" not implemented, fallback to "plain".'.format(method), file=sys.stderr)
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
        open(token_file, 'w', encoding='UTF-8').write(str(now + self.DEFAULT_EXPIRY))

        return token

    def validate(self, token, now=None):
        if now is None:
            now = int(time.time())

        token_file = os.path.join(self.cache_dir, token)

        try:
            expire = int(open(token_file, 'r', encoding='UTF-8').read())
        except FileNotFoundError:
            return False

        if now >= expire:
            self.delete(token)
            return False

        return True

    def delete(self, token):
        token_file = os.path.join(self.cache_dir, token)

        try:
            os.remove(token_file)
        except:
            pass

    def delete_expire(self, now=None):
        if now is None:
            now = int(time.time())

        try:
            for token_file in os.listdir(self.cache_dir):
                token_file = os.path.join(self.cache_dir, token_file)
                try:
                    expire = int(open(token_file, 'r', encoding='UTF-8').read())
                except:
                    continue

                if now >= expire:
                    os.remove(token_file)
        except FileNotFoundError:
            pass

    def check_delete_expire(self, now=None):
        if now is None:
            now = int(time.time())

        if now >= self.last_purge + self.PURGE_INTERVAL:
            self.last_purge = now
            self.delete_expire(now)

    PURGE_INTERVAL = 3600  # in seconds
    DEFAULT_EXPIRY = 1800  # in seconds
