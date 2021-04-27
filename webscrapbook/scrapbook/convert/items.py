import os
import shutil
import zipfile
import traceback
import time
import copy
import html
from datetime import datetime, timezone
from email.utils import format_datetime

from ... import util
from ...util import Info
from ..host import Host
from ..indexer import FavIconCacher


class Converter:
    def __init__(self, input, output, book_ids=None, item_ids=None, types=None, format=None):
        self.input = input
        self.output = output
        self.book_ids = book_ids
        self.item_ids = item_ids
        self.types = set(types) if types else {}
        self.format = format

    def run(self):
        if self.input != self.output:
            yield Info('info', 'Copying files...')
            self._copy_files()

        yield Info('info', 'Applying conversion...')
        host = Host(self.output)

        # handle all books if none specified
        for book_id in self.book_ids or host.books:
            try:
                book = host.books[book_id]
            except KeyError:
                # skip invalid book ID
                yield Info('warn', f'Skipped invalid book "{book_id}".')
                continue

            yield Info('info', f'Handling book "{book_id}"...')
            book.load_meta_files()

            book_meta_orig = copy.deepcopy(book.meta)

            # handle all items if none specified
            for id in self.item_ids or book.meta:
                if id not in book.meta:
                    # skip invalid item ID
                    yield Info('debug', f'Skipped invalid item "{id}".')
                    continue

                type = book.meta[id].get('type', '')
                if type not in self.types:
                    yield Info('debug', f'Skipped item "{id}": type="{type}"')
                    continue

                yield Info('debug', f'Checking "{id}"...')

                if self.format:
                    try:
                        yield from self._convert_item_format(book, id)
                    except Exception as exc:
                        # @TODO: better exception handling
                        yield Info('error', f'Failed to convert "{id}": {exc}', exc=exc)

            # update files
            if book.meta != book_meta_orig:
                yield Info('info', 'Saving changed meta files...')
                book.save_meta_files()

    def _copy_files(self):
        with os.scandir(self.input) as dirs:
            for src in dirs:
                dst = os.path.join(self.output, src.name)
                try:
                    shutil.copytree(src, dst)
                except NotADirectoryError:
                    shutil.copy2(src, dst)

    def _convert_item_format(self, book, id):
        meta = book.meta[id]
        index = meta.get('index')

        if not index:
            yield Info('debug', f'Skipped "{id}": no index')
            return

        if index.endswith('/index.html'):
            format = 'folder'
        elif util.is_htz(index):
            format = 'htz'
        elif util.is_maff(index):
            format = 'maff'
        elif util.is_html(index):
            format = 'single_html'
        else:
            format = 'file'

        if format == self.format:
            yield Info('debug', f'Skipped "{id}": same format')
            return

        if format == 'folder':
            indexbase = index[:-11]
            fsrc = os.path.normpath(os.path.join(book.data_dir, indexbase))
            indexdir = os.path.normpath(os.path.join(book.data_dir, indexbase + '.' + util.datetime_to_id()))
            shutil.copytree(fsrc, indexdir)
            yield from self._cache_favicon(book, id)
        elif format == 'htz':
            fsrc = os.path.normpath(os.path.join(book.data_dir, index))
            indexbase = index[:-4]
            indexdir = os.path.normpath(os.path.join(book.data_dir, indexbase + '.' + util.datetime_to_id()))
            util.zip_extract(fsrc, indexdir)
        elif format == 'maff':
            fsrc = os.path.normpath(os.path.join(book.data_dir, index))
            indexbase = index[:-5]
            indexdir = os.path.normpath(os.path.join(book.data_dir, indexbase + '.' + util.datetime_to_id()))

            maff_info = next(iter(util.get_maff_pages(fsrc)), None)
            if not maff_info:
                yield Info('debug', f'Skipping "{id}": no valid index page in MAFF')
            subpath, _, _ = maff_info.indexfilename.partition('/')

            util.zip_extract(fsrc, indexdir, subpath)

            rdf_file = os.path.join(indexdir, 'index.rdf')
            try:
                os.remove(rdf_file)
            except FileNotFoundError:
                pass
        else:
            # @TODO: support single_html
            yield Info('debug', f'Skipped "{id}": unsupported format')
            return

        try:
            if self.format == 'folder':
                fdst = os.path.normpath(os.path.join(book.data_dir, indexbase))
                yield Info('info', f'Converting "{id}": "{book.get_subpath(fsrc)}" => "{book.get_subpath(fdst)}" ...')

                if os.path.lexists(fdst):
                    yield Info('error', f'Failed to convert "{id}": target "{book.get_subpath(fdst)}" already exists.')
                    return

                shutil.move(indexdir, fdst)
                meta['index'] = indexbase + '/index.html'

            elif self.format == 'htz':
                fdst = os.path.normpath(os.path.join(book.data_dir, indexbase + '.htz'))
                yield Info('info', f'Converting "{id}": "{book.get_subpath(fsrc)}" => "{book.get_subpath(fdst)}" ...')

                if os.path.lexists(fdst):
                    yield Info('error', f'Failed to convert "{id}": target "{book.get_subpath(fdst)}" already exists.')
                    return

                util.zip_compress(fdst, indexdir, '')
                meta['index'] = indexbase + '.htz'

            elif self.format == 'maff':
                fdst = os.path.normpath(os.path.join(book.data_dir, indexbase + '.maff'))
                yield Info('info', f'Converting "{id}": "{book.get_subpath(fsrc)}" => "{book.get_subpath(fdst)}" ...')

                rdf_file = os.path.join(indexdir, 'index.rdf')
                if os.path.lexists(rdf_file):
                    yield Info('error', f'Failed to convert "{id}": index.rdf file already exists.')
                    return

                if os.path.lexists(fdst):
                    yield Info('error', f'Failed to convert "{id}": target "{book.get_subpath(fdst)}" already exists.')
                    return

                subpath = id if util.id_to_datetime(id) else util.datetime_to_id()
                util.zip_compress(fdst, indexdir, subpath)

                rdf_content = self._generate_index_rdf(book, id)
                with zipfile.ZipFile(fdst, 'a') as zh:
                    zh.writestr(f'{subpath}/index.rdf', rdf_content,
                            **util.zip_compression_params(mimetype='application/rdf+xml'))

                meta['index'] = indexbase + '.maff'

            try:
                shutil.rmtree(fsrc)
            except NotADirectoryError:
                os.remove(fsrc)
        finally:
            try:
                shutil.rmtree(indexdir)
            except FileNotFoundError:
                pass

    def _cache_favicon(self, book, id):
        generator = FavIconCacher(book, cache_archive=True, cache_file=True)
        yield from generator.run([id])

    def _generate_index_rdf(self, book, id):
        meta = book.meta[id]
        dt = util.id_to_datetime(meta.get('create', ''))
        dt = dt.astimezone() if dt else datetime.now(timezone.utc)
        return f"""\
<?xml version="1.0"?>
<RDF:RDF xmlns:MAF="http://maf.mozdev.org/metadata/rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<RDF:Description RDF:about="urn:root">
  <MAF:originalurl RDF:resource="{html.escape(meta.get('source', ''))}"/>
  <MAF:title RDF:resource="{html.escape(meta.get('title', ''))}"/>
  <MAF:archivetime RDF:resource="{format_datetime(dt)}"/>
  <MAF:indexfilename RDF:resource="index.html"/>
  <MAF:charset RDF:resource="{html.escape(meta.get('charset') or 'UTF-8')}"/>
</RDF:Description>
</RDF:RDF>
"""


def run(input, output, book_ids=None, item_ids=None, types=None, format=None):
    start = time.time()
    book_ids_text = ', '.join(f'"{id}"' for id in book_ids) if book_ids else '(all)'
    item_ids_text = ', '.join(f'"{id}"' for id in item_ids) if item_ids else '(all)'
    yield Info('info', 'converting items:')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output) if output is not None else "(in-place)"}')
    yield Info('info', f'book(s): {book_ids_text}')
    yield Info('info', f'item(s): {item_ids_text}')
    yield Info('info', f'types: {types}')
    yield Info('info', f'format: {format}')
    yield Info('info', '')

    if output is None:
        output = input

    try:
        conv = Converter(input, output, book_ids=book_ids, item_ids=item_ids, types=types, format=format)
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
