"""Legacy module for exporting version 1 *.wsba"""
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

EXPORTER_VERSION = 1


class Exporter():
    """Main class for generating exports."""
    def __init__(self, output, book, *, singleton=False):
        self.output = output
        self.book = book
        self.singleton = singleton

    def run(self, item_ids=None, recursive=False):
        self.book.load_meta_files()
        self.book.load_toc_files()

        os.makedirs(self.output, exist_ok=True)

        self.used_ts = set()
        self.map_id_to_eid = {}

        id_pool = set(self.book.meta)
        if item_ids:
            # add descendant id if recursive mode
            if recursive:
                item_ids = self.book.get_reachable_items(item_ids)

            id_pool.intersection_update(item_ids)
        else:
            # exclude recycled items by default
            dict_ = self.book.get_reachable_items(self.book.RECYCLE_ITEM_ID)
            id_pool.difference_update(dict_)

        parent_ids = OrderedDict()
        for root in self.book.SPECIAL_ITEM_ID:
            for id in self._iter_child_items(root, parent_ids):
                if id in id_pool:
                    yield from self._export_item(id, parent_ids)

    def _iter_child_items(self, id, parent_ids):
        """Generate descendant items for the item of id."""
        # do not export a circular descendant
        if id in parent_ids:
            return

        parent_ids[id] = True
        for child_id in self.book.toc.get(id, ()):
            yield child_id
            yield from self._iter_child_items(child_id, parent_ids)
        parent_ids.popitem()

    def _export_item(self, id, parent_ids):
        if id in self.map_id_to_eid:
            if self.singleton:
                yield Info('debug', f'Skipped exporting item {id!r} (singleton mode)')
                return

        yield Info('debug', f'Exporting item {id!r}')
        try:
            yield from self._export_item_internal(id, parent_ids)
        except Exception as exc:
            # unexpected error
            traceback.print_exc()
            yield Info('error', f'Failed to export {id!r}: {exc}', exc=exc)

    def _export_item_internal(self, id, parent_ids):
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

        # generate a unique timestamp prefix
        basename = ets + '-' + meta.get('title', meta.get('id', ''))
        basename = util.crop(util.validate_filename(basename), 128)

        # generate a unique filename
        i = 0
        dst = os.path.join(self.output, f'{basename}.wsba')
        while os.path.lexists(dst):
            i += 1
            dst = os.path.join(self.output, f'{basename}-{i}.wsba')

        yield Info('info', f'Exporting {id!r} to {os.path.basename(dst)!r}')
        parents = [{'id': id, 'title': self.book.meta.get(id, {}).get('title', '')} for id in parent_ids]
        meta_data = {'id': id, **meta}
        export_data = {
            'version': EXPORTER_VERSION,
            'id': eid,
            'timestamp': ets,
            'timezone': util.id_to_datetime(ets).astimezone().utcoffset().total_seconds(),
            'path': parents,
        }
        with zipfile.ZipFile(dst, 'w') as zh:
            fn = 'meta.json'
            zh.writestr(fn, json.dumps(meta_data, ensure_ascii=False, indent=2),
                        **util.fs.zip_compression_params(mimetypes.guess_type(fn)[0]))
            fn = 'export.json'
            zh.writestr(fn, json.dumps(export_data, ensure_ascii=False, indent=2),
                        **util.fs.zip_compression_params(mimetypes.guess_type(fn)[0]))

            # include data file(s)
            if index:
                zh.writestr('data/', '')
                src = os.path.join(self.book.data_dir, os.path.dirname(index) if index.endswith('/index.html') else index)
                yield Info('debug', f'Saving data files for {id!r}: {self.book.get_subpath(src)!r}')
                util.fs.zip_compress(zh, src, f'data/{os.path.basename(src)}')

            # include favicon cache
            iconfile = self.book.get_icon_file(meta)
            if not iconfile:
                return

            favicon_dir = os.path.join(self.book.tree_dir, 'favicon', '')
            if not os.path.normcase(iconfile).startswith(os.path.normcase(favicon_dir)):
                return

            zh.writestr('favicon/', '')
            util.fs.zip_compress(zh, iconfile, f'favicon/{os.path.basename(iconfile)}')


def run(host, output, book_id='', item_ids=None, *, recursive=False, singleton=False, lock=True):
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
            generator = Exporter(output, book, singleton=singleton)
            yield from generator.run(item_ids, recursive)

    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    yield Info('info', '----------------------------------------------------------------------')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
