import json
import os
import time
import traceback
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

from .. import util
from .._polyfill import mimetypes, zipfile
from ..util import Info
from .host import Host


class Exporter():
    """Main class for generating exports.
    """
    def __init__(self, output, book, *, singleton=False):
        self.output = output
        self.book = book
        self.singleton = singleton

        self.recycle = None
        self.used_ts = None
        self.map_id_to_eid = None

    def run(self, item_ids=None, recursive=False):
        book = self.book
        self.book.load_meta_files()
        self.book.load_toc_files()

        os.makedirs(self.output, exist_ok=True)

        self.recycle = set(book.toc.get('recycle', []))
        self.used_ts = set()
        self.map_id_to_eid = {}

        if item_ids:
            id_pool = {id for id in item_ids if id in book.meta and id not in self.recycle}

            # add descendant id if recursive mode
            if recursive:
                for id in list(id_pool):
                    for desc_id in self._iter_child_items(id, [id]):
                        id_pool.add(desc_id)
                        yield Info('debug', f'Included descendant item of {id!r}: {desc_id!r}')
        else:
            id_pool = {id for id in book.meta if id not in self.recycle}

        id_chain = ['root']
        for id in self._iter_child_items('root', id_chain):
            if id in id_pool:
                yield from self._export_item(id, id_chain)

        id_chain = ['hidden']
        for id in self._iter_child_items('hidden', id_chain):
            if id in id_pool:
                yield from self._export_item(id, id_chain)

    def _iter_child_items(self, id, id_chain):
        """Generate descendant items for the item of id.
        """
        for ref_id in self.book.toc.get(id, []):
            yield ref_id

            # do not export children of a circular item
            if ref_id not in id_chain:
                id_chain.append(ref_id)
                yield from self._iter_child_items(ref_id, id_chain)
                id_chain.pop()

    def _export_item(self, id, id_chain):
        if id in self.map_id_to_eid:
            if self.singleton:
                yield Info('debug', f'Skipped exporting item {id!r} (singleton mode)')
                return

        yield Info('debug', f'Exporting item {id!r}')
        try:
            yield from self._export_item_internal(id, id_chain)
        except Exception as exc:
            # unexpected error
            traceback.print_exc()
            yield Info('error', f'Failed to export {id!r}: {exc}', exc=exc)

    def _export_item_internal(self, id, id_chain):
        meta = self.book.meta[id]
        index = meta.get('index', '')

        # generate a unique timestamp as prefix
        dt = datetime.now(timezone.utc)
        ets = util.datetime_to_id(dt)
        while ets in self.used_ts:
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
        parents = [{'id': id, 'title': self.book.meta.get(id, {}).get('title', '')} for id in id_chain]
        meta_data = {'id': id, **meta}
        export_data = {
            'version': 1,
            'id': eid,
            'timestamp': ets,
            'timezone': dt.astimezone().utcoffset().total_seconds(),
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
        lh = book.get_tree_lock().acquire() if lock else nullcontext()
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
