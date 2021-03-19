import os
import shutil
import traceback
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from ... import WSB_DIR
from ... import util
from ...util import Info
from ..host import Host
from ..check import Indexer


FIND_INDEX_EXT = {'.html', '.htz', '.maff', '.htm'}


class Converter:
    def __init__(self, input, output):
        self.input = os.path.abspath(input)
        self.output = os.path.abspath(output)
        self.wsb_dir = os.path.join(self.input, WSB_DIR)
        self.host = None
        self.book = None

    def run(self):
        self.host = Host(self.output)
        self.book = self.host.books['']

        self.book.load_meta_files()
        self.book.load_toc_files()

        yield Info('info', 'Inspecting data files...')
        paths = []
        yield from self._inspect_data_dir(self.input, paths)

        yield Info('info', 'Saving tree files...')
        self.book.save_meta_files()
        self.book.save_toc_files()

    def _inspect_data_dir(self, data_dir, paths):
        yield Info('debug', f'Inspecting directory "{data_dir}"')

        if not os.path.samefile(data_dir, self.input):
            # add data_dir as an item if index.html exists
            index = os.path.join(data_dir, 'index.html')
            if os.path.isfile(index):
                yield from self._index_entry(data_dir, paths)
                return

            # create folder item
            basename = os.path.basename(data_dir)
            basename, ext = os.path.splitext(basename)
            if ext.lower() == '.htd': ext = ''

            id = self._generate_unique_id()
            meta = self.book.DEFAULT_META.copy()
            meta.update({
                'type': 'folder',
                'title': basename + ext,
                'create': id,
                'modify': id,
                })
            for key in list(meta):
                if meta[key] is None:
                    del meta[key]
            self.book.meta[id] = meta

            parent_id = paths[-1]
            self.book.toc.setdefault(parent_id, []).append(id)
            yield Info('info', f'Generated folder item "{id}" under "{parent_id}"')
        else:
            id = 'root'

        try:
            entries = os.scandir(data_dir)
        except FileNotFoundError:
            return
        except OSError as exc:
            yield Info('error', f'Failed to scan folder '
                f'"{self.book.get_subpath(exc.filename)}": [Errno {exc.args[0]}] {exc.args[1]}', exc=exc)
            return

        entries_to_handle = set()
        entries_to_exclude = set()
        with entries as entries:
            for entry in entries:
                if os.path.normcase(entry.path) == os.path.normcase(self.wsb_dir):
                    yield Info('debug', f'Skipped special "{self.book.get_subpath(entry)}"')
                    continue

                if entry.is_dir():
                    entries_to_handle.add(entry)

                elif entry.is_file():
                    if self._get_index_path_key(entry) not in entries_to_exclude:
                        basename, ext = os.path.splitext(entry.name)
                        if ext.lower() in FIND_INDEX_EXT:
                            entries_to_handle.add(entry)

                            if util.is_html(entry.path):
                                p = self._get_index_path_key(os.path.join(data_dir, f'{basename}.files'))
                                yield Info('debug', f'Excluding "{p}" from index finding')
                                entries_to_exclude.add(p)

                                p = self._get_index_path_key(os.path.join(data_dir, f'{basename}_files'))
                                yield Info('debug', f'Excluding "{p}" from index finding')
                                entries_to_exclude.add(p)

        paths.append(id)

        for entry in sorted(entries_to_handle, key=lambda x: x.path):
            if self._get_index_path_key(entry) in entries_to_exclude:
                continue

            if entry.is_dir():
                yield from self._inspect_data_dir(entry.path, paths)
            elif entry.is_file():
                yield from self._index_entry(entry.path, paths)

        paths.pop()

    def _index_entry(self, entry, paths):
        yield Info('debug', f'Generating item for "{entry}"...')

        _, ext = os.path.splitext(entry)
        ext = ext.lower()
        if ext == '.htd': ext = ''

        # generate a unique ID
        id = self._generate_unique_id(ext)

        # copy data files
        supporting_folder = self._get_supporting_folder(entry)
        if supporting_folder:
            basename = os.path.basename(entry)
            dst_dir = os.path.join(self.book.data_dir, id)
            os.makedirs(dst_dir, exist_ok=True)

            index_file = os.path.join(dst_dir, 'index.html')

            src = entry
            dst = os.path.join(dst_dir, basename)
            yield Info('info', f'Copying data file: "{src}" => "{dst}"')
            try:
                shutil.copy2(src, dst)
            except OSError as exc:
                yield Info('error', f'Failed to copy data file "{entry}": {exc}')
            try:
                shutil.copy2(src, index_file)
            except OSError as exc:
                yield Info('error', f'Failed to copy data file "{entry}": {exc}')

            src = supporting_folder
            dst = os.path.join(dst_dir, os.path.basename(supporting_folder))
            yield Info('info', f'Copying data folder: "{src}" => "{dst}"')
            try:
                shutil.copytree(src, dst)
            except OSError as exc:
                yield Info('error', f'Failed to copy data folder "{entry}": {exc}')

            # generate meta
            indexer = Indexer(self.book)
            indexed = yield from indexer.run([index_file])

            with open(index_file, 'w', encoding='UTF-8') as fh:
                fh.write(f'<!DOCTYPE html><meta charset="UTF-8"><meta http-equiv="refresh" content="0;url={quote(basename)}">')

        else:
            src = entry
            dst = os.path.join(self.book.data_dir, id + ext)
            yield Info('info', f'Copying data files: "{src}" => "{dst}"')
            try:
                try:
                    shutil.copytree(src, dst)
                except NotADirectoryError:
                    shutil.copy2(src, dst)
            except OSError as exc:
                yield Info('error', f'Failed to copy data files for "{entry}": {exc}')

            index_file = os.path.join(dst, 'index.html') if os.path.isdir(entry) else dst

            # generate meta
            indexer = Indexer(self.book)
            indexed = yield from indexer.run([index_file])

        for id in indexed:
            parent_id = paths[-1]
            self.book.toc.setdefault(parent_id, []).append(id)
            yield Info('info', f'Appended item "{id}" under "{parent_id}"')

    def _get_index_path_key(self, path):
        return self.book.get_subpath(os.path.normcase(path))

    def _get_supporting_folder(self, file):
        if os.path.isfile(file) and util.is_html(file):
            base = os.path.splitext(file)[0]

            supporting_folder = f'{base}.files'
            if os.path.isdir(supporting_folder):
                return supporting_folder

            supporting_folder = f'{base}_files'
            if os.path.isdir(supporting_folder):
                return supporting_folder

        return None

    def _generate_unique_id(self, ext=''):
        dt = datetime.now(timezone.utc)
        id = util.datetime_to_id(dt)
        while id in self.book.meta or os.path.lexists(os.path.join(self.book.data_dir, id + ext)):
            dt += timedelta(milliseconds=1)
            id = util.datetime_to_id(dt)
        return id


def run(input, output):
    start = time.time()
    yield Info('info', 'conversion mode: hierarchial files --> WebScrapBook')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output)}')
    yield Info('info', '')

    try:
        conv = Converter(input, output)
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
