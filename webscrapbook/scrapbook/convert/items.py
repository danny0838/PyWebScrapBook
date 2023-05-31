import html
import os
import shutil
import time
import traceback
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import quote

from ... import util
from ..._polyfill import zipfile
from ...util import Info
from ..host import Host
from ..indexer import FavIconCacher, SingleHtmlConverter, UnSingleHtmlConverter


class Converter:
    def __init__(self, input, output, book_items=None, types=None, format=None):
        self.input = input
        self.output = output
        self.book_items = book_items
        self.types = set(types) if types else {}
        self.format = format

    def run(self):
        if self.input != self.output:
            yield Info('info', 'Copying files...')
            os.makedirs(self.output, exist_ok=True)
            self._copy_files()

        yield Info('info', 'Applying conversion...')
        host = Host(self.output)

        for book_id, item_ids in (self.book_items or dict.fromkeys(host.books)).items():
            try:
                book = host.books[book_id]
            except KeyError:
                # skip invalid book ID
                yield Info('warn', f'Skipped invalid book {book_id!r}.')
                continue

            yield Info('info', f'Handling book {book_id!r}...')
            book.load_meta_files()

            book_meta_orig = book.checksum(book.meta)

            for id in (item_ids or book.meta):
                if id not in book.meta:
                    # skip invalid item ID
                    yield Info('debug', f'Skipped invalid item {id!r}.')
                    continue

                type = book.meta[id].get('type', '')
                if type not in self.types:
                    yield Info('debug', f'Skipped item {id!r}: type={type!r}')
                    continue

                yield Info('debug', f'Checking {id!r}...')

                if self.format:
                    try:
                        try:
                            yield from self._convert_item_format(book, id)
                        except OSError as exc:
                            raise RuntimeError(exc.strerror) from exc
                    except Exception as exc:
                        traceback.print_exc()
                        yield Info('error', f'Failed to convert {id!r}: {exc}', exc=exc)

            # update files
            if book.checksum(book.meta) != book_meta_orig:
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
            yield Info('debug', f'Skipped {id!r}: no index')
            return

        if index.endswith('/index.html'):
            format = 'folder'
        elif util.is_htz(index):
            format = 'htz'
        elif util.is_maff(index):
            format = 'maff'
        else:
            format = 'single_file'

        if format == self.format:
            yield Info('debug', f'Skipped {id!r}: same format')
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
            util.fs.zip_extract(fsrc, indexdir)
        elif format == 'maff':
            fsrc = os.path.normpath(os.path.join(book.data_dir, index))
            indexbase = index[:-5]
            indexdir = os.path.normpath(os.path.join(book.data_dir, indexbase + '.' + util.datetime_to_id()))

            maff_info = next(iter(util.get_maff_pages(fsrc)), None)
            if not maff_info:
                yield Info('debug', f'Skipping {id!r}: no valid index page in MAFF')
            subpath, _, _ = maff_info.indexfilename.partition('/')

            util.fs.zip_extract(fsrc, indexdir, subpath)

            rdf_file = os.path.join(indexdir, 'index.rdf')
            try:
                os.remove(rdf_file)
            except FileNotFoundError:
                pass
        else:
            fsrc = os.path.normpath(os.path.join(book.data_dir, index))
            indexbase, ext = os.path.splitext(index)
            indexdir = os.path.normpath(os.path.join(book.data_dir, indexbase + '.' + util.datetime_to_id()))

            os.makedirs(indexdir)
            indexfile = os.path.join(indexdir, 'index.html')
            if util.is_html(fsrc) and not util.is_xhtml(fsrc):
                mainfile = indexfile
                shutil.copy2(fsrc, mainfile)
            else:
                basename = os.path.basename(index)
                mainfile = os.path.join(indexdir, basename)
                shutil.copy2(fsrc, mainfile)
                with open(indexfile, 'w', encoding='UTF-8', newline='\n') as fh:
                    fh.write(f'<!DOCTYPE html><meta charset="UTF-8"><meta http-equiv="refresh" content="0; url={quote(basename)}">')

            if util.is_html(mainfile) or util.is_svg(mainfile):
                conv = UnSingleHtmlConverter(mainfile)
                content = conv.run()
                with open(mainfile, 'w', encoding=conv.encoding, newline='') as fh:
                    fh.write(content)

            shutil.copystat(fsrc, indexfile)

        try:
            if self.format == 'folder':
                fdst = os.path.normpath(os.path.join(book.data_dir, indexbase))
                yield Info('info', f'Converting {id!r}: {book.get_subpath(fsrc)!r} => {book.get_subpath(fdst)!r} ...')

                if os.path.lexists(fdst):
                    yield Info('error', f'Failed to convert {id!r}: target {book.get_subpath(fdst)!r} already exists.')
                    return

                shutil.move(indexdir, fdst)

                # adjust icon path to fit the new index file
                iconfile = book.get_icon_file(meta)
                if iconfile:
                    meta['icon'] = util.get_relative_url(iconfile, fdst, path_is_dir=False, start_is_dir=True)

                meta['index'] = indexbase + '/index.html'

            elif self.format == 'htz':
                fdst = os.path.normpath(os.path.join(book.data_dir, indexbase + '.htz'))
                yield Info('info', f'Converting {id!r}: {book.get_subpath(fsrc)!r} => {book.get_subpath(fdst)!r} ...')

                if os.path.lexists(fdst):
                    yield Info('error', f'Failed to convert {id!r}: target {book.get_subpath(fdst)!r} already exists.')
                    return

                util.fs.zip_compress(fdst, indexdir, '')
                shutil.copystat(os.path.join(indexdir, 'index.html'), fdst)

                # adjust icon path to fit the new index file
                iconfile = book.get_icon_file(meta)
                if iconfile:
                    meta['icon'] = util.get_relative_url(iconfile, fdst, path_is_dir=False, start_is_dir=False)

                meta['index'] = indexbase + '.htz'

            elif self.format == 'maff':
                fdst = os.path.normpath(os.path.join(book.data_dir, indexbase + '.maff'))
                yield Info('info', f'Converting {id!r}: {book.get_subpath(fsrc)!r} => {book.get_subpath(fdst)!r} ...')

                rdf_file = os.path.join(indexdir, 'index.rdf')
                if os.path.lexists(rdf_file):
                    yield Info('error', f'Failed to convert {id!r}: index.rdf file already exists.')
                    return

                if os.path.lexists(fdst):
                    yield Info('error', f'Failed to convert {id!r}: target {book.get_subpath(fdst)!r} already exists.')
                    return

                subpath = id if util.id_to_datetime(id) else util.datetime_to_id()
                util.fs.zip_compress(fdst, indexdir, subpath)

                rdf_content = self._generate_index_rdf(book, id)
                with zipfile.ZipFile(fdst, 'a') as zh:
                    zh.writestr(
                        f'{subpath}/index.rdf', rdf_content,
                        **util.fs.zip_compression_params(mimetype='application/rdf+xml')
                    )

                shutil.copystat(os.path.join(indexdir, 'index.html'), fdst)

                # adjust icon path to fit the new index file
                iconfile = book.get_icon_file(meta)
                if iconfile:
                    meta['icon'] = util.get_relative_url(iconfile, fdst, path_is_dir=False, start_is_dir=False)

                meta['index'] = indexbase + '.maff'

            elif self.format == 'single_file':
                file = os.path.join(indexdir, 'index.html')
                file = util.get_meta_refreshed_file(file) or file

                if util.is_xhtml(file):
                    ext = '.xhtml'
                elif util.is_html(file):
                    ext = '.html'
                elif util.is_svg(file):
                    ext = '.svg'
                else:
                    _, ext = os.path.splitext(file)

                # special handling to prevent named "index.html"
                if indexbase == 'index' and ext == '.html':
                    indexbase = 'index_'

                fdst = os.path.normpath(os.path.join(book.data_dir, indexbase + ext))
                yield Info('info', f'Converting {id!r}: {book.get_subpath(fsrc)!r} => {book.get_subpath(fdst)!r} ...')

                if os.path.lexists(fdst):
                    yield Info('error', f'Failed to convert {id!r}: target {book.get_subpath(fdst)!r} already exists.')
                    return

                if util.is_html(file) or util.is_svg(file):
                    conv = SingleHtmlConverter(file)
                    content = conv.run()
                    with open(fdst, 'w', encoding=conv.encoding, newline='') as fh:
                        fh.write(content)
                    shutil.copystat(file, fdst)
                else:
                    shutil.copy2(file, fdst)

                if meta.get('icon'):
                    iconfile = book.get_icon_file(meta)
                    meta['icon'] = util.get_relative_url(iconfile, fdst, path_is_dir=False, start_is_dir=False)
                meta['index'] = indexbase + ext

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


def run(input, output, book_items=None, types=None, format=None):
    start = time.time()
    yield Info('info', 'converting items:')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output) if output is not None else "(in-place)"}')

    if book_items:
        for book_id, item_ids in book_items.items():
            item_ids_text = ', '.join(f'{id!r}' for id in item_ids) if item_ids else 'all'
            yield Info('info', f'book: {book_id!r}, item(s): {item_ids_text}')
    else:
        yield Info('info', 'books: all, items: all')

    yield Info('info', f'types: {types}')
    yield Info('info', f'format: {format}')
    yield Info('info', '')

    if output is None:
        output = input

    try:
        conv = Converter(input, output, book_items=book_items, types=types, format=format)
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
