"""Scrapbook book handler.
"""
import os
import zipfile
import re
import json
from urllib.parse import urlsplit, unquote

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
    # Escape U+2028 and U+2029 for embedded JSON data used as JavaScript code
    # to prevent script breakage and potential security issue in old browsers
    # not supporting ES2019, as they are not allowed in a string literal.
    # https://stackoverflow.com/questions/16005091/node-js-javascript-stringify
    JSON_TRANSLATER = str.maketrans({'\u2028': '\\u2028', '\u2029': '\\u2029'})

    REGEX_TREE_FILE_WRAPPER = re.compile(r'^(?:/\*.*\*/|[^(])+\(([\s\S]*)\)(?:/\*.*\*/|[\s;])*$')
    REGEX_ITEM_NOTE = re.compile(r'^.*?<pre>\n?([^<]*(?:<(?!/pre>)[^<]*)*)\n</pre>.*$', re.S)

    # A javascript string >= 256 MiB (UTF-16 chars) causes an error in some
    # older browsers. Split into several smaller JavaScript files to prevent
    # such issue.

    # Split at around 256 K items (a meta item is mostly < 512 bytes)
    SAVE_META_THRESHOLD = 256 * 1024

    # Split at around 4 M entries (a TOC entry is mostly < 32 bytes)
    SAVE_TOC_THRESHOLD = 4 * 1024 * 1024

    # Split at at around 128 MiB
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
    SPECIAL_ITEM_ID = {
        'root',
        'hidden',
        'recycle',
        }
    ITEM_TYPES_WITH_OPTIONAL_INDEX = {
        'folder',
        'separator',
        'bookmark',
        }
    ITEM_INDEX_ALLOWED_EXT = {
        '.html',
        '.htz',
        '.maff',
        '.htm',
        }
    ITEM_NOTE_FORMATTER = """\
<!DOCTYPE html><html><head>\
<meta charset="UTF-8">\
<meta name="viewport" content="width=device-width">\
<style>pre { white-space: pre-wrap; overflow-wrap: break-word; }</style>\
</head><body><pre>
%NOTE_CONTENT%
</pre></body></html>"""

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

    def __repr__(self):
        repr_str = ', '.join(f'{attr}={repr(getattr(self, attr))}' for attr in self.REPR_ATTRS)
        return f'{self.__class__.__name__}({repr_str})'

    def get_subpath(self, file):
        """Get subpath of a file related to root.
        """
        return self.host.get_subpath(file)

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

        # avoid error if file is empty
        if text == '':
            return {}

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
            data.update(self.load_tree_file(file))

        # remove top-level None values to allow quick clear by appending file
        # e.g. add meta1.js with {'id1': None} to quickly delete 'id1' in meta.js
        for k in list(data):
            if data[k] is None:
                del data[k]

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
scrapbook.meta({json.dumps(data, ensure_ascii=False, indent=2).translate(self.JSON_TRANSLATER)})""")

    def save_meta_files(self):
        """Save to tree/meta#.js
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
                self.backup(file)
                os.remove(file)
            except FileNotFoundError:
                break
            i += 1

    def save_toc_file(self, i, data):
        self.save_tree_file('toc', i, f"""/**
 * Feel free to edit this file, but keep data code valid JSON format.
 */
scrapbook.toc({json.dumps(data, ensure_ascii=False, indent=2).translate(self.JSON_TRANSLATER)})""")

    def save_toc_files(self):
        """Save to tree/toc#.js
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
                self.backup(file)
                os.remove(file)
            except FileNotFoundError:
                break
            i += 1

    def save_fulltext_file(self, i, data):
        self.save_tree_file('fulltext', i, f"""/**
 * This file is generated by WebScrapBook and is not intended to be edited.
 */
scrapbook.fulltext({json.dumps(data, ensure_ascii=False, indent=1).translate(self.JSON_TRANSLATER)})""")

    def save_fulltext_files(self):
        """Save to tree/fulltext#.js
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
                self.backup(file)
                os.remove(file)
            except FileNotFoundError:
                break
            i += 1

    def backup(self, file, **kwargs):
        """A shortcut for auto backup.
        """
        self.host.auto_backup(file, **kwargs)

    def get_lock(self, name, *args, **kwargs):
        return self.host.get_lock(f'book-{self.id}-{name}', *args, **kwargs)

    def get_tree_lock(self, *args, **kwargs):
        return self.get_lock('tree', *args, **kwargs)

    def get_index_paths(self, index):
        if util.is_maff(index):
            pages = util.get_maff_pages(os.path.join(self.data_dir, index))
            return [p.indexfilename for p in pages]

        if util.is_htz(index):
            return ['index.html']

        return [os.path.basename(index)]

    def get_tree_from_index_file(self, file):
        try:
            if util.is_html(file):
                with open(file, 'rb') as fh:
                    return util.load_html_tree(fh)

            if util.is_htz(file):
                with zipfile.ZipFile(file) as zh:
                    with zh.open('index.html') as fh:
                        return util.load_html_tree(fh)

            if util.is_maff(file):
                info = next(iter(util.get_maff_pages(file)), None)
                if not info:
                    return None

                with zipfile.ZipFile(file) as zh:
                    with zh.open(info.indexfilename) as fh:
                        return util.load_html_tree(fh)
        except (OSError, zipfile.BadZipFile, KeyError):
            return None

        return None

    def get_icon_file(self, item):
        """Get favicon file path of an item.

        Returns:
            str file path of the favicon, or None if not determinable
        """
        icon = item.get('icon', '')

        if not icon:
            return None

        u = urlsplit(icon)

        if u.scheme:
            return None

        if u.netloc:
            return None

        if not u.path:
            return None

        if u.path.startswith('/'):
            return None

        index = item.get('index', '')
        return os.path.normpath(os.path.join(self.data_dir, os.path.dirname(index), unquote(u.path)))

    def load_note_file(self, file):
        with open(file, encoding='UTF-8') as fh:
            content = fh.read()

        return self.REGEX_ITEM_NOTE.sub(r'\1', content)

    def save_note_file(self, file, content):
        data = util.format_string(self.ITEM_NOTE_FORMATTER, {
            'NOTE_CONTENT': content,
            })
        # enforce LF to prevent bad parsing for legacy ScrapBook
        with open(file, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(data)
