"""Generator of integrity check for scrapbook data.
"""
import os
import traceback
import zipfile
import time
import copy
from urllib.parse import urlsplit, unquote
from datetime import datetime

from .. import WSB_DIR
from .host import Host
from .book import TreeFileError, Book
from .indexer import Indexer, FavIconCacher
from .indexer import generate_item_create, generate_item_modify
from .. import util
from ..util import Info
from .._compat.contextlib import nullcontext


# threshold (in seconds) to report file mtime newer than item modify property
# more than a normal page capture delay
OLDER_MTIME_THRESHOLD = 10 * 60


class BookChecker:
    RESOLVE_METHODS = {
        'resolve_invalid_id',
        'resolve_missing_index',
        'resolve_missing_index_file',
        'resolve_missing_date',
        'resolve_older_mtime',
        'resolve_toc_unreachable',
        'resolve_toc_invalid',
        'resolve_toc_empty_subtree',
        'resolve_unindexed_files',
        'resolve_absolute_icon',
        'resolve_unused_icon',
        }

    def __init__(self, book, resolve_all=False, **kwargs):
        self.book = book

        # init resolve* arguments
        self.resolve = False
        for k in self.RESOLVE_METHODS:
            if not resolve_all:
                v = kwargs.get(k)
                if not v:
                    setattr(self, k, False)
                    continue
            setattr(self, k, True)
            self.resolve = True

        self.wsb_dir = os.path.join(book.root, WSB_DIR)

    def run(self):
        self.seen_in_toc = set()
        self.find_index_exclude = set()
        self.used_favicons = set()

        self.cnt_warns = 0
        self.cnt_errors = 0
        self.cnt_resolves = 0
        self.cnt_items = 0
        self.cnt_dirs = 0
        self.cnt_files = 0
        self.cnt_bytes = 0

        yield Info('info', 'Loading tree...')
        self._load_tree()

        book_meta_orig = copy.deepcopy(self.book.meta)
        book_toc_orig = copy.deepcopy(self.book.toc)

        yield Info('info', 'Checking metadata...')
        yield from self._check_meta()

        yield Info('info', 'Checking data files...')
        yield from self._check_data_dir()

        yield Info('info', 'Checking TOC...')
        yield from self._check_toc()
        yield from self._check_toc_empty_subtree()

        yield Info('info', 'Checking favicon cache...')
        yield from self._check_favicon_cache()

        # update files
        if self.book.meta != book_meta_orig:
            yield Info('info', 'Saving changed meta files...')
            self.book.save_meta_files()

        if self.book.toc != book_toc_orig:
            yield Info('info', 'Saving changed TOC files...')
            self.book.save_toc_files()

        yield Info('info', f'Totally {self.cnt_items} items, {self.cnt_dirs} folders, '
            f'{self.cnt_files} files, {util.format_filesize(self.cnt_bytes)}.')

        if self.resolve and (self.cnt_errors + self.cnt_warns > 0):
            yield Info('info', f'Found {self.cnt_errors} errors, {self.cnt_warns} warnings. (Resolved {self.cnt_resolves})')
        else:
            yield Info('info', f'Found {self.cnt_errors} errors, {self.cnt_warns} warnings.')

    def _load_tree(self):
        try:
            self.book.load_meta_files()
        except TreeFileError as exc:
            raise RuntimeError(f'Malformed meta file '
                f'"{self.book.get_subpath(exc.filename)}": {exc}') from exc
        except OSError as exc:
            raise RuntimeError(f'Failed to load meta file "{self.book.get_subpath(exc.filename)}": {exc.strerror}') from exc

        try:
            self.book.load_toc_files()
        except TreeFileError as exc:
            raise RuntimeError(f'Malformed TOC file '
                f'"{self.book.get_subpath(exc.filename)}": {exc}') from exc
        except OSError as exc:
            raise RuntimeError(f'Failed to load TOC file "{self.book.get_subpath(exc.filename)}": {exc.strerror}') from exc

    def _check_meta(self):
        items_invalid_id = {}
        items_missing_index = {}
        items_missing_index_file = {}
        items_missing_date = {}
        items_older_mtime = {}
        items_absolute_icon = {}

        for id, meta in self.book.meta.items():
            if meta is None:
                continue

            yield Info('debug', f'Checking item meta for "{id}"')

            # id
            if id in Book.SPECIAL_ITEM_ID:
                yield Info('error', f'"{id}": invalid ID (special item)')
                self.cnt_errors += 1
                items_invalid_id[id] = True

            # type
            type = meta.get('type', '')

            # index
            index = meta.get('index', '')
            index_file = None
            if index:
                file = os.path.join(self.book.data_dir, index)
                if os.path.isfile(file):
                    index_file = file
                    yield from self._check_index_file(id, index, file)
                else:
                    yield Info('error', f'"{id}": missing index file "{self.book.get_subpath(file)}"')
                    self.cnt_errors += 1
                    items_missing_index_file[id] = True

                if type in {'folder', 'separator'}:
                    yield Info('warn', f'"{id}": a {type} item should not have an index file.')
                    self.cnt_warns += 1
                elif type == 'bookmark' and not index.lower().endswith('.htm'):
                    yield Info('warn', f'"{id}": a bookmark item should use "*.htm" as index file.')
                    self.cnt_warns += 1
            else:
                if type not in Book.ITEM_TYPES_WITH_OPTIONAL_INDEX:
                    yield Info('error', f'"{id}": missing "index" property.')
                    self.cnt_errors += 1
                    items_missing_index[id] = True

            # icon
            icon = meta.get('icon')
            if icon:
                icon_parts = urlsplit(icon)
                if icon_parts.scheme:
                    yield Info('warn', f'"{id}": icon "{util.crop(icon, 256)}" is an absolute URL')
                    self.cnt_warns += 1
                    items_absolute_icon[id] = True
                elif icon_parts.netloc:
                    yield Info('error', f'"{id}": icon "{util.crop(icon, 256)}" is a protocol-relative URL')
                    self.cnt_errors += 1
                elif icon_parts.path.startswith('/'):
                    yield Info('error', f'"{id}": icon "{util.crop(icon, 256)}" is a root-relative URL')
                    self.cnt_errors += 1
                else:
                    yield from self._check_favicon_file(id, meta)

            # create
            create = meta.get('create')
            if not create:
                yield Info('error', f'"{id}": missing "create" property.')
                self.cnt_errors += 1
                items_missing_date[id] = True

            # modify
            modify = meta.get('modify')
            if not modify:
                yield Info('error', f'"{id}": missing "modify" property.')
                self.cnt_errors += 1
                items_missing_date[id] = True
            elif index_file:
                try:
                    ts = os.stat(index_file).st_mtime
                except OSError:
                    pass
                else:
                    dt = datetime.fromtimestamp(ts - OLDER_MTIME_THRESHOLD)
                    mtime_check = util.datetime_to_id(dt)
                    if mtime_check > modify:
                        dt = datetime.fromtimestamp(ts)
                        mtime = util.datetime_to_id(dt)
                        yield Info('warn', f'"{id}": "modify" property ({modify}) is older than last modified time of index file ({mtime}).')
                        self.cnt_warns += 1
                        items_older_mtime[id] = True

        self.cnt_items += len(self.book.meta)

        if items_invalid_id and self.resolve_invalid_id:
            yield from self._resolve_invalid_id(items_invalid_id)

        if items_missing_index and self.resolve_missing_index:
            yield from self._resolve_missing_index(items_missing_index)

        if items_missing_index_file and self.resolve_missing_index_file:
            yield from self._resolve_missing_index_file(items_missing_index_file)

        if items_missing_date and self.resolve_missing_date:
            yield from self._resolve_missing_date(items_missing_date)

        if items_older_mtime and self.resolve_older_mtime:
            yield from self._resolve_older_mtime(items_older_mtime)

        if items_absolute_icon and self.resolve_absolute_icon:
            yield from self._resolve_absolute_icon(items_absolute_icon)

    def _check_index_file(self, id, index, file):
        pf = self._get_index_path_key(file)
        if pf in self.find_index_exclude:
            yield Info('warn', f'"{id}": index file "{self.book.get_subpath(file)}" is used by another item.')
            self.cnt_warns += 1
        else:
            yield Info('debug', f'Excluding "{pf}" from index finding')
            self.find_index_exclude.add(pf)

            if index.endswith('/index.html'):
                pd = self._get_index_path_key(os.path.dirname(file))
                yield Info('debug', f'Excluding "{pd}" from index finding')
                self.find_index_exclude.add(pd)
            elif util.is_html(index):
                basename, ext = os.path.splitext(index)
                p = self._get_index_path_key(os.path.join(os.path.dirname(file), f'{basename}.files'))
                yield Info('debug', f'Excluding "{p}" from index finding')
                self.find_index_exclude.add(p)

                p = self._get_index_path_key(os.path.join(os.path.dirname(file), f'{basename}_files'))
                yield Info('debug', f'Excluding "{p}" from index finding')
                self.find_index_exclude.add(p)
            elif util.is_archive(index):
                try:
                    zh = zipfile.ZipFile(file)
                except zipfile.BadZipFile:
                    yield Info('error', f'"{id}": corrupted archive file "{self.book.get_subpath(file)}"')
                    self.cnt_errors += 1
                    return

                with zh as zh:
                    if util.is_htz(index):
                        try:
                            zh.getinfo('index.html')
                        except KeyError:
                            yield Info('error', f'"{id}": missing "index.html" in archive file "{self.book.get_subpath(file)}"')
                            self.cnt_errors += 1
                    else:
                        if not util.get_maff_pages(zh):
                            yield Info('error', f'"{id}": no valid page in archive file "{self.book.get_subpath(file)}"')
                            self.cnt_errors += 1

    def _check_favicon_file(self, id, meta):
        favicon_dir = os.path.join(self.book.tree_dir, 'favicon', '')
        file = self.book.get_icon_file(meta)
        file_ci = os.path.normcase(file)
        is_in_favicon_dir = file_ci.startswith(os.path.normcase(favicon_dir))

        if not os.path.isfile(file):
            yield Info('error', f'"{id}": missing icon file "{self.book.get_subpath(file)}"')
            self.cnt_errors += 1
            return

        if is_in_favicon_dir:
            self.used_favicons.add(file_ci)

    def _check_toc(self):
        items_unreachable = {}
        items_missing_meta = {}
        ref_items_invalid = {}

        for id, ref_ids in self.book.toc.items():
            if ref_ids is None:
                continue

            yield Info('debug', f'Checking item TOC for "{id}"')

            # missing meta
            if not self.book.meta.get(id) and id not in Book.SPECIAL_ITEM_ID:
                yield Info('error', f'"{id}": invalid ID (missing metadata entry)')
                self.cnt_errors += 1
                items_missing_meta[id] = True

            # check referenced IDs
            for ref_id in ref_ids:
                self.seen_in_toc.add(ref_id)

                # special item ID is invalid
                if ref_id in Book.SPECIAL_ITEM_ID:
                    yield Info('error', f'"{id}": invalid reference ID "{ref_id}" (special item)')
                    self.cnt_errors += 1
                    ref_items_invalid.setdefault(id, {})[ref_id] = True
                    continue

                # missing meta
                if not self.book.meta.get(ref_id):
                    yield Info('error', f'"{id}": invalid reference ID "{ref_id}" (missing metadata entry)')
                    self.cnt_errors += 1
                    ref_items_invalid.setdefault(id, {})[ref_id] = True
                    continue

        # items not reachable from TOC
        for id in self.book.meta:
            if id not in self.seen_in_toc and id not in Book.SPECIAL_ITEM_ID:
                yield Info('error', f'"{id}": not recheable from TOC.')
                self.cnt_errors += 1
                items_unreachable[id] = True

        if (items_missing_meta or ref_items_invalid) and self.resolve_toc_invalid:
            yield from self._resolve_toc_invalid(items_missing_meta, ref_items_invalid)

        if items_unreachable and self.resolve_toc_unreachable:
            yield from self._resolve_toc_unreachable(items_unreachable)

    def _check_toc_empty_subtree(self):
        # Calculate this after other TOC related issues are resolved,
        # as they might produce more empty lists.
        yield Info('debug', f'Checking empty lists in TOC...')

        items_empty_toc = {}

        for id, ref_ids in self.book.toc.items():
            if ref_ids is None:
                continue

            if not ref_ids and id != 'root':
                yield Info('warn', f'"{id}": TOC list is empty')
                self.cnt_warns += 1
                items_empty_toc[id] = True

        if items_empty_toc and self.resolve_toc_empty_subtree:
            yield from self._resolve_toc_empty_subtree(items_empty_toc)

    def _check_data_dir(self):
        unindexed_files = {}
        yield from self._check_data_dir_internal(self.book.data_dir, unindexed_files, find_index=True)

        if unindexed_files and self.resolve_unindexed_files:
            yield from self._resolve_unindexed_files(unindexed_files)

    def _check_data_dir_internal(self, data_dir, unindexed_files, find_index=True):
        yield Info('debug', f'Inspecting folder "{self.book.get_subpath(data_dir)}" (find_index={find_index})')

        if find_index:
            index = os.path.join(data_dir, 'index.html')
            if self._get_index_path_key(index) not in self.find_index_exclude and os.path.isfile(index):
                yield Info('warn', f'File "{self.book.get_subpath(index)}" not used as item index')
                self.cnt_warns += 1
                unindexed_files[index] = True

                yield Info('debug', f'Excluding "{self.book.get_subpath(data_dir)}" from index finding')
                find_index = False

        try:
            entries = os.scandir(data_dir)
        except FileNotFoundError:
            return
        except OSError as exc:
            yield Info('error', f'Failed to scan folder "{self.book.get_subpath(exc.filename)}": {exc.strerror}', exc=exc)
            self.cnt_errors += 1
            return

        subdirs = {}
        with entries as entries:
            for entry in entries:
                if os.path.samefile(entry, self.wsb_dir):
                    yield Info('debug', f'Skipped special "{self.book.get_subpath(entry)}"')
                    continue

                if entry.is_dir():
                    self.cnt_dirs += 1
                    subdirs.setdefault(entry, True)

                elif entry.is_file():
                    try:
                        self.cnt_bytes += entry.stat().st_size
                    except OSError as exc:
                        # e.g. a broken symlink can cause this
                        yield Info('error', f'Failed to access file "{self.book.get_subpath(exc.filename)}": {exc.strerror}', exc=exc)
                        self.cnt_errors += 1
                    else:
                        self.cnt_files += 1

                    if find_index and entry.is_file():
                        if self._get_index_path_key(entry) not in self.find_index_exclude:
                            basename, ext = os.path.splitext(entry.name.lower())
                            if ext in self.book.ITEM_INDEX_ALLOWED_EXT:
                                yield Info('warn', f'File "{self.book.get_subpath(entry)}" not used as item index')
                                self.cnt_warns += 1
                                unindexed_files[entry.path] = True

                                if util.is_html(entry.path):
                                    p = self._get_index_path_key(os.path.join(data_dir, f'{basename}.files'))
                                    yield Info('debug', f'Excluding "{p}" from index finding')
                                    self.find_index_exclude.add(p)

                                    p = self._get_index_path_key(os.path.join(data_dir, f'{basename}_files'))
                                    yield Info('debug', f'Excluding "{p}" from index finding')
                                    self.find_index_exclude.add(p)

        for entry in subdirs:
            p = self._get_index_path_key(entry)
            chk = find_index and p not in self.find_index_exclude
            yield from self._check_data_dir_internal(entry, unindexed_files, find_index=chk)

    def _check_favicon_cache(self):
        unused_icons = {}

        try:
            entries = os.scandir(os.path.join(self.book.tree_dir, 'favicon'))
        except FileNotFoundError:
            return
        except OSError as exc:
            yield Info('error', f'Failed to scan folder "{self.book.get_subpath(exc.filename)}": {exc.strerror}', exc=exc)
            self.cnt_errors += 1
            return

        with entries as entries:
            for entry in entries:
                if os.path.normcase(entry.path) not in self.used_favicons:
                    yield Info('warn', f'Unused favicon file "{self.book.get_subpath(entry)}".')
                    self.cnt_warns += 1
                    unused_icons[entry.path] = True

        if unused_icons and self.resolve_unused_icon:
            yield from self._resolve_unused_icon(unused_icons)

    def _get_index_path_key(self, path):
        return self.book.get_subpath(os.path.normcase(path))

    def _resolve_invalid_id(self, ids):
        yield Info('info', 'Removing items with invalid ID...')
        for id in ids:
            try:
                del self.book.meta[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed "{id}" from meta.')
                self.cnt_resolves += 1

    def _resolve_missing_index(self, ids):
        yield Info('info', 'Removing items missing index property...')
        for id in ids:
            try:
                del self.book.meta[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed "{id}" from meta.')
                self.cnt_resolves += 1

    def _resolve_missing_index_file(self, ids):
        yield Info('info', 'Removing items missing index file...')
        for id in ids:
            try:
                del self.book.meta[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed "{id}" from meta.')
                self.cnt_resolves += 1

    def _resolve_missing_date(self, ids):
        yield Info('info', 'Generating missing create/modify item property...')
        for id in ids:
            try:
                item = self.book.meta[id]
            except KeyError:
                continue

            if not item.get('create'):
                create = generate_item_create(self.book, id)
                if create:
                    item['create'] = create
                    yield Info('info', f'Added "create" property for "{id}".')
                    self.cnt_resolves += 1

            if not item.get('modify'):
                modify = generate_item_modify(self.book, id)
                if modify:
                    item['modify'] = modify
                    yield Info('info', f'Added "modify" property for "{id}".')
                    self.cnt_resolves += 1

    def _resolve_older_mtime(self, ids):
        yield Info('info', 'Updating items with older modify property...')
        for id in ids:
            index = self.book.meta[id].get('index')
            if index:
                file = os.path.join(self.book.data_dir, index)
                try:
                    ts = os.stat(file).st_mtime
                except OSError:
                    pass
                else:
                    dt = datetime.fromtimestamp(ts)
                    mtime = util.datetime_to_id(dt)
                    if mtime > self.book.meta[id].get('modify'):
                        self.book.meta[id]['modify'] = mtime
                        yield Info('info', f'Updated "modify" property for "{id}".')
                        self.cnt_resolves += 1

    def _resolve_toc_invalid(self, items_missing_meta, ref_items_invalid):
        yield Info('info', 'Removing invalid items from TOC...')

        for id in items_missing_meta:
            try:
                del self.book.toc[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed "{id}" from TOC.')
                self.cnt_resolves += 1

        for id, ref_ids in ref_items_invalid.items():
            for ref_id in ref_ids:
                try:
                    self.book.toc[id].remove(ref_id)
                except (KeyError, ValueError):
                    pass
                else:
                    yield Info('info', f'Removed "{ref_id}" from the subtree of "{id}".')
                    self.cnt_resolves += 1

    def _resolve_toc_unreachable(self, ids):
        yield Info('info', 'Adding unreachable items to root TOC...')
        self.book.toc.setdefault('root', [])
        for id in ids:
            self.book.toc['root'].append(id)
            yield Info('info', f'Added "{id}" to root TOC.')
            self.cnt_resolves += 1

    def _resolve_toc_empty_subtree(self, ids):
        yield Info('info', 'Removing empty item lists from TOC...')
        for id in ids:
            try:
                del self.book.toc[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed "{id}" from TOC.')
                self.cnt_resolves += 1

    def _resolve_unindexed_files(self, files):
        yield Info('info', 'Indexing unindexed files...')
        indexer = Indexer(self.book)
        indexed = yield from indexer.run(files)

        favicon_dir = os.path.join(self.book.tree_dir, 'favicon', '')

        for id in indexed:
            # add to TOC if not seen
            if id not in self.seen_in_toc:
                self.book.toc.setdefault('root', []).append(id)
                self.seen_in_toc.add(id)

            # record added cached favicons
            index = self.book.meta[id].get('index')
            icon = self.book.meta[id].get('icon')
            file = os.path.normpath(os.path.join(self.book.data_dir, os.path.dirname(index), unquote(icon)))
            file_ci = os.path.normcase(file)
            is_in_favicon_dir = file_ci.startswith(os.path.normcase(favicon_dir))
            if is_in_favicon_dir:
                self.used_favicons.add(file_ci)

            self.cnt_resolves += 1

    def _resolve_absolute_icon(self, ids):
        yield Info('info', 'Caching favicons with absolute URL...')
        generator = FavIconCacher(self.book)
        cached = yield from generator.run(ids)

        for id, file in cached.items():
            self.used_favicons.add(os.path.normcase(file))
            self.cnt_resolves += 1

    def _resolve_unused_icon(self, files):
        yield Info('info', 'Removing unused favicons...')
        for file in files:
            try:
                self.book.backup(file)
                os.remove(file)
            except FileNotFoundError:
                pass
            else:
                yield Info('info', f'Removed "{self.book.get_subpath(file)}".')
                self.cnt_resolves += 1


def run(root, book_ids=None, *, config=None, no_lock=False, no_backup=False, **kwargs):
    start = time.time()

    host = Host(root, config)

    if not no_backup:
        host.init_backup(note='check')
        yield Info('info', f'Prepared backup at "{host.get_subpath(host._backup_dir)}".')

    try:
        # handle all books if none specified
        for book_id in book_ids or host.books:
            try:
                book = host.books[book_id]
            except KeyError:
                # skip invalid book ID
                yield Info('warn', f'Skipped invalid book "{book_id}".')
                continue

            yield Info('debug', f'Loading book "{book_id}"...')
            try:
                if book.no_tree:
                    yield Info('info', f'Skipped book "{book_id}" ({book.name}) (no_tree).')
                    continue

                yield Info('info', f'Checking book "{book_id}" ({book.name}).')
                lh = nullcontext() if no_lock else book.get_tree_lock().acquire()
                with lh:
                    generator = BookChecker(book, **kwargs)
                    yield from generator.run()
            except Exception as exc:
                traceback.print_exc()
                yield Info('critical', str(exc), exc=exc)
            else:
                yield Info('info', 'Done.')

            yield Info('info', '----------------------------------------------------------------------')
    finally:
        if not no_backup:
            host.init_backup(False)

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
