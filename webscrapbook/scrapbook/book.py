"""Scrapbook book handler.
"""
import os
import shutil
import re
import json
from .. import WSB_DIR
from .. import util


class TreeFileError(ValueError):
    def __init__(self, msg, filename=None):
        self.msg = msg
        self.filename = filename


class TreeFileMalformedError(TreeFileError):
    pass


class TreeFileMalformedWrappingError(TreeFileMalformedError):
    """Malformed wrapping part of a tree file
    """


class TreeFileMalformedJsonError(TreeFileMalformedError):
    """A subclass for JSONDecodeError

    This exception should be raised from a JSONDecodeError, and details
        are accessible through __cause__ attribute.
    """


class Book:
    """Main scrapbook book controller.
    """
    REGEX_TREE_FILE_WRAPPER = re.compile(r'^(?:/\*.*\*/|[^(])+\(([\s\S]*)\)(?:/\*.*\*/|[\s;])*$')
    SAVE_META_THRESHOLD = 256 * 1024
    SAVE_TOC_THRESHOLD = 4 * 1024 * 1024
    SAVE_FULLTEXT_THRESHOLD = 128 * 1024 * 1024
    REPR_ATTRS = ('id', 'name', 'top_dir')
    DEFAULT_META = {
        'id': None,
        'index': None,
        'title': None,
        'type': None,
        'create': None,
        'modify': None,
        'source': None,
        'icon': None,
        'comment': None,
        }
    TYPES_OPTIONAL_INDEX = {
        'folder',
        'separator',
        'bookmark',
        }

    def __init__(self, host, book_id=''):
        self.host = host
        config = host.config['book'][book_id]
        self.id = book_id
        self.name = config['name']
        self.root = host.root
        self.top_dir = os.path.normpath(os.path.join(host.chroot, config['top_dir']))
        self.data_dir = os.path.normpath(os.path.join(self.top_dir, config['data_dir']))
        self.tree_dir = os.path.normpath(os.path.join(self.top_dir, config['tree_dir']))
        self.no_tree = config['no_tree']

        self.meta = None
        self.toc = None
        self.fulltext = None
        self.backup_dir = None

    def __repr__(self):
        repr_str = ', '.join(f'{attr}={repr(getattr(self, attr))}' for attr in self.REPR_ATTRS)
        return f'{self.__class__.__name__}({repr_str})'

    def get_subpath(self, file):
        """Get subpath of a file related to top_dir.

        Also convert "\" to "/", which makes it useful for showing a file in
            issue safely.
        """
        return os.path.relpath(file, self.root).replace('\\', '/')

    def get_tree_file(self, name, index=0):
        return os.path.join(self.tree_dir, f'{name}{index or ""}.js')

    def iter_tree_files(self, name):
        i = 0
        while True:
            file = self.get_tree_file(name, i)
            if not os.path.exists(file):
                break
            yield file
            i += 1

    def iter_meta_files(self):
        yield from self.iter_tree_files('meta')

    def iter_toc_files(self):
        yield from self.iter_tree_files('toc')

    def iter_fulltext_files(self):
        yield from self.iter_tree_files('fulltext')

    def load_tree_file(self, file):
        """Load a tree file.

        Raises:
            OSError: failed to open or read (unlikely to happen as this is
                usually called via iter_tree_files() and file existence has
                been checked in prior)
            TreeFileMalformedError: file malformed
        """
        with open(file, encoding='UTF-8') as fh:
            text = fh.read()

        m = self.REGEX_TREE_FILE_WRAPPER.search(text)

        if not m:
            raise TreeFileMalformedWrappingError(f'Malformed tree file wrapping', filename=file)

        try:
            return json.loads(m.group(1))
        except json.decoder.JSONDecodeError as exc:
            raise TreeFileMalformedJsonError(f'Malformed tree file: {exc}', filename=file) from exc

    def load_tree_files(self, name):
        data = {}
        for file in self.iter_tree_files(name):
            d = self.load_tree_file(file)
            data.update(d)
        return data

    def load_meta_files(self, refresh=False):
        if refresh or self.meta is None:
            self.meta = self.load_tree_files('meta')

    def load_toc_files(self, refresh=False):
        if refresh or self.toc is None:
            self.toc = self.load_tree_files('toc')

    def load_fulltext_files(self, refresh=False):
        if refresh or self.fulltext is None:
            self.fulltext = self.load_tree_files('fulltext')

    def save_tree_file(self, name, index, data):
        """Save a tree file.

        Raises:
            OSError: failed to write
        """
        file = self.get_tree_file(name, index)
        self.backup(file)
        with open(file, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(data)

    def save_meta_file(self, i, data):
        self.save_tree_file('meta', i, f"""/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.meta({json.dumps(data, ensure_ascii=False, indent=2)})""")

    def save_meta_files(self):
        """Save to tree/meta#.js

        A javascript string >= 256 MiB (UTF-16 chars) causes an error
        in the browser. Split each js file at around 256 K items to
        prevent the issue. (An item is mostly < 512 bytes)
        """
        os.makedirs(os.path.join(self.tree_dir), exist_ok=True)
        i = 0
        size = 1
        meta = {}
        for id in list(self.meta):
            if self.meta[id] is None:
                del self.meta[id]
                continue
            meta[id] = self.meta[id]
            size += 1
            if size >= self.SAVE_META_THRESHOLD:
                self.save_meta_file(i, meta)
                i += 1
                size = 0
                meta = {}

        if size:
            self.save_meta_file(i, meta)
            i += 1

        # remove unused tree/meta#.js
        while True:
            file = self.get_tree_file('meta', i)
            try:
                os.remove(file)
            except FileNotFoundError:
                break
            i += 1

    def save_toc_file(self, i, data):
        self.save_tree_file('toc', i, f"""/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.toc({json.dumps(data, ensure_ascii=False, indent=2)})""")

    def save_toc_files(self):
        """Save to tree/toc#.js

        A javascript string >= 256 MiB (UTF-16 chars) causes an error
        in the browser. Split each js file at around 4 M entries to
        prevent the issue. (An entry is mostly < 32 bytes)
        """
        os.makedirs(os.path.join(self.tree_dir), exist_ok=True)
        i = 0
        size = 1
        toc = {}
        for id in list(self.toc):
            if self.toc[id] is None:
                del self.toc[id]
                continue
            toc[id] = self.toc[id]
            size += 1 + len(toc[id])
            if size >= self.SAVE_TOC_THRESHOLD:
                self.save_toc_file(i, toc)
                i += 1
                size = 0
                toc = {}

        if size:
            self.save_toc_file(i, toc)
            i += 1

        # remove unused tree/toc#.js
        while True:
            file = self.get_tree_file('toc', i)
            try:
                os.remove(file)
            except FileNotFoundError:
                break
            i += 1

    def save_fulltext_file(self, i, data):
        self.save_tree_file('fulltext', i, f"""/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({json.dumps(data, ensure_ascii=False, indent=1)})""")

    def save_fulltext_files(self):
        """Save to tree/fulltext#.js

        A javascript string >= 256 MiB (UTF-16 chars) causes an error
        in the browser. Split each js file at at around 128 MiB to
        prevent the issue.
        """
        os.makedirs(os.path.join(self.tree_dir), exist_ok=True)
        i = 0
        size = 1
        fulltext = {}
        for id in list(self.fulltext):
            if self.fulltext[id] is None:
                del self.fulltext[id]
                continue
            fulltext[id] = self.fulltext[id]
            for path in fulltext[id]:
                size += len(fulltext[id][path]['content'])
            if size >= self.SAVE_FULLTEXT_THRESHOLD:
                self.save_fulltext_file(i, fulltext)
                i += 1
                size = 0
                fulltext = {}

        if size:
            self.save_fulltext_file(i, fulltext)
            i += 1

        # remove unused tree/fulltext#.js
        while True:
            file = self.get_tree_file('fulltext', i)
            try:
                os.remove(file)
            except FileNotFoundError:
                break
            i += 1

    def init_backup(self, ts=True):
        """Setup a backup dir for following backups until next set.

        Args:
            ts: a webscrapbook ID as timestamp. True to generate one from
            current time. False to disable backup.
        """
        if ts is False:
            self.backup_dir = None
            return

        if ts is True:
            ts = util.datetime_to_id()

        self.backup_dir = os.path.join(self.root, WSB_DIR, 'backup', ts)

    def backup(self, file, base=None):
        """Create a backup for the file.

        Args:
            file: a path-like for the file or directory to backup. Silently
                skipped if it doesn't exists or the backup cannot be performed.
            base: an arbitrary base directory to calculate the backup file
                path since. Must be an absolute path.

        Raises:
            OSError: failed to copy
        """
        if base is None:
            base = self.root

        if not self.backup_dir:
            return

        if not os.path.exists(file):
            return

        if not os.path.abspath(file).startswith(os.path.join(base, '')):
            return

        dst = os.path.join(self.backup_dir, os.path.relpath(file, base))
        if os.path.lexists(dst):
            try:
                shutil.rmtree(dst)
            except NotADirectoryError:
                os.remove(dst)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            shutil.copytree(file, dst)
        except NotADirectoryError:
            shutil.copy2(file, dst)

    def get_index_paths(self, index):
        if util.is_maff(index):
            pages = util.get_maff_pages(os.path.join(self.data_dir, index))
            return [p.indexfilename for p in pages]

        if util.is_htz(index):
            return ['index.html']

        return [os.path.basename(index)]

    def get_lock(self, name, *args, **kwargs):
        return self.host.get_lock(f'book-{self.id}-{name}', *args, **kwargs)

    def get_tree_lock(self, *args, **kwargs):
        return self.get_lock('tree', *args, **kwargs)
