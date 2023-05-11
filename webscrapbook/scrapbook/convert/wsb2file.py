import html
import os
import shutil
import time
import traceback

from ... import util
from ...util import Info
from ..host import Host


class Converter:
    def __init__(self, input, output, book_id='', prefix=True):
        self.input = input
        self.output = output
        self.book_id = book_id
        self.book = None
        self.prefix = prefix

        self.used_paths = set()

    def run(self):
        host = Host(self.input)

        try:
            self.book = host.books[self.book_id]
        except KeyError as exc:
            raise RuntimeError(f'book {self.book_id!r} does not exist') from exc

        self.book.load_meta_files()
        self.book.load_toc_files()

        id_chain = set()
        path_chain = []
        ref_ids = self.book.toc.get(self.book.ROOT_ITEM_ID, [])
        idx_len = len(str(len(ref_ids)))
        for idx, ref_id in enumerate(ref_ids):
            yield from self._export_item(ref_id, idx, idx_len, id_chain, path_chain)

    def _export_item(self, id, idx, idx_len, id_chain, path_chain):
        if id not in self.book.meta or id in self.book.SPECIAL_ITEM_ID:
            return

        yield Info('debug', f'Exporting item {id!r}')

        meta = self.book.meta[id]
        type = meta.get('type', '')
        prefix = f'{idx + 1:0{idx_len}d}-' if self.prefix else ''
        basename = self.book.meta[id].get('title') or (id if type != 'separator' else '----')

        path = os.path.join(self.output, *path_chain, util.crop(prefix + util.validate_filename(basename), 128))
        path = self._get_unique_path(path)
        self.used_paths.add(path)

        if type == 'folder':
            dst = path
            subpath = os.path.relpath(dst, self.output)
            yield Info('info', f'Exporting {id!r} to {subpath!r}...')
            try:
                os.makedirs(dst, exist_ok=True)
            except OSError as exc:
                yield Info('error', f'Failed to export {id!r} to {subpath!r}: {exc}', exc=exc)

        elif type == 'separator':
            if self.prefix:
                dst = path + '.-'
                subpath = os.path.relpath(dst, self.output)
                yield Info('info', f'Exporting {id!r} to {subpath!r}...')
                try:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with open(dst, 'wb') as fh:
                        pass
                except OSError as exc:
                    yield Info('error', f'Failed to export {id!r} to {subpath!r}: {exc}', exc=exc)

        elif type == 'bookmark':
            source = meta.get('source')
            if source:
                dst = path + '.htm'
                subpath = os.path.relpath(dst, self.output)
                yield Info('info', f'Exporting {id!r} to {subpath!r}...')
                try:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with open(dst, 'w', encoding='UTF-8') as fh:
                        fh.write(f'<!DOCTYPE html><meta charset="UTF-8"><meta http-equiv="refresh" content="0; url={html.escape(source)}">')
                except OSError as exc:
                    yield Info('error', f'Failed to export {id!r} to {subpath!r}: {exc}', exc=exc)

        else:
            index = meta.get('index', '')
            if index:
                if index.endswith('/index.html'):
                    src = os.path.normpath(os.path.dirname(os.path.join(self.book.data_dir, index)))
                    ext = '.htd'
                else:
                    src = os.path.normpath(os.path.join(self.book.data_dir, index))
                    _, ext = os.path.splitext(src)

                    if not ext:
                        # prevent conflict with folder
                        ext = '._'

                dst = path + ext
                subpath = os.path.relpath(dst, self.output)
                yield Info('info', f'Exporting {id!r} to {subpath!r}...')
                try:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    try:
                        shutil.copytree(src, dst)
                    except NotADirectoryError:
                        shutil.copy2(src, dst)
                except OSError as exc:
                    yield Info('error', f'Failed to export {id!r} to {subpath!r}: {exc}', exc=exc)

        # do not add descendants for a recursive item
        if id in id_chain:
            return

        id_chain.add(id)
        path_chain.append(os.path.basename(path))
        ref_ids = self.book.toc.get(id, [])
        idx_len = len(str(len(ref_ids)))
        for idx, ref_id in enumerate(ref_ids):
            yield from self._export_item(ref_id, idx, idx_len, id_chain, path_chain)
        path_chain.pop()
        id_chain.remove(id)

    def _get_unique_path(self, path):
        i = 0
        prefix = path
        while path in self.used_paths:
            i += 1
            path = f'{prefix}({i})'
        return path


def run(input, output, book_id='', prefix=True):
    start = time.time()
    yield Info('info', 'conversion mode: WebScrapBook --> hierarchical files')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output)}')
    yield Info('info', f'book: {book_id!r}')
    yield Info('info', f'prefix: {prefix}')
    yield Info('info', '')

    try:
        conv = Converter(input, output, book_id=book_id, prefix=prefix)
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
