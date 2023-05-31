"""Generator of integrity check for scrapbook data.
"""
import os
import time
import traceback
from contextlib import nullcontext
from datetime import datetime
from urllib.parse import unquote, urlsplit

from .. import WSB_DIR, util
from .._polyfill import zipfile
from ..util import Info
from .book import TreeFileError
from .host import Host
from .indexer import (
    SUPPORT_FOLDER_SUFFIXES,
    FavIconCacher,
    Indexer,
    generate_item_create,
    generate_item_modify,
)

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
        self.book_wsb_dir = os.path.join(book.top_dir, WSB_DIR)

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

        book_meta_orig = self.book.checksum(self.book.meta)
        book_toc_orig = self.book.checksum(self.book.toc)

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
        if self.book.checksum(self.book.meta) != book_meta_orig:
            yield Info('info', 'Saving changed meta files...')
            self.book.save_meta_files()

        if self.book.checksum(self.book.toc) != book_toc_orig:
            yield Info('info', 'Saving changed TOC files...')
            self.book.save_toc_files()

        yield Info('info',
                   f'Totally {self.cnt_items} items, {self.cnt_dirs} folders, '
                   f'{self.cnt_files} files, {util.format_filesize(self.cnt_bytes)}.')

        if self.resolve and (self.cnt_errors + self.cnt_warns > 0):
            yield Info('info',
                       f'Found {self.cnt_errors} errors, {self.cnt_warns} warnings. '
                       f'(Resolved {self.cnt_resolves})')
        else:
            yield Info('info', f'Found {self.cnt_errors} errors, {self.cnt_warns} warnings.')

    def _load_tree(self):
        try:
            self.book.load_meta_files()
        except TreeFileError as exc:
            raise RuntimeError(
                f'Malformed meta file '
                f'{self.book.get_subpath(exc.filename)!r}: {exc}'
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f'Failed to load meta file '
                f'{self.book.get_subpath(exc.filename)!r}: {exc.strerror}'
            ) from exc

        try:
            self.book.load_toc_files()
        except TreeFileError as exc:
            raise RuntimeError(
                f'Malformed TOC file '
                f'{self.book.get_subpath(exc.filename)!r}: {exc}'
            ) from exc
        except OSError as exc:
            raise RuntimeError(f'Failed to load TOC file {self.book.get_subpath(exc.filename)!r}: {exc.strerror}') from exc

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

            yield Info('debug', f'Checking item meta for {id!r}')

            # id
            if id in self.book.SPECIAL_ITEM_ID:
                yield Info('error', f'{id!r}: invalid ID (special item)')
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
                    yield Info('error', f'{id!r}: missing index file {self.book.get_subpath(file)!r}')
                    self.cnt_errors += 1
                    items_missing_index_file[id] = True

                if type in {'folder', 'separator'}:
                    yield Info('warn', f'{id!r}: a {type!r} item should not have an index file.')
                    self.cnt_warns += 1
                elif type == 'bookmark' and not index.lower().endswith('.htm'):
                    yield Info('warn', f"{id!r}: a bookmark item should use '*.htm' as index file.")
                    self.cnt_warns += 1
            else:
                if type not in self.book.ITEM_TYPES_WITH_OPTIONAL_INDEX:
                    yield Info('error', f"{id!r}: missing 'index' property.")
                    self.cnt_errors += 1
                    items_missing_index[id] = True

            # icon
            icon = meta.get('icon')
            if icon:
                icon_parts = urlsplit(icon)
                if icon_parts.scheme:
                    yield Info('warn', f'{id!r}: icon {util.crop(icon, 256)!r} is an absolute URL')
                    self.cnt_warns += 1
                    items_absolute_icon[id] = True
                elif icon_parts.netloc:
                    yield Info('error', f'{id!r}: icon {util.crop(icon, 256)!r} is a protocol-relative URL')
                    self.cnt_errors += 1
                elif icon_parts.path.startswith('/'):
                    yield Info('error', f'{id!r}: icon {util.crop(icon, 256)!r} is a root-relative URL')
                    self.cnt_errors += 1
                else:
                    yield from self._check_favicon_file(id, meta)

            # create
            create = meta.get('create')
            if not create:
                yield Info('error', f"{id!r}: missing 'create' property.")
                self.cnt_errors += 1
                items_missing_date[id] = True

            # modify
            modify = meta.get('modify')
            if not modify:
                yield Info('error', f"{id!r}: missing 'modify' property.")
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
                        yield Info('warn', f"{id!r}: 'modify' property ({modify}) is older than last modified time of index file ({mtime}).")
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
            yield Info('warn', f'{id!r}: index file {self.book.get_subpath(file)!r} is used by another item.')
            self.cnt_warns += 1
        else:
            yield Info('debug', f'Excluding {pf!r} from index finding')
            self.find_index_exclude.add(pf)

            if index.endswith('/index.html'):
                pd = self._get_index_path_key(os.path.dirname(file))
                yield Info('debug', f'Excluding {pd!r} from index finding')
                self.find_index_exclude.add(pd)
            elif util.is_html(index):
                basename, ext = os.path.splitext(index)
                for suffix in SUPPORT_FOLDER_SUFFIXES:
                    p = self._get_index_path_key(os.path.join(os.path.dirname(file), f'{basename}{suffix}'))
                    yield Info('debug', f'Excluding {p!r} from index finding')
                    self.find_index_exclude.add(p)
            elif util.is_archive(index):
                try:
                    zh = zipfile.ZipFile(file)
                except zipfile.BadZipFile:
                    yield Info('error', f'{id!r}: corrupted archive file {self.book.get_subpath(file)!r}')
                    self.cnt_errors += 1
                    return

                with zh as zh:
                    if util.is_htz(index):
                        try:
                            zh.getinfo('index.html')
                        except KeyError:
                            yield Info('error', f"{id!r}: missing 'index.html' in archive file {self.book.get_subpath(file)!r}")
                            self.cnt_errors += 1
                    else:
                        if not util.get_maff_pages(zh):
                            yield Info('error', f'{id!r}: no valid page in archive file {self.book.get_subpath(file)!r}')
                            self.cnt_errors += 1

    def _check_favicon_file(self, id, meta):
        favicon_dir = os.path.join(self.book.tree_dir, 'favicon', '')
        file = self.book.get_icon_file(meta)
        file_ci = os.path.normcase(file)
        is_in_favicon_dir = file_ci.startswith(os.path.normcase(favicon_dir))

        if not os.path.isfile(file):
            yield Info('error', f'{id!r}: missing icon file {self.book.get_subpath(file)!r}')
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

            yield Info('debug', f'Checking item TOC for {id!r}')

            # missing meta
            if not self.book.meta.get(id) and id not in self.book.SPECIAL_ITEM_ID:
                yield Info('error', f'{id!r}: invalid ID (missing metadata entry)')
                self.cnt_errors += 1
                items_missing_meta[id] = True

            # check referenced IDs
            for ref_id in ref_ids:
                self.seen_in_toc.add(ref_id)

                # special item ID is invalid
                if ref_id in self.book.SPECIAL_ITEM_ID:
                    yield Info('error', f'{id!r}: invalid reference ID {ref_id!r} (special item)')
                    self.cnt_errors += 1
                    ref_items_invalid.setdefault(id, {})[ref_id] = True
                    continue

                # missing meta
                if not self.book.meta.get(ref_id):
                    yield Info('error', f'{id!r}: invalid reference ID {ref_id!r} (missing metadata entry)')
                    self.cnt_errors += 1
                    ref_items_invalid.setdefault(id, {})[ref_id] = True
                    continue

        # items not reachable from TOC
        for id in self.book.meta:
            if id not in self.seen_in_toc and id not in self.book.SPECIAL_ITEM_ID:
                yield Info('error', f'{id!r}: not recheable from TOC.')
                self.cnt_errors += 1
                items_unreachable[id] = True

        if (items_missing_meta or ref_items_invalid) and self.resolve_toc_invalid:
            yield from self._resolve_toc_invalid(items_missing_meta, ref_items_invalid)

        if items_unreachable and self.resolve_toc_unreachable:
            yield from self._resolve_toc_unreachable(items_unreachable)

    def _check_toc_empty_subtree(self):
        # Calculate this after other TOC related issues are resolved,
        # as they might produce more empty lists.
        yield Info('debug', 'Checking empty lists in TOC...')

        items_empty_toc = {}
        for id, ref_ids in self.book.toc.items():
            if not ref_ids:
                yield Info('warn', f'{id!r}: TOC list is empty')
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
        yield Info('debug', f'Inspecting folder {self.book.get_subpath(data_dir)!r} (find_index={find_index!r})')

        if find_index:
            index = os.path.join(data_dir, 'index.html')
            if self._get_index_path_key(index) not in self.find_index_exclude and os.path.isfile(index):
                yield Info('warn', f'File {self.book.get_subpath(index)!r} not used as item index')
                self.cnt_warns += 1
                unindexed_files[index] = True

                yield Info('debug', f'Excluding {self.book.get_subpath(data_dir)!r} from index finding')
                find_index = False

        try:
            entries = os.scandir(data_dir)
        except FileNotFoundError:
            return
        except OSError as exc:
            yield Info('error', f'Failed to scan folder {self.book.get_subpath(exc.filename)!r}: {exc.strerror}', exc=exc)
            self.cnt_errors += 1
            return

        entries_to_handle = set()
        with entries as entries:
            for entry in entries:
                try:
                    assert not os.path.samefile(entry, self.wsb_dir)
                except AssertionError:
                    yield Info('debug', f'Skipped special {self.book.get_subpath(entry)!r}')
                    continue
                except OSError:
                    pass

                try:
                    assert not os.path.samefile(entry, self.book_wsb_dir)
                except AssertionError:
                    yield Info('debug', f'Skipped special {self.book.get_subpath(entry)!r}')
                    continue
                except OSError:
                    pass

                if entry.is_dir():
                    self.cnt_dirs += 1
                    entries_to_handle.add(entry)

                elif entry.is_file():
                    try:
                        self.cnt_bytes += entry.stat().st_size
                    except OSError as exc:
                        # e.g. a broken symlink can cause this
                        yield Info('error', f'Failed to access file {self.book.get_subpath(exc.filename)!r}: {exc.strerror}', exc=exc)
                        self.cnt_errors += 1
                    else:
                        self.cnt_files += 1

                    if not find_index:
                        continue

                    if self._get_index_path_key(entry) in self.find_index_exclude:
                        continue

                    basename, ext = os.path.splitext(entry.name)
                    if ext.lower() not in self.book.ITEM_INDEX_ALLOWED_EXT:
                        continue

                    entries_to_handle.add(entry)

                    if not util.is_html(entry.path):
                        continue

                    for suffix in SUPPORT_FOLDER_SUFFIXES:
                        p = self._get_index_path_key(os.path.join(data_dir, f'{basename}{suffix}'))
                        yield Info('debug', f'Excluding {p!r} from index finding')
                        self.find_index_exclude.add(p)

        for entry in sorted(entries_to_handle, key=lambda x: x.path):
            if entry.is_dir():
                p = self._get_index_path_key(entry)
                chk = find_index and p not in self.find_index_exclude
                yield from self._check_data_dir_internal(entry, unindexed_files, find_index=chk)

            elif entry.is_file():
                yield Info('warn', f'File {self.book.get_subpath(entry)!r} not used as item index')
                self.cnt_warns += 1
                unindexed_files[entry.path] = True

    def _check_favicon_cache(self):
        unused_icons = {}

        try:
            entries = os.scandir(os.path.join(self.book.tree_dir, 'favicon'))
        except FileNotFoundError:
            return
        except OSError as exc:
            yield Info('error', f'Failed to scan folder {self.book.get_subpath(exc.filename)!r}: {exc.strerror}', exc=exc)
            self.cnt_errors += 1
            return

        with entries as entries:
            for entry in entries:
                if os.path.normcase(entry.path) not in self.used_favicons:
                    yield Info('warn', f'Unused favicon file {self.book.get_subpath(entry)!r}.')
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
                yield Info('info', f'Removed {id!r} from meta.')
                self.cnt_resolves += 1

    def _resolve_missing_index(self, ids):
        yield Info('info', 'Removing items missing index property...')
        for id in ids:
            try:
                del self.book.meta[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed {id!r} from meta.')
                self.cnt_resolves += 1

    def _resolve_missing_index_file(self, ids):
        yield Info('info', 'Removing items missing index file...')
        for id in ids:
            try:
                del self.book.meta[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed {id!r} from meta.')
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
                    yield Info('info', f"Added 'create' property for {id!r}.")
                    self.cnt_resolves += 1

            if not item.get('modify'):
                modify = generate_item_modify(self.book, id)
                if modify:
                    item['modify'] = modify
                    yield Info('info', f"Added 'modify' property for {id!r}.")
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
                        yield Info('info', f"Updated 'modify' property for {id!r}.")
                        self.cnt_resolves += 1

    def _resolve_toc_invalid(self, items_missing_meta, ref_items_invalid):
        yield Info('info', 'Removing invalid items from TOC...')

        for id in items_missing_meta:
            try:
                del self.book.toc[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed {id!r} from TOC.')
                self.cnt_resolves += 1

        for id, ref_ids in ref_items_invalid.items():
            for ref_id in ref_ids:
                try:
                    self.book.toc[id].remove(ref_id)
                except (KeyError, ValueError):
                    pass
                else:
                    yield Info('info', f'Removed {ref_id!r} from the subtree of {id!r}.')
                    self.cnt_resolves += 1

    def _resolve_toc_unreachable(self, ids):
        yield Info('info', 'Adding unreachable items to root TOC...')
        toc = self.book.toc.setdefault(self.book.ROOT_ITEM_ID, [])
        for id in ids:
            toc.append(id)
            yield Info('info', f'Added {id!r} to root TOC.')
            self.cnt_resolves += 1

    def _resolve_toc_empty_subtree(self, ids):
        yield Info('info', 'Removing empty item lists from TOC...')
        for id in ids:
            try:
                del self.book.toc[id]
            except KeyError:
                pass
            else:
                yield Info('info', f'Removed {id!r} from TOC.')
                self.cnt_resolves += 1

    def _resolve_unindexed_files(self, files):
        yield Info('info', 'Indexing unindexed files...')
        indexer = Indexer(self.book)
        indexed = yield from indexer.run(files)

        favicon_dir = os.path.join(self.book.tree_dir, 'favicon', '')

        for id in indexed:
            # add to TOC if not seen
            if id not in self.seen_in_toc:
                root = self.book.ROOT_ITEM_ID
                target_index = 0 if self.book.config['new_at_top'] else len(self.book.toc.get(root, ()))
                self.book.toc.setdefault(root, []).insert(target_index, id)
                self.seen_in_toc.add(id)

            # record added cached favicons
            index = self.book.meta[id].get('index')
            icon = self.book.meta[id].get('icon')
            if icon:
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

        for _id, file in cached.items():
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
                yield Info('info', f'Removed {self.book.get_subpath(file)!r}.')
                self.cnt_resolves += 1


def run(host, book_ids=None, *, lock=True, backup=True, **kwargs):
    start = time.time()

    if isinstance(host, Host):
        pass
    elif isinstance(host, str):
        host = Host(host)
    else:
        host = Host(*host)

    if backup:
        host.init_auto_backup(note='check')
        yield Info('info', f'Prepared backup at {host.get_subpath(host._auto_backup_dir)!r}.')
        yield Info('info', '----------------------------------------------------------------------')

    try:
        # handle all books if none specified
        first = True
        for book_id in book_ids or host.books:
            if first:
                first = False
            else:
                yield Info('info', '----------------------------------------------------------------------')

            try:
                book = host.books[book_id]
            except KeyError:
                # skip invalid book ID
                yield Info('warn', f'Skipped invalid book {book_id!r}.')
                continue

            yield Info('debug', f'Loading book {book_id!r}...')

            if book.no_tree:
                yield Info('info', f'Skipped book {book_id!r} ({book.name!r}) (no_tree).')
                continue

            yield Info('info', f'Checking book {book_id!r} ({book.name!r}).')
            lh = book.get_tree_lock(persist=lock).acquire() if lock else nullcontext()
            with lh:
                generator = BookChecker(book, **kwargs)
                yield from generator.run()

            yield Info('info', 'Done.')
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    finally:
        if backup:
            host.init_auto_backup(False)

    yield Info('info', '----------------------------------------------------------------------')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
