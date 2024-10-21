import json
import os
import time
import traceback
from collections import OrderedDict
from contextlib import nullcontext
from datetime import timedelta

from .. import util
from .._polyfill import mimetypes, zipfile
from ..util import Info
from .book import _id_now
from .host import Host

EXPORTER_VERSION = 2

SCHEME_ITEM_IDS = 0
SCHEME_ROOT_INDEXES = 1


class Exporter():
    """Main class for generating exports."""
    def __init__(self, output, book, *, scheme=SCHEME_ITEM_IDS, singleton=False, stream=None):
        self.output = output
        self.book = book
        self.scheme = scheme
        self.singleton = singleton
        self.stream = stream

    def run(self, items=None, recursive=False):
        self.book.load_meta_files()
        self.book.load_toc_files()

        self.used_ts = set()
        self.map_id_to_eid = {}

        if isinstance(self.output, zipfile.ZipFile):
            cm = nullcontext(self.output)
        else:
            cm = zipfile.ZipFile(self.output, 'w')

        with cm as self._zh:
            if self.scheme == SCHEME_ITEM_IDS:
                yield from self._export_from_item_ids(items, recursive)
            elif self.scheme == SCHEME_ROOT_INDEXES:
                yield from self._export_from_root_indexes(items, recursive)
            else:
                raise ValueError(f'Unknown items scheme: {self.scheme!r}')

        if self.stream is not None:
            yield Info('debug', 'Streaming...', self.stream.get())

    def _export_from_item_ids(self, items, recursive):
        id_pool = set(self.book.meta)
        if items:
            # add descendant id if recursive mode
            if recursive:
                items = self.book.get_reachable_items(items)

            id_pool.intersection_update(items)
        else:
            # exclude recycled items by default
            dict_ = self.book.get_reachable_items(self.book.RECYCLE_ITEM_ID)
            id_pool.difference_update(dict_)

        parent_ids = OrderedDict()
        for root in self.book.SPECIAL_ITEM_ID:
            for i, id in self._enum_child_items(root, parent_ids):
                if id in id_pool:
                    yield from self._export_item(i, id, parent_ids)

    def _export_from_root_indexes(self, items, recursive):
        pool = set()
        for item in items:
            root_id, *indexes = item

            # skip invalid item
            if not indexes:
                continue

            # deduplicate
            key = tuple(item)
            if key in pool:
                continue
            pool.add(key)

            item_id = root_id
            parent_ids = []
            for index in indexes:
                parent_ids.append(item_id)
                item_id = self.book.toc[item_id][index]

            yield from self._export_item(index, item_id, parent_ids)
            if recursive:
                for _index, _item_id in self._enum_child_items2(item_id, parent_ids, indexes):
                    # deduplicate
                    key = (root_id, *indexes)
                    if key in pool:
                        continue
                    pool.add(key)

                    yield from self._export_item(_index, _item_id, parent_ids)

    def _enum_child_items(self, id, parent_ids):
        """Generate descendant items for the item of id."""
        # do not export a circular descendant
        if id in parent_ids:
            return

        parent_ids[id] = True
        for i, child_id in enumerate(self.book.toc.get(id, ())):
            yield i, child_id
            yield from self._enum_child_items(child_id, parent_ids)
        parent_ids.popitem()

    def _enum_child_items2(self, id, parent_ids, indexes):
        """Generate descendant items for the item of id."""
        # do not export a circular descendant
        if id in parent_ids:
            return

        parent_ids.append(id)
        for i, child_id in enumerate(self.book.toc.get(id, ())):
            indexes.append(i)
            yield i, child_id
            yield from self._enum_child_items2(child_id, parent_ids, indexes)
            indexes.pop()
        parent_ids.pop()

    def _export_item(self, pos, id, parent_ids):
        if id in self.map_id_to_eid:
            if self.singleton:
                yield Info('debug', f'Skipped exporting item {id!r} (singleton mode)')
                return

        yield Info('debug', f'Exporting item {id!r}')
        try:
            yield from self._export_item_internal(pos, id, parent_ids)
        except Exception as exc:
            # unexpected error
            traceback.print_exc()
            yield Info('error', f'Failed to export {id!r}: {exc}', exc=exc)

    def _export_item_internal(self, pos, id, parent_ids):
        meta = self.book.meta[id]
        index = meta.get('index', '')

        # generate a unique timestamp as prefix
        ets = _id_now()
        while ets in self.used_ts:
            try:
                dt += timedelta(milliseconds=1)  # noqa: F821
            except UnboundLocalError:
                dt = util.id_to_datetime(ets)
                dt += timedelta(milliseconds=1)
            ets = util.datetime_to_id(dt)
        self.used_ts.add(ets)

        # setup an export id (eid), which is unique and is same among all
        # occurrences of the same id, to the ets of the first occurrence
        eid = self.map_id_to_eid.setdefault(id, ets)

        yield Info('info', f'Exporting {id!r} to {ets!r}')
        parents = [{'id': id, 'title': self.book.meta.get(id, {}).get('title', '')} for id in parent_ids]
        meta_data = {'id': id, **meta}
        export_data = {
            'version': EXPORTER_VERSION,
            'id': eid,
            'timestamp': ets,
            'timezone': int(util.id_to_datetime(ets).astimezone().utcoffset().total_seconds()),
            'path': parents,
            'index': pos,
        }

        zh = self._zh

        # add topdir and info files
        zh.writestr(f'{ets}/', '')
        fn = f'{ets}/meta.json'
        zh.writestr(fn, json.dumps(meta_data, ensure_ascii=False, indent=2),
                    **util.fs.zip_compression_params(mimetypes.guess_type(fn)[0]))
        fn = f'{ets}/export.json'
        zh.writestr(fn, json.dumps(export_data, ensure_ascii=False, indent=2),
                    **util.fs.zip_compression_params(mimetypes.guess_type(fn)[0]))
        if self.stream is not None:
            yield Info('debug', 'Streaming...', self.stream.get())

        # include data file(s)
        if index:
            zh.writestr(f'{ets}/data/', '')
            src = os.path.join(self.book.data_dir, os.path.dirname(index) if index.endswith('/index.html') else index)
            yield Info('debug', f'Saving data files for {id!r}: {self.book.get_subpath(src)!r}')
            gen = util.fs.zip_compress(zh, src, f'{ets}/data/{os.path.basename(src)}', stream=self.stream)
            if self.stream is not None:
                for bytes_ in gen:
                    yield Info('debug', 'Streaming...', bytes_)

        # include favicon cache
        iconfile = self.book.get_icon_file(meta)
        if not iconfile:
            return

        favicon_dir = os.path.join(self.book.tree_dir, 'favicon', '')
        if not os.path.normcase(iconfile).startswith(os.path.normcase(favicon_dir)):
            return

        zh.writestr(f'{ets}/favicon/', '')
        gen = util.fs.zip_compress(zh, iconfile, f'{ets}/favicon/{os.path.basename(iconfile)}', stream=self.stream)
        if self.stream is not None:
            for bytes_ in gen:
                yield Info('debug', 'Streaming...', bytes_)


def run(host, output, book_id='', items=None, *,
        scheme=SCHEME_ITEM_IDS, recursive=False, singleton=False, stream=None,
        lock=True):
    start = time.time()

    if isinstance(host, Host):
        pass
    elif isinstance(host, str):
        host = Host(host)
    else:
        host = Host(*host)

    # Fail for invalid book ID
    if book_id not in host.books:
        yield Info('error', f'Invalid book {book_id!r}.')
        return

    yield Info('debug', f'Loading book {book_id!r}.')

    try:
        book = host.books[book_id]

        if book.no_tree:
            yield Info('error', f'Unable to export book {book_id!r} ({book.name!r}) (no_tree).')
            return

        yield Info('info', f'Exporting from book {book_id!r} ({book.name!r}).')
        lh = book.get_tree_lock(persist=lock).acquire() if lock else nullcontext()
        with lh:
            generator = Exporter(output, book, scheme=scheme, singleton=singleton, stream=stream)
            yield from generator.run(items, recursive)

    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    yield Info('info', '----------------------------------------------------------------------')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
