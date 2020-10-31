import os
import shutil
import zipfile
import traceback
import time
from urllib.parse import urlsplit, quote, unquote
from urllib.request import pathname2url, url2pathname
from datetime import datetime, timedelta

from ... import WSB_DIR, WSB_CONFIG
from ... import util
from ...util import Info
from ..host import Host
from .. import book as wsb_book

from lxml import etree


RDF = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'
NS1 = '{http://amb.vis.ne.jp/mozilla/scrapbook-rdf#}'
NC = '{http://home.netscape.com/NC-rdf#}'

LEGACY_TYPE_MAP = {
    "postit": "note",
    "note": "notex",
    }


class Converter:
    def __init__(self, input, output, book_id=''):
        self.input = input
        self.output = output
        self.book_id = book_id

        self.id_to_oid = {}
        self.oid_to_id = {}
        self.path_to_oid = {}
        self.icons_to_cache = {}

    def run(self):
        host = Host(self.input)

        try:
            book = host.books[self.book_id]
        except KeyError as exc:
            raise RuntimeError(f'book "{self.book_id}" does not exist') from exc

        book.load_meta_files()
        book.load_toc_files()

        yield Info('info', 'Creating ID mapping...')
        yield from self._generate_id_mapping(book)

        yield Info('info', 'Creating directory mapping...')
        yield from self._generate_directory_mapping(book)

        yield Info('info', 'Generating scrapbook.rdf...')
        yield from self._generate_rdf(book)

        yield Info('info', 'Copying data files...')
        yield from self._copy_data_files(book)

        yield Info('info', 'Copying icon files...')
        yield from self._copy_icon_files()

    def _generate_id_mapping(self, book):
        def get_legacy_id(id):
            ts = util.id_to_datetime(id)
            if ts:
                return util.datetime_to_id_legacy(ts)

            ts = util.id_to_datetime_legacy(id)
            if ts:
                return id

            return None

        def generate_unique_id(id):
            oid = get_legacy_id(id) or util.datetime_to_id_legacy()
            ts = util.id_to_datetime_legacy(oid)
            while oid in self.oid_to_id:
                ts += timedelta(seconds=1)
                oid = util.datetime_to_id_legacy(ts)
            return oid

        nonconvertable_ids = []

        # map convertable IDs
        for id in book.meta:
            yield Info('debug', f'Createding ID mapping: "{id}"')
            oid = get_legacy_id(id)
            if oid and oid not in self.oid_to_id:
                self.id_to_oid[id] = oid
                self.oid_to_id[oid] = id
                yield Info('debug', f'Created ID mapping: "{id}" => "{oid}"')
            else:
                nonconvertable_ids.append(id)

        # generate for non-convertable IDs
        for id in nonconvertable_ids:
            oid = generate_unique_id(id)
            self.id_to_oid[id] = oid
            self.oid_to_id[oid] = id
            yield Info('debug', f'Created ID mapping: "{id}" => "{oid}" (new)')

    def _generate_directory_mapping(self, book):
        for id, oid in self.id_to_oid.items():
            index = book.meta[id].get('index', '')
            if not index.endswith('/index.html'):
                continue

            dsrc = os.path.join(book.data_dir, os.path.dirname(index), '')
            self.path_to_oid[os.path.normcase(dsrc)] = oid
            yield Info('debug', f'Created directory mapping "{dsrc}" => "{oid}"')

    def _generate_rdf(self, book):
        def make_meta_node(id, meta):
            yield Info('debug', f'Generating meta node for "{id}"')

            oid = self.id_to_oid[id]
            ometa = {}
            type = meta.get('type', '')
            tagname = f'{NC}BookmarkSeparator' if type == 'separator' else f'{RDF}Description'

            node = etree.SubElement(root, tagname)
            node.attrib[f'{RDF}about'] = f'urn:scrapbook:item{oid}'
            node.attrib[f'{NS1}id'] = oid

            otype = LEGACY_TYPE_MAP.get(type, type)
            if meta.get('marked') and otype == '':
                node.attrib[f'{NS1}type'] = 'marked'
            else:
                node.attrib[f'{NS1}type'] = otype

            node.attrib[f'{NS1}title'] = meta.get('title', '')
            node.attrib[f'{NS1}chars'] = meta.get('charset', '')
            node.attrib[f'{NS1}source'] = meta.get('source', '')
            node.attrib[f'{NS1}icon'] = yield from self._handle_item_icon(book, id)
            node.attrib[f'{NS1}comment'] = meta.get('comment', '').replace('\n', ' __BR__ ')

            create = meta.get('create')
            if create:
                node.attrib[f'{NS1}create'] = util.datetime_to_id_legacy(util.id_to_datetime(create))

            modify = meta.get('modify')
            if modify:
                node.attrib[f'{NS1}modify'] = util.datetime_to_id_legacy(util.id_to_datetime(modify))

            locked = meta.get('locked')
            if locked is not None:
                node.attrib[f'{NS1}lock'] = 'true' if locked else ''

        def make_toc_node(id):
            yield Info('debug', f'Generating TOC node for "{id}"')

            node = etree.SubElement(root, f'{RDF}Seq')
            if id == 'root':
                node.attrib[f'{RDF}about'] = f'urn:scrapbook:root'
            else:
                oid = self.id_to_oid[id]
                node.attrib[f'{RDF}about'] = f'urn:scrapbook:item{oid}'

            for ref_id in book.toc.get(id, []):
                if ref_id in seen_in_toc:
                    yield Info('debug', f'Skipped adding "{ref_id}" under "{id}" (referenced)')
                    continue

                yield Info('debug', f'Adding "{ref_id}" under "{id}"')
                oref_id = self.id_to_oid[ref_id]
                child = etree.SubElement(node, f'{RDF}li')
                child.attrib[f'{RDF}resource'] = f'urn:scrapbook:item{oref_id}'
                seen_in_toc.add(ref_id)

                if ref_id in book.toc:
                    yield from make_toc_node(ref_id)

        root = etree.XML("""\
<?xml version="1.0"?>
<RDF:RDF xmlns:NS1="http://amb.vis.ne.jp/mozilla/scrapbook-rdf#"
         xmlns:NC="http://home.netscape.com/NC-rdf#"
         xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
</RDF:RDF>
""")

        for id, meta in book.meta.items():
            yield from make_meta_node(id, meta)

        seen_in_toc = {'root'}
        yield from make_toc_node('root')

        try:
            etree.indent(root)
        except AttributeError:
            # etree.indent is supported since lxml >= 4.5.0
            # Do simple line separation for first-level children for older
            # versions.
            for child in root:
                child.tail = '\n'

        tree = root.getroottree()
        file = os.path.join(self.output, 'scrapbook.rdf')
        os.makedirs(os.path.dirname(file), exist_ok=True)
        tree.write(file, encoding='UTF-8', xml_declaration=True, pretty_print=True)

    def _copy_data_files(self, book):
        for id, oid in self.id_to_oid.items():
            yield Info('debug', f'Copying data files for "{id}" => "{oid}"')
            type = book.meta[id].get('type', '')
            if type in wsb_book.Book.TYPES_OPTIONAL_INDEX:
                yield Info('debug', f'Skipped copying data for "{id}": type is "{type}"')
                continue

            index = book.meta[id].get('index', '')
            if not index:
                yield Info('debug', f'Skipped copying data for "{id}": no index')
                continue

            try:
                if index.endswith('/index.html'):
                    fsrc = os.path.normpath(os.path.dirname(os.path.join(book.data_dir, index)))
                    fdst = os.path.join(self.output, 'data', oid)
                    os.makedirs(os.path.dirname(fdst), exist_ok=True)
                    shutil.copytree(fsrc, fdst)
                elif os.path.splitext(index)[1].lower() == '.html':
                    fsrc = os.path.normpath(os.path.join(book.data_dir, index))
                    fdst = os.path.join(self.output, 'data', oid, 'index.html')
                    os.makedirs(os.path.dirname(fdst), exist_ok=True)
                    shutil.copy2(fsrc, fdst)
                elif util.is_htz(index):
                    fsrc = os.path.normpath(os.path.join(book.data_dir, index))
                    fdst = os.path.join(self.output, 'data', oid)
                    os.makedirs(os.path.dirname(fdst), exist_ok=True)
                    util.zip_extract(fsrc, fdst)
                elif util.is_maff(index):
                    fsrc = os.path.normpath(os.path.join(book.data_dir, index))
                    fdst = os.path.join(self.output, 'data', oid)
                    pages = util.get_maff_pages(fsrc)
                    if len(pages) == 0:
                        yield Info('error', f'Failed to copy data for "{id}": no page in MAFF archive')
                        continue
                    else:
                        if len(pages) > 1:
                            yield Info('warn', f'"{id}": only the first web page in MAFF archive can be copied')
                        page = pages[0]
                        topdir, _, _ = page.indexfilename.partition('/')

                    os.makedirs(os.path.dirname(fdst), exist_ok=True)
                    with zipfile.ZipFile(fsrc) as zh:
                        util.zip_extract(fsrc, fdst, topdir)
                else:
                    basename = os.path.basename(index)
                    fsrc = os.path.normpath(os.path.join(book.data_dir, index))
                    fdst = os.path.join(self.output, 'data', oid, basename)
                    os.makedirs(os.path.dirname(fdst), exist_ok=True)
                    shutil.copy2(fsrc, fdst)
                    with open(os.path.join(self.output, 'data', oid, 'index.html'), 'w', encoding='UTF-8') as fh:
                        fh.write('<html><head><meta charset="UTF-8">'
                            f'<meta http-equiv="refresh" content="0;URL=./{quote(basename)}">'
                            '</head><body></body></html>')
            except OSError as exc:
                yield Info('error', f'Failed to copy data for "{id}": {exc}', exc=exc)

            if type == 'postit':
                yield Info('debug', f'Converting data file for "{id}": type={type}')
                file = os.path.join(self.output, 'data', oid, 'index.html')
                content = book.load_note_file(file)
                with open(file, 'w', encoding='UTF-8') as fh:
                    fh.write(f"""\
<html><head><meta http-equiv="Content-Type" content="text/html;Charset=UTF-8"></head><body><pre>
{content}
</pre></body></html>""")

    def _handle_item_icon(self, book, id):
        yield Info('debug', f'Checking icon for "{id}"')
        icon = book.meta[id].get('icon', '')

        if not icon:
            # return moz_icon if defined
            moz_icon_url = book.meta[id].get('icon-moz')
            if moz_icon_url:
                yield Info('debug', f'Use moz-icon URL from property for "{id}": "{moz_icon_url}"')
                return moz_icon_url

            # generate moz-icon:// for files
            if book.meta[id].get('type', '') == 'file':
                index = book.meta[id].get('index', '')
                indexfile = os.path.normpath(os.path.join(book.data_dir, index))
                _, target, _ = util.parse_meta_refresh(indexfile)
                if target:
                    parts = urlsplit(target)
                    if not parts.scheme and not parts.netloc and not parts.path.startswith('/'):
                        targetfile = os.path.join(os.path.dirname(indexfile), url2pathname(parts.path))
                        moz_icon_url = f'moz-icon://{quote(os.path.basename(targetfile))}?size=16'
                        yield Info('debug', f'Generated moz-icon URL for "{id}": "{moz_icon_url}"')
                        return moz_icon_url
            return ''

        file = book.get_icon_file(book.meta[id])

        if not file:
            return icon

        file_ci = os.path.normcase(file)

        # favicon cache should go to "icon" folder
        favicon_dir = os.path.join(book.tree_dir, 'favicon', '')
        if file_ci.startswith(os.path.normcase(favicon_dir)):
            subpath = os.path.relpath(file, favicon_dir)
            fdst = os.path.join(self.output, 'icon', subpath)
            self.icons_to_cache[file_ci] = fdst
            yield Info('debug', f'Created icon file mapping (cache): "{file}" => "{fdst}"')
            return f'resource://scrapbook/icon/{pathname2url(subpath)}'

        # if inside data folder
        if file_ci.startswith(os.path.normcase(book.data_dir)):
            # if under an item folder, map to legacy item folder
            for path, oid in self.path_to_oid.items():
                if file_ci.startswith(path):
                    subpath = os.path.relpath(file, path)
                    fdst = os.path.join(self.output, 'data', oid, subpath)
                    self.icons_to_cache[file_ci] = fdst
                    yield Info('debug', f'Created icon file mapping (item): "{file}" => "{fdst}"')
                    return f'resource://scrapbook/data/{oid}/{pathname2url(subpath)}'

            # otherwise, map to sub-data-directory path
            subpath = os.path.relpath(file, book.data_dir)
            fdst = os.path.join(self.output, 'data', subpath)
            self.icons_to_cache[file_ci] = fdst
            yield Info('debug', f'Created icon file mapping (data): "{file}" => "{fdst}"')
            return f'resource://scrapbook/data/{pathname2url(subpath)}'

        # record icons outside of "data" folder to copy later
        subpath = os.path.relpath(file, book.top_dir)
        fdst = os.path.join(self.output, subpath)
        self.icons_to_cache[file_ci] = fdst
        yield Info('debug', f'Created icon file mapping: "{file}" => "{fdst}"')
        return f'resource://scrapbook/{pathname2url(subpath)}'

    def _copy_icon_files(self):
        for fsrc, fdst in self.icons_to_cache.items():
            yield Info('debug', f'Copying icon "{fsrc}" => "{fdst}"')
            if not os.path.exists(fdst):
                os.makedirs(os.path.dirname(fdst), exist_ok=True)
                shutil.copy2(fsrc, fdst)


def run(input, output, book_id=''):
    start = time.time()
    yield Info('info', 'conversion mode: WebScrapBook --> ScrapBook')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output)}')
    yield Info('info', f'book ID: "{book_id}"')
    yield Info('info', '')

    try:
        conv = Converter(input, output, book_id=book_id)
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
