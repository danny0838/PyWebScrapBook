import os
import re
import shutil
import time
import traceback
from datetime import timedelta
from urllib.parse import quote
from urllib.request import pathname2url

from lxml import etree

from ... import util
from ...util import Info
from ...util.html import HtmlRewriter, Markup, MarkupTag
from ..host import Host

RDF = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'
NS1 = '{http://amb.vis.ne.jp/mozilla/scrapbook-rdf#}'
NC = '{http://home.netscape.com/NC-rdf#}'

LEGACY_TYPE_MAP = {
    'postit': 'note',
    'note': 'notex',
}

HTML_FILE_FILTER = re.compile(r'^.+\.x?html$', re.I)
REGEX_LINEFEED = re.compile(r'\r\n?|\n')


class Converter:
    def __init__(self, input, output, book_id='', data_files=False):
        self.input = input
        self.output = output
        self.book_id = book_id
        self.data_files = data_files

        self.id_to_oid = {}
        self.oid_to_id = {}
        self.path_to_oid = {}
        self.icons_to_cache = {}

    def run(self):
        host = Host(self.input)

        try:
            book = host.books[self.book_id]
        except KeyError as exc:
            raise RuntimeError(f'book {self.book_id!r} does not exist') from exc

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
            yield Info('debug', f'Createding ID mapping: {id!r}')
            oid = get_legacy_id(id)
            if oid and oid not in self.oid_to_id:
                self.id_to_oid[id] = oid
                self.oid_to_id[oid] = id
                yield Info('debug', f'Created ID mapping: {id!r} => {oid!r}')
            else:
                nonconvertable_ids.append(id)

        # generate for non-convertable IDs
        for id in nonconvertable_ids:
            oid = generate_unique_id(id)
            self.id_to_oid[id] = oid
            self.oid_to_id[oid] = id
            yield Info('debug', f'Created ID mapping: {id!r} => {oid!r} (new)')

    def _generate_directory_mapping(self, book):
        for id, oid in self.id_to_oid.items():
            index = book.meta[id].get('index', '')
            if not index.endswith('/index.html'):
                continue

            dsrc = os.path.join(book.data_dir, os.path.dirname(index), '')
            self.path_to_oid[os.path.normcase(dsrc)] = oid
            yield Info('debug', f'Created directory mapping {dsrc!r} => {oid!r}')

    def _generate_rdf(self, book):
        def make_meta_node(id, meta):
            yield Info('debug', f'Generating meta node for {id!r}')

            oid = self.id_to_oid[id]
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
            yield Info('debug', f'Generating TOC node for {id!r}')

            node = etree.SubElement(root, f'{RDF}Seq')
            if id == book.ROOT_ITEM_ID:
                node.attrib[f'{RDF}about'] = 'urn:scrapbook:root'
            else:
                oid = self.id_to_oid[id]
                node.attrib[f'{RDF}about'] = f'urn:scrapbook:item{oid}'

            for ref_id in book.toc.get(id, []):
                if ref_id in seen_in_toc:
                    yield Info('debug', f'Skipped adding {ref_id!r} under {id!r} (referenced)')
                    continue

                yield Info('debug', f'Adding {ref_id!r} under {id!r}')
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

        seen_in_toc = {book.ROOT_ITEM_ID}
        yield from make_toc_node(book.ROOT_ITEM_ID)

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
            yield Info('debug', f'Copying data files for {id!r} => {oid!r}')
            type = book.meta[id].get('type', '')
            if type in book.ITEM_TYPES_WITH_OPTIONAL_INDEX:
                yield Info('debug', f'Skipped copying data for {id!r}: type is {type!r}')
                continue

            index = book.meta[id].get('index', '')
            if not index:
                yield Info('debug', f'Skipped copying data for {id!r}: no index')
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
                    util.fs.zip_extract(fsrc, fdst)
                elif util.is_maff(index):
                    fsrc = os.path.normpath(os.path.join(book.data_dir, index))
                    fdst = os.path.join(self.output, 'data', oid)
                    pages = util.get_maff_pages(fsrc)
                    if len(pages) == 0:
                        yield Info('error', f'Failed to copy data for {id!r}: no page in MAFF archive')
                        continue
                    else:
                        if len(pages) > 1:
                            yield Info('warn', f'{id!r}: only the first web page in MAFF archive can be copied')
                        page = pages[0]
                        topdir, _, _ = page.indexfilename.partition('/')

                    os.makedirs(os.path.dirname(fdst), exist_ok=True)
                    util.fs.zip_extract(fsrc, fdst, topdir)
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
                yield Info('error', f'Failed to copy data for {id!r}: {exc}', exc=exc)

            if type == 'postit':
                yield Info('debug', f'Converting data file for {id!r} (type={type!r})')
                file = os.path.join(self.output, 'data', oid, 'index.html')
                try:
                    content = book.load_postit_file(file)
                except OSError as exc:
                    yield Info('error', f"Failed to convert 'index.html' for {id!r}: {exc.strerror}", exc=exc)
                else:
                    with open(file, 'w', encoding='UTF-8') as fh:
                        fh.write(f"""\
<html><head><meta http-equiv="Content-Type" content="text/html;Charset=UTF-8"></head><body><pre>
{content}
</pre></body></html>""")
            elif self.data_files:
                yield Info('debug', f'Converting data files for {id!r} (type={type!r})')
                index_dir = os.path.join(self.output, 'data', oid)
                for root, _dirs, files in os.walk(index_dir):
                    for file in files:
                        if HTML_FILE_FILTER.search(file):
                            file = os.path.join(root, file)
                            yield Info('debug', f'Checking: {file!r}...')
                            try:
                                conv = ConvertHtmlFile(file)
                                conv.run()
                            except Exception as exc:
                                traceback.print_exc()
                                yield Info('error', f'Failed to convert {file!r} for {id!r}: {exc}', exc=exc)

    def _handle_item_icon(self, book, id):
        yield Info('debug', f'Checking icon for {id!r}')
        icon = book.meta[id].get('icon', '')

        if not icon:
            # return moz_icon if defined
            moz_icon_url = book.meta[id].get('icon-moz')
            if moz_icon_url:
                yield Info('debug', f'Use moz-icon URL from property for {id!r}: {moz_icon_url!r}')
                return moz_icon_url

            # generate moz-icon:// for files
            if book.meta[id].get('type', '') == 'file':
                index = book.meta[id].get('index', '')
                indexfile = os.path.normpath(os.path.join(book.data_dir, index))
                targetfile = util.get_meta_refreshed_file(indexfile)
                if targetfile:
                    moz_icon_url = f'moz-icon://{quote(os.path.basename(targetfile))}?size=16'
                    yield Info('debug', f'Generated moz-icon URL for {id!r}: {moz_icon_url!r}')
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
            self.icons_to_cache[file_ci] = (file, fdst)
            yield Info('debug', f'Created icon file mapping (cache): {file!r} => {fdst!r}')
            return f'resource://scrapbook/icon/{pathname2url(subpath)}'

        # if inside data folder
        if file_ci.startswith(os.path.normcase(book.data_dir)):
            # if under an item folder, map to legacy item folder
            for path, oid in self.path_to_oid.items():
                if file_ci.startswith(path):
                    subpath = os.path.relpath(file, path)
                    fdst = os.path.join(self.output, 'data', oid, subpath)
                    self.icons_to_cache[file_ci] = (file, fdst)
                    yield Info('debug', f'Created icon file mapping (item): {file!r} => {fdst!r}')
                    return f'resource://scrapbook/data/{oid}/{pathname2url(subpath)}'

            # otherwise, map to sub-data-directory path
            subpath = os.path.relpath(file, book.data_dir)
            fdst = os.path.join(self.output, 'data', subpath)
            self.icons_to_cache[file_ci] = (file, fdst)
            yield Info('debug', f'Created icon file mapping (data): {file!r} => {fdst!r}')
            return f'resource://scrapbook/data/{pathname2url(subpath)}'

        # record icons outside of "data" folder to copy later
        subpath = os.path.relpath(file, book.top_dir)
        fdst = os.path.join(self.output, subpath)
        self.icons_to_cache[file_ci] = (file, fdst)
        yield Info('debug', f'Created icon file mapping: {file!r} => {fdst!r}')
        return f'resource://scrapbook/{pathname2url(subpath)}'

    def _copy_icon_files(self):
        for fsrc, fdst in self.icons_to_cache.values():
            yield Info('debug', f'Copying icon {fsrc!r} => {fdst!r}')
            if not os.path.exists(fdst):
                os.makedirs(os.path.dirname(fdst), exist_ok=True)
                shutil.copy2(fsrc, fdst)


