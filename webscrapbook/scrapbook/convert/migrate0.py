import os
import shutil
import traceback
import time

from ...util import Info
from ..host import Host


class Converter:
    def __init__(self, input, output, book_ids=None, *, convert_data_files=False):
        self.input = input
        self.output = output
        self.book_ids = book_ids
        self.convert_data_files = convert_data_files

    def run(self):
        if self.input != self.output:
            yield Info('info', 'Copying files...')
            self._copy_files()

        yield Info('info', 'Applying migration...')
        host = Host(self.output)

        book_ids = self.book_ids
        if not book_ids:
            book_ids = list(host.books)

        avail_book_ids = set(host.books)

        for book_id in book_ids:
            # skip invalid book ID
            if book_id not in avail_book_ids:
                yield Info('warn', f'Skipped invalid book "{book_id}".')
                continue

            yield Info('info', f'Handling book "{book_id}"...')
            book = host.books[book_id]
            book.load_meta_files()
            book.load_toc_files()

            if self.convert_data_files:
                yield from self._convert_data_files(book)

    def _copy_files(self):
        with os.scandir(self.input) as dirs:
            for src in dirs:
                dst = os.path.join(self.output, src.name)
                try:
                    shutil.copytree(src, dst)
                except NotADirectoryError:
                    shutil.copy2(src, dst)

    def _convert_data_files(self, book):
        yield Info('info', 'Converting data files...')
        converter = ConvertLegacyDataFiles(book)
        yield from converter.run()


class ConvertLegacyDataFiles:
    """Convert data files with legacy data format.

    - Convert a postit with legacy or other bad page wrapper.
    """
    def __init__(self, book):
        self.book = book

    def run(self):
        book = self.book
        for id, meta in book.meta.items():
            index = meta.get('index', '')
            if not index.endswith('/index.html'):
                continue

            type = meta.get('type', '')
            yield Info('debug', f'Converting data files for "{id}" (type="{type}")...')
            if type == 'postit':
                index_file = os.path.normpath(os.path.join(book.data_dir, index))
                yield Info('debug', f'Checking: {index_file}...')
                try:
                    content = book.load_note_file(index_file)
                except OSError as exc:
                    yield Info('error', f'Failed to convert "{index}" for "{id}": [Errno {exc.args[0]}] {exc.args[1]}', exc=exc)
                else:
                    book.save_note_file(index_file, content)


def run(input, output, book_ids=None, *, convert_data_files=False):
    start = time.time()
    ids = ', '.join(f'"{id}"' for id in book_ids) if book_ids else '(all)'
    yield Info('info', 'conversion mode: migrate0')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output) if output is not None else "(in-place)"}')
    yield Info('info', f'book ID(s): {ids}')
    yield Info('info', f'convert data files: {convert_data_files}')
    yield Info('info', '')

    if output is None:
        output = input

    try:
        conv = Converter(input, output, book_ids=book_ids, convert_data_files=convert_data_files)
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
