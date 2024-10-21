"""Scrapbook book handler.
"""
import functools
import glob
import hashlib
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit
from urllib.request import pathname2url

from lxml import etree

from .. import util
from .._polyfill import zipfile

# A shortcut for getting an ID at current time. Also for easier mock testing.
_id_now = functools.partial(util.datetime_to_id, None)


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
    REGEX_ITEM_POSTIT = re.compile(r'^.*?<pre>\n?([^<]*(?:<(?!/pre>)[^<]*)*)\n</pre>.*$', re.S)

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
        'charset': None,
        'marked': None,
        'locked': None,
        'location': None,
    }
    ROOT_ITEM_ID = 'root'
    HIDDEN_ITEM_ID = 'hidden'
    RECYCLE_ITEM_ID = 'recycle'
    SPECIAL_ITEM_ID = dict.fromkeys((
        ROOT_ITEM_ID,
        HIDDEN_ITEM_ID,
        RECYCLE_ITEM_ID,
    ))
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
        '.xhtml',
        '.xht',
        '.svg',
    }
    ITEM_POSTIT_FORMATTER = """\
<!DOCTYPE html><html><head>\
<meta charset="UTF-8">\
<meta name="viewport" content="width=device-width">\
<style>pre { white-space: pre-wrap; overflow-wrap: break-word; }</style>\
</head><body><pre>
%POSTIT_CONTENT%
</pre></body></html>"""

    TEMPLATE_DIR = 'templates'
    TEMPLATES = {
        ('note', '.html'): {
            'filename': 'note_template.html',
            'content': """\
<!DOCTYPE html>
<html data-scrapbook-type="note">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title data-scrapbook-elem="title">%NOTE_TITLE%</title>
</head>
<body>%NOTE_TITLE%</body>
</html>
""",
        },
        ('note', '.md'): {
            'filename': 'note_template.md',
            'content': """%NOTE_TITLE%""",
        },
    }

    def __init__(self, host, book_id=''):
        self.host = host
        self.config = config = host.config['book'][book_id]
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

    @staticmethod
    def checksum(obj, method='sha1'):
        """Get a checksum of an object (by its JSONified string)."""
        m = hashlib.new(method)
        gen = json.JSONEncoder(
            ensure_ascii=False,
            check_circular=False,
            separators=(',', ':'),
        ).iterencode(obj)
        for chunk in gen:
            m.update(chunk.encode('UTF-8'))
        return m.digest()

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
            raise TreeFileMalformedWrappingError('Malformed tree file wrapping', filename=file)

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
        for k in tuple(data):
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

    def save_tree_file(self, name, index, gen):
        """Save a tree file.

        Raises:
            OSError: failed to write
        """
        file = self.get_tree_file(name, index)
        self.backup(file)
        with open(file, 'w', encoding='UTF-8', newline='\n') as fh:
            for chunk in gen:
                fh.write(chunk.translate(self.JSON_TRANSLATER))

    def _gen_meta_file(self, data):
        yield '/* Feel free to edit this file, but keep data code valid JSON format. */\n'
        yield 'scrapbook.meta('
        yield from json.JSONEncoder(
            ensure_ascii=False,
            check_circular=False,
            indent=2,
        ).iterencode(data)
        yield ')'

    def save_meta_files(self):
        """Save to tree/meta#.js
        """
        os.makedirs(os.path.join(self.tree_dir), exist_ok=True)
        i = 0
        size = 1
        meta = {}
        for id in tuple(self.meta):
            if self.meta[id] is None:
                del self.meta[id]
                continue
            meta[id] = self.meta[id]
            size += 1
            if size >= self.SAVE_META_THRESHOLD:
                self.save_tree_file('meta', i, self._gen_meta_file(meta))
                i += 1
                size = 0
                meta = {}

        if size:
            self.save_tree_file('meta', i, self._gen_meta_file(meta))
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

    def _gen_toc_file(self, data):
        yield '/* Feel free to edit this file, but keep data code valid JSON format. */\n'
        yield 'scrapbook.toc('
        yield from json.JSONEncoder(
            ensure_ascii=False,
            check_circular=False,
            indent=2,
        ).iterencode(data)
        yield ')'

    def save_toc_files(self):
        """Save to tree/toc#.js
        """
        os.makedirs(os.path.join(self.tree_dir), exist_ok=True)
        i = 0
        size = 1
        toc = {}
        for id in tuple(self.toc):
            if self.toc[id] is None:
                del self.toc[id]
                continue
            toc[id] = self.toc[id]
            size += 1 + len(toc[id])
            if size >= self.SAVE_TOC_THRESHOLD:
                self.save_tree_file('toc', i, self._gen_toc_file(toc))
                i += 1
                size = 0
                toc = {}

        if size:
            self.save_tree_file('toc', i, self._gen_toc_file(toc))
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

    def _gen_fulltext_file(self, data):
        yield '/* This file is generated by WebScrapBook and is not intended to be edited. */\n'
        yield 'scrapbook.fulltext('
        yield from json.JSONEncoder(
            ensure_ascii=False,
            check_circular=False,
            indent=1,
        ).iterencode(data)
        yield ')'

    def save_fulltext_file(self, i, data):
        self.save_tree_file('fulltext', i, self._gen_fulltext_file(data))

    def save_fulltext_files(self):
        """Save to tree/fulltext#.js
        """
        os.makedirs(os.path.join(self.tree_dir), exist_ok=True)
        i = 0
        size = 1
        fulltext = {}
        for id in tuple(self.fulltext):
            if self.fulltext[id] is None:
                del self.fulltext[id]
                continue
            fulltext[id] = self.fulltext[id]
            for path in fulltext[id]:
                size += len(fulltext[id][path]['content'])
            if size >= self.SAVE_FULLTEXT_THRESHOLD:
                self.save_tree_file('fulltext', i, self._gen_fulltext_file(fulltext))
                i += 1
                size = 0
                fulltext = {}

        if size:
            self.save_tree_file('fulltext', i, self._gen_fulltext_file(fulltext))
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
        if util.is_html(file):
            return util.load_html_tree(file)

        if util.is_htz(file):
            with zipfile.ZipFile(file) as zh:
                with zh.open('index.html') as fh:
                    return util.load_html_tree(fh)

        if util.is_maff(file):
            try:
                info = next(iter(util.get_maff_pages(file)))
            except StopIteration:
                raise ValueError('no page in MAFF archive')

            with zipfile.ZipFile(file) as zh:
                with zh.open(info.indexfilename) as fh:
                    return util.load_html_tree(fh)

        if util.is_svg(file):
            with open(file, 'rb') as fh:
                return etree.parse(fh)

        raise ValueError('unsupported index file type')

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

    def load_postit_file(self, file):
        with open(file, encoding='UTF-8') as fh:
            content = fh.read()

        return self.REGEX_ITEM_POSTIT.sub(r'\1', content)

    def save_postit_file(self, file, content):
        data = util.format_string(self.ITEM_POSTIT_FORMATTER, {
            'POSTIT_CONTENT': content,
        })
        # enforce LF to prevent bad parsing for legacy ScrapBook
        with open(file, 'w', encoding='UTF-8', newline='\n') as fh:
            fh.write(data)

    def get_reachable_items(self, item_ids=None, dict=None):
        """Get a flattened set of reachable items, including self.

        Args:
            item_ids: a str or an iterable of str of item IDs to search from,
                or None for common special items
            dict: a dict to store the final result, or None to generate one
        """
        if item_ids is None:
            item_ids = self.SPECIAL_ITEM_ID
        elif isinstance(item_ids, str):
            item_ids = (item_ids,)

        if dict is None:
            dict = {}

        for item_id in item_ids:
            self._get_reachable_items(item_id, dict)

        return dict

    def _get_reachable_items(self, item_id, dict):
        if item_id in dict:
            return

        dict[item_id] = True

        try:
            child_ids = self.toc[item_id]
        except KeyError:
            return

        for child_id in child_ids:
            self._get_reachable_items(child_id, dict)

    def get_unique_id(self, item_id=None):
        """Get an unique item ID.

        Args:
            item_id: a pre-generated item ID in the format of datetime_to_id()
        """
        if item_id is None:
            item_id = _id_now()

        while (item_id in self.meta
               or os.path.lexists(os.path.join(self.data_dir, item_id))
               or next(glob.iglob(glob.escape(os.path.join(self.data_dir, item_id)) + '.*'), None)
               ):
            try:
                dt += timedelta(milliseconds=1)  # noqa: F821
            except UnboundLocalError:
                dt = util.id_to_datetime(item_id) or datetime.now(timezone.utc)
                dt += timedelta(milliseconds=1)
            item_id = util.datetime_to_id(dt)

        return item_id

    def get_template(self, type, ext='.html'):
        try:
            tpl = self.TEMPLATES[(type, ext)]
        except KeyError:
            raise ValueError(f'Unknown template: {(type, ext)!r}')

        file = os.path.join(self.tree_dir, self.TEMPLATE_DIR, tpl['filename'])

        # generate if not exists
        if not os.path.lexists(file):
            util.fs.save(file, tpl['content'].encode('UTF-8'))

        with open(file, encoding='UTF-8') as fh:
            content = fh.read()

        return content

    def get_item(self, item_id, include_parents=False):
        """Singular version shortcut of get_items()."""
        return self.get_items((item_id,), include_parents).get(item_id)

    def get_items(self, items, include_parents=False):
        """Get information about items in the book.

        Args:
            items: an iterable of item IDs
            include_parents: whether to include parents information

        Returns:
            dict: information of the items
        """
        reverse_toc = {}
        if include_parents:
            for parent_id, toc in self.toc.items():
                for i, item_id in enumerate(toc):
                    reverse_toc.setdefault(item_id, []).append(
                        (parent_id, i),
                    )

        results = {}
        for item_id in items:
            result = {}

            meta = self.meta.get(item_id)
            if meta is not None:
                result['meta'] = meta

            children = self.toc.get(item_id)
            if children is not None:
                result['children'] = children

            if include_parents:
                parents = reverse_toc.get(item_id)
                if parents is not None:
                    result['parents'] = parents

            if result:
                results[item_id] = result

        return results

    def add_item(self, item=None, target_parent_id=ROOT_ITEM_ID, target_index=None):
        """Singular version shortcut of add_items()."""
        return self.add_items((item,), target_parent_id, target_index)

    def add_items(self, items, target_parent_id=ROOT_ITEM_ID, target_index=None):
        """Add items to the book.

        Args:
            items: an iterable of dict with item properties (or None to
                generate a new item).
            target_parent_id: None to not insert to any parent
            target_index: None to append to last

        Returns:
            dict: ID and meta of the added items

        Raises:
            ValueError: if the provided item ID already exists, the target
                parent does not exist, the target index is invalid, etc.
        """
        if not (target_parent_id is None
                or target_parent_id in self.meta
                or target_parent_id in self.SPECIAL_ITEM_ID):
            raise ValueError(f'Invalid target parent ID: {target_parent_id!r}')

        if not (target_index is None or target_index >= 0):
            raise ValueError(f'Invalid target index: {target_index!r}')

        added = {}
        for item in items:
            if item is None:
                continue

            try:
                item_id = item['id']
            except KeyError:
                continue

            if item_id in self.SPECIAL_ITEM_ID:
                raise ValueError(f'Item ID is preserved: {item_id!r}')

            if item_id in self.meta:
                raise ValueError(f'Item already exists: {item_id!r}')

            if item_id in added:
                raise ValueError(f'Item is duplicated: {item_id!r}')

            added[item_id] = True

        # add to meta (uniquify ID)
        rv = {}
        for item in items:
            item_id = self._add_item(item)
            rv[item_id] = self.meta[item_id]

        # add to TOC if target parent is provided
        if rv and target_parent_id is not None:
            # adjust target_index
            if target_index is None:
                target_index = 0 if self.config['new_at_top'] else float('inf')
            target_index = min(target_index, len(self.toc.get(target_parent_id, ())))

            self.toc.setdefault(target_parent_id, [])[target_index:target_index] = rv

        return rv

    def _add_item(self, meta):
        # prepare new item meta
        item = self.DEFAULT_META.copy()
        if meta is not None:
            item.update(meta)

        if item.get('id') is None:
            # use the same base timestamp for id and create
            item_id = _id_now()
            item['id'] = self.get_unique_id(item_id)
            if item.get('create') is None:
                item['create'] = item_id
        elif item.get('create') is None:
            item['create'] = _id_now()

        if item.get('modify') is None:
            item['modify'] = item['create']

        # remove None keys
        for key in tuple(item):
            if item[key] is None:
                del item[key]

        # add to meta
        self.meta[item['id']] = item

        # remove ID field
        item_id = item.pop('id')

        return item_id

    def update_item(self, item, auto_modify=True):
        """Singular version shortcut of update_items()."""
        return self.update_items((item,), auto_modify=auto_modify)

    def update_items(self, items, auto_modify=True):
        """Update items.

        Args:
            items: an iterable of dict with item properties
            auto_modify: automatically update the 'modify' property (overwrites
                the property value of the provided item)

        Returns:
            dict: ID and meta of the updated items

        Raises:
            ValueError: if the item ID is not specified, the provided item
                does not exist, etc.
        """
        # prepare items to handle
        tasks = {}
        for item in items:
            try:
                item_id = item['id']
            except KeyError:
                raise ValueError(f'Item ID not specified: {item!r}')

            if item_id not in self.meta:
                raise ValueError(f'Item not exist: {item_id!r}')

            # Prevent handling the same item again.
            if item_id in tasks:
                continue

            tasks[item_id] = item

        # perform the tasks
        if auto_modify:
            modify_ts = _id_now()

        rv = {}
        for item_id, item in tasks.items():
            # update meta
            self.meta[item_id].update(item)

            # update modify
            if auto_modify:
                self.meta[item_id]['modify'] = modify_ts

            # remove ID field
            del self.meta[item_id]['id']

            rv[item_id] = self.meta[item_id]

        return rv

    def move_item(self, current_parent_id, current_index,
                  target_parent_id, target_index=None):
        """Singular version shortcut of move_items()."""
        return self.move_items(((current_parent_id, current_index),),
                               target_parent_id, target_index)

    def move_items(self, items, target_parent_id, target_index=None):
        """Move items.

        Args:
            items: an iterable of tuple (current_parent_id, current_index) in
                tree order
            target_parent_id: the parent to insert at
            target_index: the position to insert at, or None to append to last

        Returns:
            int: index that the items are inserted at

        Raises:
            ValueError: if the item does not exist, the target parent does not
                exist, the target index is invalid, etc.
        """
        if not (target_parent_id in self.meta or target_parent_id in self.SPECIAL_ITEM_ID):
            raise ValueError(f'Invalid target parent ID: {target_parent_id!r}')

        if not (target_index is None or target_index >= 0):
            raise ValueError(f'Invalid target index: {target_index!r}')

        # adjust target_index
        if target_index is None:
            target_index = 0 if self.config['new_at_top'] else float('inf')
        target_index = min(target_index, len(self.toc.get(target_parent_id, ())))

        # prepare items to handle
        tasks = {}
        for current_parent_id, current_index in items:
            if not (current_index >= 0):
                raise ValueError(f'Invalid item index: {current_index!r}')

            try:
                item_id = self.toc[current_parent_id][current_index]
            except (KeyError, IndexError):
                raise ValueError(
                    f'Item not exist: {current_parent_id!r}[{current_index!r}]'
                ) from None

            item = (item_id, current_parent_id, current_index)

            # Prevent handling the same item again, which may happen when the
            # user selects a recursive tree.
            #
            # For example:
            #
            #     root
            #       item1
            #         item2
            #           item1
            #             item2
            #
            # In this case the user may select:
            #
            #     [('root', 0) ('item1', 0), ('item2', 0), ('item1', 0)]
            #
            # and the last item should be ignored.
            #
            if item in tasks:
                continue

            # Silently ignore moving into a descendant as it will become
            # non-reachable (unless move within the same parent).
            if (target_parent_id in self.get_reachable_items(item_id)
                    and current_parent_id != target_parent_id):
                continue

            tasks[item] = True

        # perform the tasks
        if tasks:
            try:
                it = reversed(tasks)
            except TypeError:
                # Python 3.7 does not support dict reverse
                it = reversed(tuple(tasks))

            for _, current_parent_id, current_index in it:
                # remove from parent TOC
                del self.toc[current_parent_id][current_index]
                if not self.toc[current_parent_id]:
                    del self.toc[current_parent_id]

                # fix when moving within the same parent
                if current_parent_id == target_parent_id and current_index < target_index:
                    target_index -= 1

            self.toc.setdefault(target_parent_id, [])[target_index:target_index] = (
                item_id for item_id, _, _ in tasks
            )

        return target_index

    def link_item(self, current_parent_id, current_index,
                  target_parent_id, target_index=None):
        """Singular version shortcut of link_items()."""
        return self.link_items(((current_parent_id, current_index),),
                               target_parent_id, target_index)

    def link_items(self, items, target_parent_id, target_index=None):
        """Create links for items.

        Args:
            items: an iterable of tuple (current_parent_id, current_index) in
                tree order
            target_parent_id: the parent to insert at
            target_index: the position to insert at, or None to append to last

        Returns:
            int: index that the items are inserted at

        Raises:
            ValueError: if the item does not exist, the target parent does not
                exist, the target index is invalid, etc.
        """
        if not (target_parent_id in self.meta or target_parent_id in self.SPECIAL_ITEM_ID):
            raise ValueError(f'Invalid target parent ID: {target_parent_id!r}')

        if not (target_index is None or target_index >= 0):
            raise ValueError(f'Invalid target index: {target_index!r}')

        # adjust target_index
        if target_index is None:
            target_index = 0 if self.config['new_at_top'] else float('inf')
        target_index = min(target_index, len(self.toc.get(target_parent_id, ())))

        # prepare items to handle
        tasks = {}
        for current_parent_id, current_index in items:
            if not (current_index >= 0):
                raise ValueError(f'Invalid item index: {current_index!r}')

            try:
                item_id = self.toc[current_parent_id][current_index]
            except (KeyError, IndexError):
                raise ValueError(
                    f'Item not exist: {current_parent_id!r}[{current_index!r}]'
                ) from None

            item = (item_id, current_parent_id, current_index)

            # Prevent handling the same item again, as move_items().
            if item in tasks:
                continue

            tasks[item] = True

        # perform the tasks
        if tasks:
            self.toc.setdefault(target_parent_id, [])[target_index:target_index] = (
                item_id for item_id, _, _ in tasks
            )

        return target_index

    def copy_item(self, current_parent_id, current_index,
                  target_parent_id, target_index=None, *,
                  target_book_id=None, recursively=True):
        """Singular version shortcut of copy_items()."""
        return self.copy_items(((current_parent_id, current_index),),
                               target_parent_id, target_index,
                               target_book_id=target_book_id,
                               recursively=recursively,
                               )

    def copy_items(self, items, target_parent_id, target_index=None, *,
                   target_book_id=None, recursively=True):
        """Copy items.

        Args:
            items: an iterable of tuple (current_parent_id, current_index) in
                tree order
            target_parent_id: the parent to insert at
            target_index: the position to insert at, or None to append to last
            target_book_id: the ID of the scrapbook copy to
            recursively: also copy descendant items

        Returns:
            int: index that the items are inserted at
            str: ID of the target book
            list: ID of the generated items

        Raises:
            ValueError: if the item does not exist, the target parent does not
                exist, the target index is invalid, etc.
        """
        if target_book_id is None:
            target_book_id = self.id

        if target_book_id == self.id:
            target_book = self
        else:
            try:
                target_book = self.host.books[target_book_id]
            except KeyError:
                raise ValueError(f'Invalid target book ID: {target_book_id!r}')

            target_book.load_meta_files()
            target_book.load_toc_files()

        if not (target_parent_id in target_book.meta or target_parent_id in self.SPECIAL_ITEM_ID):
            raise ValueError(f'Invalid target parent ID: {target_parent_id!r}')

        if not (target_index is None or target_index >= 0):
            raise ValueError(f'Invalid target index: {target_index!r}')

        # adjust target_index
        if target_index is None:
            target_index = 0 if target_book.config['new_at_top'] else float('inf')
        target_index = min(target_index, len(target_book.toc.get(target_parent_id, ())))

        # prepare items to handle
        tasks = {}
        for current_parent_id, current_index in items:
            if not (current_index >= 0):
                raise ValueError(f'Invalid item index: {current_index!r}')

            try:
                item_id = self.toc[current_parent_id][current_index]
            except (KeyError, IndexError):
                raise ValueError(
                    f'Item not exist: {current_parent_id!r}[{current_index!r}]'
                ) from None

            if item_id not in self.meta:
                raise ValueError(f'Item not exist: {item_id!r}')

            item = (item_id, current_parent_id, current_index)

            # Prevent handling the same item again, as move_items().
            if item in tasks:
                continue

            tasks[item] = True

        # perform the tasks
        _target_index = target_index
        id_map = {}
        for item_id, _, _ in tasks:
            self._copy_item_tree(item_id, target_parent_id, _target_index, target_book,
                                 recursively, id_map)
            _target_index += 1

        return target_index, target_book_id, [v for v in id_map.values() if v]

    def _copy_item_tree(self, item_id, target_parent_id, target_index, target_book,
                        recursively, id_map):
        try:
            _item_id = id_map[item_id]
        except KeyError:
            pass
        else:
            if _item_id is not None:
                # already copied, simply link to the copy
                target_book.toc.setdefault(target_parent_id, []).insert(target_index, _item_id)
                return
            else:
                # an added copy, ignore it to prevent an infinite loop
                return

        new_item_id = self._copy_item_data(item_id, target_parent_id, target_index, target_book,
                                           id_map)

        if recursively:
            for i, child_item_id in enumerate(self.toc.get(item_id, ())):
                self._copy_item_tree(child_item_id, new_item_id, i, target_book,
                                     recursively, id_map)

    def _copy_item_data(self, item_id, target_parent_id, target_index, target_book,
                        id_map):
        try:
            item = self.meta[item_id]
        except KeyError:
            return

        # add new item and get its ID
        _item = item if item_id in target_book.meta else {**item, 'id': item_id}
        new_item_id = next(iter(target_book.add_item(_item, target_parent_id, target_index)))
        new_item = target_book.meta[new_item_id]

        # add to map
        id_map[item_id] = new_item_id
        if new_item_id != item_id and target_book.id == self.id:
            id_map[new_item_id] = None

        # copy data files
        if item.get('index'):
            if item['index'].endswith('/index.html'):
                old_index = item['index'][:-len('/index.html')]
                new_index = util.validate_filename(new_item_id)
                new_item['index'] = f'{new_index}/index.html'
            else:
                old_index = item['index']
                new_index = util.validate_filename(new_item_id) + os.path.splitext(old_index)[1]
                new_item['index'] = new_index

            old_index_file = os.path.normpath(os.path.join(self.data_dir, old_index))
            new_index_file = os.path.normpath(os.path.join(target_book.data_dir, new_index))
            if os.path.lexists(old_index_file):
                util.fs.copy(old_index_file, new_index_file)

        # copy cached favicon
        if target_book.id != self.id:
            for _ in range(1):
                old_icon_file = self.get_icon_file(item)
                if not old_icon_file:
                    break

                favicon_dir = os.path.join(self.tree_dir, 'favicon', '')
                if not os.path.normcase(old_icon_file).startswith(os.path.normcase(favicon_dir)):
                    break

                try:
                    new_base = os.path.dirname(new_index_file)
                except UnboundLocalError:
                    new_base = target_book.data_dir
                new_icon_file = os.path.join(target_book.tree_dir, 'favicon', os.path.basename(old_icon_file))
                new_item['icon'] = pathname2url(os.path.relpath(new_icon_file, new_base))
                if os.path.lexists(old_icon_file) and not os.path.lexists(new_icon_file):
                    util.fs.copy(old_icon_file, new_icon_file)

        return new_item_id

    def recycle_item(self, current_parent_id, current_index):
        """Singular version shortcut of recycle_items()."""
        return self.recycle_items(((current_parent_id, current_index),))

    def recycle_items(self, items):
        """Move items to the recycle bin and set metadata.

        Args:
            items: an iterable of tuple (current_parent_id, current_index) in
                tree order

        Returns:
            dict: ID and original parent ID of the recycled items

        Raises:
            ValueError: if the item does not exist
        """
        # prepare items to handle
        tasks = {}
        for current_parent_id, current_index in items:
            if not (current_index >= 0):
                raise ValueError(f'Invalid item index: {current_index!r}')

            try:
                item_id = self.toc[current_parent_id][current_index]
            except (KeyError, IndexError):
                raise ValueError(
                    f'Item not exist: {current_parent_id!r}[{current_index!r}]'
                ) from None

            if item_id not in self.meta:
                raise ValueError(f'Item not exist: {item_id!r}')

            item = (item_id, current_parent_id, current_index)

            # Prevent handling the same item again, as move_items().
            if item in tasks:
                continue

            tasks[item] = True

        # perform the tasks
        recycle_ts = _id_now()

        try:
            it = reversed(tasks)
        except TypeError:
            # Python 3.7 does not support dict reverse
            it = reversed(tuple(tasks))

        for _, current_parent_id, current_index in it:
            # remove from parent TOC
            del self.toc[current_parent_id][current_index]
            if not self.toc[current_parent_id]:
                del self.toc[current_parent_id]

        # handle unreachable items
        reachable_items = self.get_reachable_items()

        recycled = {}
        for item_id, current_parent_id, _ in tasks:
            if item_id not in reachable_items and item_id not in recycled:
                recycled[item_id] = current_parent_id
                self.meta[item_id]['parent'] = current_parent_id
                self.meta[item_id]['recycled'] = recycle_ts

        if recycled:
            target_parent_id = self.RECYCLE_ITEM_ID
            target_index = 0 if self.config['new_at_top'] else len(self.toc.get(target_parent_id, ()))
            self.toc.setdefault(target_parent_id, [])[target_index:target_index] = recycled

        return recycled

    def unrecycle_item(self, current_parent_id, current_index):
        """Singular version shortcut of unrecycle_items()."""
        return self.unrecycle_items(((current_parent_id, current_index),))

    def unrecycle_items(self, items):
        """Move items from the recycle bin to the original parent.

        Args:
            items: an iterable of tuple (current_parent_id, current_index) in
                tree order

        Returns:
            dict: ID and parent ID of the unrecycled items

        Raises:
            ValueError: if the item does not exist
        """
        # prepare items to handle
        tasks = {}
        for current_parent_id, current_index in items:
            if not (current_index >= 0):
                raise ValueError(f'Invalid item index: {current_index!r}')

            try:
                item_id = self.toc[current_parent_id][current_index]
            except (KeyError, IndexError):
                raise ValueError(
                    f'Item not exist: {current_parent_id!r}[{current_index!r}]'
                ) from None

            if item_id not in self.meta:
                raise ValueError(f'Item not exist: {item_id!r}')

            item = (item_id, current_parent_id, current_index)

            # Prevent handling the same item again, as move_items().
            if item in tasks:
                continue

            tasks[item] = True

        # perform the tasks
        try:
            it = reversed(tasks)
        except TypeError:
            # Python 3.7 does not support dict reverse
            it = reversed(tuple(tasks))

        for _, current_parent_id, current_index in it:
            # remove from parent TOC
            del self.toc[current_parent_id][current_index]
            if not self.toc[current_parent_id]:
                del self.toc[current_parent_id]

        unrecycled = {}
        for item_id, _, _ in tasks:
            # Ignore the duplicated entry in case multiple entries of item_id
            # is seen (which should generally not happen).
            if item_id in unrecycled:
                continue

            try:
                target_parent_id = self.meta[item_id].pop('parent')
            except KeyError:
                target_parent_id = self.ROOT_ITEM_ID

            try:
                del self.meta[item_id]['recycled']
            except KeyError:
                pass

            # insert to root instead if the original parent no more exists
            if not (target_parent_id in self.meta or target_parent_id in self.SPECIAL_ITEM_ID):
                target_parent_id = self.ROOT_ITEM_ID

            # record target in the map
            unrecycled[item_id] = target_parent_id

        if unrecycled:
            map_parent_items = {}
            for item_id, target_parent_id in unrecycled.items():
                map_parent_items.setdefault(target_parent_id, []).append(item_id)

            for target_parent_id, item_ids in map_parent_items.items():
                target_index = 0 if self.config['new_at_top'] else len(self.toc.get(target_parent_id, ()))
                self.toc.setdefault(target_parent_id, [])[target_index:target_index] = item_ids

        return unrecycled

    def delete_item(self, current_parent_id, current_index):
        """Singular version shortcut of delete_items()."""
        return self.delete_items(((current_parent_id, current_index),))

    def delete_items(self, items):
        """Delete items and purge their data files.

        Args:
            items: an iterable of tuple (current_parent_id, current_index) in
                tree order

        Returns:
            list: ID of the deleted items

        Raises:
            ValueError: if the item does not exist
        """
        # prepare items to handle
        tasks = {}
        for current_parent_id, current_index in items:
            if not (current_index >= 0):
                raise ValueError(f'Invalid item index: {current_index!r}')

            try:
                item_id = self.toc[current_parent_id][current_index]
            except (KeyError, IndexError):
                raise ValueError(
                    f'Item not exist: {current_parent_id!r}[{current_index!r}]'
                ) from None

            item = (item_id, current_parent_id, current_index)

            # Prevent handling the same item again, as move_items().
            if item in tasks:
                continue

            tasks[item] = True

        # perform the tasks
        old_reachable_items = self.get_reachable_items()

        try:
            it = reversed(tasks)
        except TypeError:
            # Python 3.7 does not support dict reverse
            it = reversed(tuple(tasks))

        for _, current_parent_id, current_index in it:
            # remove from parent TOC
            del self.toc[current_parent_id][current_index]
            if not self.toc[current_parent_id]:
                del self.toc[current_parent_id]

        reachable_items = self.get_reachable_items()

        deleted = {item_id: True for item_id in old_reachable_items if item_id not in reachable_items}
        for item_id in deleted:
            index = self.meta.get(item_id, {}).get('index')
            if index:
                if index.endswith('/index.html'):
                    index = index[:-len('/index.html')]
                entry = os.path.join(self.data_dir, index)

                # silently pass if index file does not exist
                if os.path.lexists(entry):
                    util.fs.delete(entry)

            try:
                del self.meta[item_id]
            except KeyError:
                pass

            try:
                del self.toc[item_id]
            except KeyError:
                pass

        return list(deleted)

    def sort_item(self, item_id, key=None, reverse=False, recursively=False):
        return self.sort_items((item_id,), key, reverse, recursively)

    def sort_items(self, items, key=None, reverse=False, recursively=False):
        """Sort given items.

        Args:
            items: an iterable of container item_id in tree order
            key: the key to sort, which can be 'reverse', 'type', 'title',
                'index', 'source', 'create', 'modify', or 'marked'
            reverse: sort in reverse order
            recursively: also sort items in all descendant items

        Raises:
            ValueError: if the item does not exist
        """
        if recursively:
            item_ids = self.get_reachable_items(items)
        else:
            item_ids = items

        for item_id in item_ids:
            self._sort_item(item_id, key, reverse)

    def _sort_item(self, item_id, key, reverse):
        try:
            toc = self.toc[item_id]
        except KeyError:
            # no toc to sort
            return

        if key == 'reverse':
            toc.reverse()
        elif key == 'id':
            toc.sort(reverse=reverse)
        else:
            try:
                keyfunc = getattr(self, f'_sort_items_keyfunc_{key}')
            except AttributeError:
                raise ValueError(f'Unknown sort key: {key!r}')
            toc.sort(key=keyfunc, reverse=reverse)

    _sort_items_map_type_value = {
        'folder': -1,
        'bookmark': 1,
        'postit': 2,
        'note': 3,
    }

    def _sort_items_keyfunc_type(self, item_id):
        type = self.meta.get(item_id, {}).get('type')
        try:
            value = self._sort_items_map_type_value[type]
        except KeyError:
            value = 0
        return value

    def _sort_items_keyfunc_title(self, item_id):
        return self.meta.get(item_id, {}).get('title', '')

    def _sort_items_keyfunc_index(self, item_id):
        return self.meta.get(item_id, {}).get('index', '')

    def _sort_items_keyfunc_source(self, item_id):
        return self.meta.get(item_id, {}).get('source', '')

    def _sort_items_keyfunc_create(self, item_id):
        return self.meta.get(item_id, {}).get('create', '')

    def _sort_items_keyfunc_modify(self, item_id):
        return self.meta.get(item_id, {}).get('modify', '')

    def _sort_items_keyfunc_marked(self, item_id):
        return bool(self.meta.get(item_id, {}).get('marked'))

    def load_item_postit(self, item_id):
        """Get content of a postit item.

        Args:
            item_id: ID of the postit item

        Returns:
            str: content of the postit item

        Raises:
            ValueError: if the provided item does not exist, item is not a
                postit, item index missing, etc.
        """
        try:
            item = self.meta[item_id]
        except KeyError:
            raise ValueError(f'Item not exist: {item_id!r}') from None

        if item.get('type') != 'postit':
            raise ValueError(f'Item is not a postit: {item_id!r}')

        index = item.get('index')
        if not index:
            raise ValueError(f'Item index missing: {item_id!r}')

        index_file = os.path.join(self.data_dir, index)

        if not os.path.lexists(index_file):
            return ''

        return html.unescape(self.load_postit_file(index_file))

    def save_item_postit(self, item_id, content, auto_modify=True):
        """Save content for a postit item.

        Args:
            item_id: ID of the postit item
            content: new content to save
            auto_modify: automatically update the 'modify' property

        Returns:
            dict: ID and updated meta of the saved postit item

        Raises:
            ValueError: if the provided item does not exist, item is not a
                postit, item index missing, etc.
        """
        try:
            item = self.meta[item_id]
        except KeyError:
            raise ValueError(f'Item not exist: {item_id!r}') from None

        if item.get('type') != 'postit':
            raise ValueError(f'Item is not a postit: {item_id!r}')

        index = item.get('index')
        if not index:
            raise ValueError(f'Item index missing: {item_id!r}')

        index_file = os.path.join(self.data_dir, index)

        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        self.save_postit_file(index_file, html.escape(content, False))

        item['title'] = re.sub(r'\n[\s\S]*$', '', content, flags=re.M)

        if auto_modify:
            item['modify'] = _id_now()

        return {item_id: item}

    def add_item_subpage(self, item_id, title=None, ext='.html', base=None):
        """Generate a subpage for an item.

        Args:
            item_id: ID of the item
            title: title of the subpage, or None for index
            ext: file extension of the subpage ('.html' or '.md')
            base: base file (from data dir) to create the subpage, or None to
                be relative to item index

        Returns:
            str: ID of the item

        Raises:
            ValueError: if the provided item does not exist, item index
                missing, item is single-file, file already exists, etc.
        """
        try:
            item = self.meta[item_id]
        except KeyError:
            raise ValueError(f'Item not exist: {item_id!r}') from None

        index = item.get('index')
        if not index:
            raise ValueError(f'Item index missing: {item_id!r}')

        if not index.endswith('/index.html'):
            raise ValueError(f"Index page is not '*/index.html': {item_id!r}")

        item_dir = os.path.normpath(os.path.join(self.data_dir, os.path.dirname(index)))

        if base is None:
            base = index
        base_dir = os.path.normpath(os.path.dirname(os.path.join(self.data_dir, base)))

        if not os.path.normcase(base_dir).startswith(os.path.normcase(os.path.join(self.data_dir, ''))):
            raise ValueError(f'base not under data directory: {base!r}')

        dst = util.validate_filename(('index' if title is None else title) + ext)
        dst = os.path.join(base_dir, dst)

        if os.path.lexists(dst):
            raise ValueError(f'Page already exists: {self.get_subpath(dst)!r}')

        try:
            tpl = self.get_template(item.get('type', ''), ext)
        except ValueError:
            data = ''
        else:
            data = util.format_string(tpl, {
                'NOTE_TITLE': html.escape(item.get('title', '') if title is None else title),
                'SCRAPBOOK_DIR': html.escape(util.get_relative_url(self.top_dir, dst, start_is_dir=False)),
                'TREE_DIR': html.escape(util.get_relative_url(self.tree_dir, dst, start_is_dir=False)),
                'DATA_DIR': html.escape(util.get_relative_url(self.data_dir, dst, start_is_dir=False)),
                'ITEM_DIR': html.escape(util.get_relative_url(item_dir, dst, start_is_dir=False)),
            })

        util.fs.save(dst, data.encode('UTF-8'))

        return item_id