class ConvertHtmlFile(HtmlRewriter):
    def rewrite(self, markups):
        markups, _ = self.convert(markups)
        return markups

    def convert(self, markups, start=0, endtag=None):
        rv = []
        i = start
        while True:
            try:
                markup = markups[i]
            except IndexError:
                break

            if markup.type == 'starttag':
                # pass-through special context tags
                if markup.tag in ('template', 'svg', 'math'):
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023
                    for j in range(i, iend + 1):
                        rv.append(markups[j])
                    i = iend + 1
                    continue

                # handle annotations
                type = markup.getattr('data-scrapbook-elem')

                # linemarker / inline
                if type == 'linemarker':
                    id = markup.getattr('data-scrapbook-id')
                    title = markup.getattr('title')
                    style = markup.getattr('style')

                    tag = 'span'
                    attrs = {
                        'data-sb-id': id,
                        'data-sb-obj': 'inline' if title else 'linemarker',
                        'class': ['scrapbook-inline' if title else 'linemarker-marked-line'],
                    }

                    if style:
                        attrs['style'] = style

                    if title:
                        attrs['title'] = title

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                    ))

                    _rv, _i = self.convert(markups, i + 1, markup.endtag)
                    rv.extend(_rv)
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='endtag',
                        tag=tag,
                    ))

                    i = _i + 1
                    self.changed = True
                    continue

                # freenote / sticky
                elif type == 'sticky' and 'styled' in markup.classes:
                    is_relative = 'relative' in markup.classes
                    is_plaintext = 'plaintext' in markup.classes

                    tag = 'div'
                    attrs = {
                        'data-sb-obj': 'freenote',
                        'style': None,
                    }

                    # style
                    attrs['style'] = ' '.join([
                        'cursor: help;',
                        'overflow: visible;',
                        ('margin: 16px auto; ' if is_relative else '') + 'border: 1px solid #CCCCCC;',
                        'border-top-width: 12px;',
                        'background: #FAFFFA;',
                        'opacity: 0.95;',
                        'padding: 0px;',
                        'z-index: 500000;',
                        'text-align: start;',
                        'font-size: small;',
                        'line-height: 1.2em;',
                        'word-wrap: break-word;',
                        f'position: {"static" if is_relative else "absolute"};',
                    ])

                    style = markup.getattr('style')
                    if style:
                        attrs['style'] += ' ' + style

                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                    ))

                    if is_plaintext:
                        iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023

                        last_child_i = i
                        for j in self.iterfind(markups, lambda x: x.type == 'endtag' and x != markup.endtag, i + 1, markup.endtag):  # noqa: B023
                            last_child_i = j
                        text = ''.join(str(d) for d in markups[last_child_i + 1:iend] if d.type == 'data')

                        for line in REGEX_LINEFEED.split(text):
                            rv.append(Markup(
                                is_xhtml=self.is_xhtml,
                                type='data',
                                data=line,
                                convert_charrefs=False,
                            ))
                            rv.append(MarkupTag(
                                is_xhtml=self.is_xhtml,
                                type='starttag',
                                tag='br',
                                attrs=[],
                                is_self_end=self.is_xhtml,
                            ))
                        rv.pop()  # pop an extra <br>

                        rv.append(MarkupTag(
                            is_xhtml=self.is_xhtml,
                            type='endtag',
                            tag=tag,
                        ))
                        i = iend + 1

                    else:
                        _rv, _i = self.convert(markups, i + 1, markup.endtag)
                        rv.extend(_rv)
                        rv.append(MarkupTag(
                            is_xhtml=self.is_xhtml,
                            type='endtag',
                            tag=tag,
                        ))

                        i = _i + 1

                    self.changed = True
                    continue

                # block-comment
                elif (type == 'sticky'
                      and 'styled' not in markup.classes
                      and 'relative' in markup.classes
                      and 'plaintext' in markup.classes
                      ):
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023

                    tag = 'div'
                    attrs = {
                        'class': ['scrapbook-block-comment'],
                        'style': markup.getattr('style'),
                    }

                    last_child_i = i
                    for j in self.iterfind(markups, lambda x: x.type == 'endtag' and x != markup.endtag, i + 1, markup.endtag):  # noqa: B023
                        last_child_i = j
                    text = ''.join(str(d) for d in markups[last_child_i + 1:iend] if d.type == 'data')

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                    ))
                    rv.append(Markup(
                        is_xhtml=self.is_xhtml,
                        type='data',
                        data=text,
                        convert_charrefs=False,
                    ))
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='endtag',
                        tag=tag,
                    ))

                    i = iend + 1
                    self.changed = True
                    continue

                # remove WebScrapBook-specific elements
                elif type in ('annotation-css', 'annotation-loader'):
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023
                    i = iend + 1
                    self.changed = True
                    continue

                else:
                    markup_changed = False
                    for j, attr_value in enumerate(markup.attrs):
                        attr, value = attr_value

                        # convert data-scrapbook-elem
                        if attr == 'data-scrapbook-elem':
                            markup.attrs[j] = ('data-sb-obj', type)
                            markup_changed = True

                        # convert id attribute
                        elif attr == 'data-scrapbook-id':
                            markup.attrs[j] = ('data-sb-id', value)
                            markup_changed = True

                    if markup_changed:
                        rv.append(MarkupTag(
                            is_xhtml=self.is_xhtml,
                            type='starttag',
                            tag=markup.tag,
                            attrs=markup.attrs,
                            is_self_end=markup.is_self_end,
                        ))

                        i += 1
                        self.changed = True
                        continue

            elif markup.type == 'endtag':
                if endtag is not None:
                    if markup == endtag:
                        break

            rv.append(markup)
            i += 1

        return rv, i


def run(input, output, book_id='', data_files=True):
    start = time.time()
    yield Info('info', 'conversion mode: WebScrapBook --> ScrapBook')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output)}')
    yield Info('info', f'book: {book_id!r}')
    yield Info('info', f'data-files: {data_files}')
    yield Info('info', '')

    try:
        conv = Converter(input, output, book_id=book_id, data_files=data_files)
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
