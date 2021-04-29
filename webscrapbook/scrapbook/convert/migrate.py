import os
import shutil
import traceback
import re
import time
from datetime import datetime
from urllib.parse import urlsplit
from urllib.request import url2pathname

from ... import util
from ...util import Info
from ...util.html import Markup, MarkupTag
from ..host import Host


class Converter:
    def __init__(self, input, output, book_ids=None, *, convert_data_files=False, use_native_tags=False):
        self.input = input
        self.output = output
        self.book_ids = book_ids
        self.convert_data_files = convert_data_files
        self.use_native_tags = use_native_tags

    def run(self):
        if self.input != self.output:
            yield Info('info', 'Copying files...')
            self._copy_files()

        yield Info('info', 'Applying migration...')
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
        converter = ConvertLegacyDataFiles(book, use_native_tags=self.use_native_tags)
        yield from converter.run()


class ConvertLegacyDataFiles:
    """Convert data files with legacy data format.

    - Convert a web page with legacy annotations and chrome:// stylesheets or icons.
    - Convert a postit with legacy or other bad page wrapper.
    """
    HTML_FILE_FILTER = re.compile(r'^.+\.x?html$', re.I)

    def __init__(self, book, *, use_native_tags=False):
        self.book = book
        self.use_native_tags = use_native_tags

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
                    yield Info('error', f'Failed to convert "{index}" for "{id}": {exc.strerror}', exc=exc)
                else:
                    book.save_note_file(index_file, content)
            else:
                index_dir = os.path.normpath(os.path.dirname(os.path.join(book.data_dir, index)))
                for root, dirs, files in os.walk(index_dir):
                    for file in files:
                        if self.HTML_FILE_FILTER.search(file):
                            file = os.path.join(root, file)
                            yield Info('debug', f'Checking: {file}...')
                            try:
                                self._convert_legacy_html_file(file)
                            except Exception as exc:
                                traceback.print_exc()
                                yield Info('error', f'Failed to convert "{file}" for "{id}": {exc}', exc=exc)

    def _convert_legacy_html_file(self, file):
        markups = util.load_html_markups(file)
        encoding = util.load_html_markups.last_encoding
        is_xhtml = util.is_xhtml(file)
        converter = ConvertLegacyHtmlFile(markups,
            encoding=encoding,
            is_xhtml=is_xhtml,
            use_native_tags=self.use_native_tags,
            host=self.book.host,
            file=file,
            )
        converter.run()

        # save rewritten markups
        if converter.changed:
            with open(file, 'w', encoding=encoding, newline='\n') as fh:
                for markup in converter.output:
                    if not markup.hidden:
                        fh.write(str(markup))


class ConvertLegacyHtmlFile:
    PRE_WRAP_REGEX = re.compile(r'\bwhite-space:\s*pre-wrap\b', re.I)

    LEGACY_CLASSES_MAP = {
        'linemarker-marked-line': 'linemarker',
        'scrapbook-inline': 'inline',
        'scrapbook-sticky': 'sticky',
        'scrapbook-sticky-header': 'sticky-header',
        'scrapbook-sticky-footer': 'sticky-footer',
        'scrapbook-block-comment': 'block-comment',
        }
    LEGACY_FREENOTE_STYLE_POSITION_REGEX = re.compile(r'position:\s*(\w+);', re.I)
    LEGACY_POS_STYLE_REGEX = re.compile(r'(?:left|top|width|height):\s*[\d.]+px;', re.I)
    LEGACY_COMBINE_CSS = """\
body {
    margin: 0px;
    background-color: #FFFFFF;
}
cite.scrapbook-header {
    clear: both;
    display: block;
    padding: 3px 6px;
    font-family: "MS UI Gothic","Tahoma","Verdana","Arial","Sans-Serif","Helvetica";
    font-style: normal;
    font-size: 12px;
    background-color: InfoBackground;
    border: 1px solid ThreeDShadow;
}
cite.scrapbook-header img {
    vertical-align: middle;
}
cite.scrapbook-header a {
    color: InfoText;
    text-decoration: none;
}
cite.scrapbook-header a[href]:hover {
    color: #3388FF;
}
cite.scrapbook-header a.marked { font-weight: bold; }
cite.scrapbook-header a.combine  { color: blue; }
cite.scrapbook-header a.bookmark { color: limegreen; }
cite.scrapbook-header a.notex { color: rgb(80,0,32); }
"""
    LEGACY_COMBINE_ICON_MAP = {
        'chrome://scrapbook/skin/treefolder.png': 'fclose.png',
        'chrome://scrapbook/skin/treenote.png': 'postit.png',
        'chrome://scrapbook/skin/treenotex.png': 'note.png',
        'chrome://scrapbook/skin/treeitem.png': 'item.png',
        }

    # @TODO: better way to sync with WebScrapBook browser extension
    ANNOTATION_CSS = """\
[data-scrapbook-elem="linemarker"][title] {
  cursor: help;
}
[data-scrapbook-elem="sticky"] {
  display: block;
  overflow: auto;
}
[data-scrapbook-elem="sticky"].styled {
  position: absolute;
  z-index: 500000;
  opacity: .95;
  box-sizing: border-box;
  margin: 0;
  border: 1px solid #CCCCCC;
  border-top-width: 1.25em;
  border-radius: .25em;
  padding: .25em;
  min-width: 6em;
  min-height: 4em;
  background: #FAFFFA;
  box-shadow: .15em .15em .3em black;
  font: .875em/1.2 sans-serif;
  color: black;
  overflow-wrap: break-word;
  cursor: help;
}
[data-scrapbook-elem="sticky"].styled.relative {
  position: relative;
  margin: 16px auto;
}
[data-scrapbook-elem="sticky"].styled.plaintext {
  white-space: pre-wrap;
}
[data-scrapbook-elem="sticky"].dragging {
  opacity: .75;
  z-index: 2147483641;
}
"""
    ANNOTATION_JS = """\
function () {
  var w = window, d = document, r = d.documentElement, e;
  d.addEventListener('click', function (E) {
    if (r.hasAttribute('data-scrapbook-toolbar-active')) { return; }
    if (!w.getSelection().isCollapsed) { return; }
    e = E.target;
    if (e.matches('[data-scrapbook-elem="linemarker"]')) {
      if (e.title) {
        if (!confirm(e.title)) {
          E.preventDefault();
          E.stopPropagation();
        }
      }
    } else if (e.matches('[data-scrapbook-elem="sticky"]')) {
      if (confirm('%EditorDeleteAnnotationConfirm%')) {
        e.parentNode.removeChild(e);
        E.preventDefault();
        E.stopPropagation();
      }
    }
  }, true);
}
"""

    def __init__(self, markups, encoding='UTF-8',
            is_xhtml=False, use_native_tags=False, host=None, file=None):
        self.markups = markups
        self.encoding = encoding
        self.is_xhtml = is_xhtml
        self.use_native_tags = use_native_tags
        self.host = host
        self.file = file

        self.changed = False
        self.output = []

        self.combine_icons = {}
        self.map_id_markups = {}
        self.require_annotation_loader = False

    def run(self):
        for i, markup in enumerate(self.markups):
            if markup.type == 'starttag':
                # record map of data-sb-id to markup
                id = markup.getattr('data-sb-id')
                self.map_id_markups.setdefault(id, []).append(markup)

                # check and record requirement of loader
                type = markup.getattr('data-scrapbook-elem')
                if type == 'sticky' or (type == 'linemarker' and markup.getattr('title') is not None):
                    self.require_annotation_loader = True

        rv, _ = self.convert()

        # add annotation loader if needed
        if self.require_annotation_loader:
            markups = []

            markups.append(MarkupTag(
                type='starttag',
                tag='style',
                attrs=[
                    ('data-scrapbook-elem', 'annotation-css'),
                    ],
                ))
            markups.append(Markup(
                type='data',
                data=util.compress_code(self.ANNOTATION_CSS),
                is_cdata=True,
                ))
            markups.append(MarkupTag(
                type='endtag',
                tag='style',
                ))

            script = util.compress_code(self.ANNOTATION_JS)
            if self.host:
                script = util.format_string(script, self.host.get_i18n())
            script = f'({script})()'

            markups.append(MarkupTag(
                type='starttag',
                tag='script',
                attrs=[
                    ('data-scrapbook-elem', 'annotation-loader'),
                    ],
                ))
            markups.append(Markup(
                type='data',
                data=script,
                is_cdata=True,
                ))
            markups.append(MarkupTag(
                type='endtag',
                tag='script',
                ))

            pos = None
            for i in reversed(range(0, len(rv))):
                markup = rv[i]
                if markup.type == 'endtag':
                    if markup.tag == 'body':
                        pos = i
                        break

                    if markup.tag == 'html':
                        pos = i

            if pos is not None:
                rv = rv[:pos] + markups + rv[pos:]
            else:
                rv += markups

        self.output = rv

    def convert(self, start=0, endtag=None):
        rv = []
        i = start
        while True:
            try:
                markup = self.markups[i]
            except IndexError:
                break

            if markup.type == 'starttag':
                # handle legacy stylesheet
                if markup.tag == 'link' and markup.getattr('rel') == 'stylesheet':
                    href = markup.getattr('href')

                    # remove legacy annotation CSS
                    if href == 'chrome://scrapbook/skin/annotation.css':
                        i += 1
                        self.changed = True
                        continue

                    # convert legacy combine CSS
                    if href == 'chrome://scrapbook/skin/combine.css':
                        rv.append(MarkupTag(
                            type='starttag',
                            tag='style',
                            attrs=[
                                ('data-scrapbook-elem', 'custom-css'),
                                ],
                            ))
                        rv.append(Markup(
                            type='data',
                            data=util.compress_code(self.LEGACY_COMBINE_CSS),
                            is_cdata=True,
                            ))
                        rv.append(MarkupTag(
                            type='endtag',
                            tag='style',
                            ))

                        i += 1
                        self.changed = True
                        continue

                # handle legacy combine icon
                if markup.tag == 'img':
                    src_changed = False
                    for j, attr_value in enumerate(markup.attrs):
                        attr, value = attr_value
                        if attr == 'src' and value in self.LEGACY_COMBINE_ICON_MAP:
                            new_src = self._get_legacy_combine_icon_url(value)
                            if new_src is not None:
                                markup.attrs[j] = (attr, new_src)
                                src_changed = True
                                break

                    if src_changed:
                        rv.append(MarkupTag(
                            type='starttag',
                            tag=markup.tag,
                            attrs=markup.attrs,
                            ))

                        i += 1
                        self.changed = True
                        continue

                # handle annotations
                type = self._get_legacy_scrapbook_object_type(markup)

                if type in ('linemarker', 'inline'):
                    tag = 'span' if self.use_native_tags else 'scrapbook-linemarker'
                    attrs = {
                        'data-scrapbook-id': None,
                        'data-scrapbook-elem': 'linemarker',
                        'class': [],
                        }

                    # id
                    id = markup.getattr('data-sb-id')
                    new_id = None

                    if id is not None:
                        new_id = self._convert_legacy_scrapbook_elem_id(id)
                        try:
                            if markup == self.map_id_markups[id][0]:
                                attrs['class'].append('first')
                        except KeyError:
                            pass
                        try:
                            if markup == self.map_id_markups[id][-1]:
                                attrs['class'].append('last')
                        except KeyError:
                            pass

                    if new_id is not None:
                        attrs['data-scrapbook-id'] = new_id

                    # style
                    css = markup.getattr('style')
                    if css is not None:
                        attrs['style'] = css

                    # title
                    title = markup.getattr('title')
                    if title is not None:
                        attrs['title'] = title
                        self.require_annotation_loader = True

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                        ))

                    _rv, _i = self.convert(i + 1, markup.endtag)
                    rv.extend(_rv)
                    rv.append(MarkupTag(
                        type='endtag',
                        tag=tag,
                        ))

                    i = _i + 1
                    self.changed = True
                    continue

                elif type == 'freenote':
                    tag = 'div' if self.use_native_tags else 'scrapbook-sticky'
                    attrs = {
                        'data-scrapbook-elem': 'sticky',
                        'class': ['styled'],
                        }

                    # CSS
                    # @TODO: implement CSS parser for better error proof
                    css = markup.getattr('style')
                    if css is not None:
                        m = self.LEGACY_FREENOTE_STYLE_POSITION_REGEX.search(css)
                        if m and m.group(1).lower() == 'static':
                            attrs['class'].append('relative')

                        css_new = ' '.join(m.group(0) for m in self.LEGACY_POS_STYLE_REGEX.finditer(css))
                        if css_new:
                            attrs['style'] = css_new

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                        ))

                    _rv, _i = self.convert(i + 1, markup.endtag)
                    rv.extend(_rv)
                    rv.append(MarkupTag(
                        type='endtag',
                        tag=tag,
                        ))

                    i = _i + 1
                    self.changed = True
                    self.require_annotation_loader = True
                    continue

                elif type == 'sticky':
                    iend = self.find(lambda x: x == markup.endtag, i + 1, markup.endtag)

                    tag = 'div' if self.use_native_tags else 'scrapbook-sticky'
                    attrs = {
                        'data-scrapbook-elem': 'sticky',
                        'class': ['styled', 'plaintext'],
                        }
                    if 'scrapbook-sticky-relative' in markup.classes:
                        attrs['class'].append('relative')

                    # CSS
                    # @TODO: implement CSS parser for better error proof
                    css = markup.getattr('style')
                    if css is not None:
                        css_new = ' '.join(m.group(0) for m in self.LEGACY_POS_STYLE_REGEX.finditer(css))
                        if css_new:
                            attrs['style'] = css_new

                    # text content
                    textarea_i = self.find(lambda x: x.tag == 'textarea', i + 1, markup.endtag)
                    if textarea_i is not None:
                        # unsaved sticky: take textarea content
                        textarea_iend = self.find(lambda x: x == self.markups[textarea_i].endtag, textarea_i + 1, markup.endtag)
                        text = ''.join(str(d) for d in self.markups[textarea_i + 1:textarea_iend])
                    else:
                        last_child_i = i
                        for j in self.iterfind(lambda x: x.type == 'endtag' and x != markup.endtag, i + 1, markup.endtag):
                            last_child_i = j
                        text = ''.join(str(d) for d in self.markups[last_child_i + 1:iend] if d.type == 'data')

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                        ))
                    if text:
                        rv.append(Markup(
                            type='data',
                            data=text,
                            convert_charrefs=False,
                            ))
                    rv.append(MarkupTag(
                        type='endtag',
                        tag=tag,
                        ))

                    i = iend + 1
                    self.changed = True
                    self.require_annotation_loader = True
                    continue

                elif type == 'block-comment':
                    iend = self.find(lambda x: x == markup.endtag, i + 1, markup.endtag)

                    tag = 'div' if self.use_native_tags else 'scrapbook-sticky'
                    attrs = {
                        'data-scrapbook-elem': 'sticky',
                        'class': ['plaintext', 'relative'],
                        }

                    # CSS
                    css = markup.getattr('style')
                    if css:
                        if not self.PRE_WRAP_REGEX.search(css):
                            css += ' white-space: pre-wrap;'
                    else:
                        css = 'white-space: pre-wrap;'
                    attrs['style'] = css

                    # text content
                    textarea_i = self.find(lambda x: x.tag == 'textarea', i + 1, markup.endtag)
                    if textarea_i is not None:
                        # unsaved block-comment: take textarea content
                        textarea_iend = self.find(lambda x: x == self.markups[textarea_i].endtag, textarea_i + 1, markup.endtag)
                        text = ''.join(str(d) for d in self.markups[textarea_i + 1:textarea_iend])
                    else:
                        text = ''.join(str(d) for d in self.markups[i + 1:iend] if d.type == 'data')

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                        ))
                    if text:
                        rv.append(Markup(
                            type='data',
                            data=text,
                            convert_charrefs=False,
                            ))
                    rv.append(MarkupTag(
                        type='endtag',
                        tag=tag,
                        ))

                    i = iend + 1
                    self.changed = True
                    self.require_annotation_loader = True
                    continue

                else:
                    markup_changed = False
                    has_data_sb_obj = False
                    for j, attr_value in enumerate(markup.attrs):
                        attr, value = attr_value

                        # convert type attribute
                        if attr == 'data-sb-obj':
                            has_data_sb_obj = True
                            markup.attrs[j] = ('data-scrapbook-elem', type)
                            markup_changed = True

                        # convert id attribute
                        elif attr == 'data-sb-id':
                            markup.attrs[j] = ('data-scrapbook-id',  self._convert_legacy_scrapbook_elem_id(value))
                            markup_changed = True

                        # convert data-sb-orig-<attr>
                        elif attr.startswith('data-sb-orig-'):
                            attr = f'data-scrapbook-orig-attr-{attr[13:]}'
                            markup.attrs[j] = (attr, value)
                            markup_changed = True

                    if type and not has_data_sb_obj:
                        markup.attrs.append(('data-scrapbook-elem', type))
                        markup_changed = True

                    if markup_changed:
                        rv.append(MarkupTag(
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

    def find(self, filter, start=0, endtag=None):
        return next(self.iterfind(filter, start, endtag), None)

    def iterfind(self, filter, start=0, endtag=None):
        i = start
        while True:
            try:
                markup = self.markups[i]
            except IndexError:
                break

            if filter(markup):
                yield i

            if markup.type == 'endtag':
                if endtag is not None:
                    if markup == endtag:
                        break

            i += 1

    def _get_legacy_scrapbook_object_type(self, markup):
        type = markup.getattr('data-sb-obj')
        if type is None:
            for cls in markup.classes:
                if cls in self.LEGACY_CLASSES_MAP:
                    type = self.LEGACY_CLASSES_MAP[cls]
                    break
        return type

    def _get_legacy_combine_icon_url(self, src):
        if self.host is None or self.file is None:
            return None

        # attempt to load from cache
        try:
            return self.combine_icons[src]
        except KeyError:
            pass

        # save the icon under the root index dir
        root = os.path.dirname(self.file)
        filename, ext = os.path.splitext(os.path.basename(urlsplit(src).path))
        fsrc = self.host.get_static_file(self.LEGACY_COMBINE_ICON_MAP[src])
        fdst = os.path.join(root, f'{filename}{ext}')
        i = 1
        while os.path.lexists(fdst):
            fdst = os.path.join(root, f'{filename}-{i}{ext}')
            i += 1

        shutil.copyfile(fsrc, fdst)

        new_src = self.combine_icons[src] = util.get_relative_url(
            fdst,
            self.file,
            path_is_dir=False,
            start_is_dir=False,
            )

        return new_src

    def _convert_legacy_scrapbook_elem_id(self, id):
        """Convert legacy sb-obj-id (JavaScript timestamp) to WebScrapBook id.
        """
        try:
            dt = datetime.fromtimestamp(int(id) / 1000.0)
            return util.datetime_to_id(dt)
        except Exception:
            return id


def run(input, output, book_ids=None, *, convert_data_files=False, use_native_tags=False):
    start = time.time()
    book_ids_text = ', '.join(f'"{id}"' for id in book_ids) if book_ids else '(all)'
    yield Info('info', 'migrating:')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output) if output is not None else "(in-place)"}')
    yield Info('info', f'book(s): {book_ids_text}')
    yield Info('info', f'convert data files: {convert_data_files}')
    yield Info('info', f'use native tags: {use_native_tags}')
    yield Info('info', '')

    if output is None:
        output = input

    try:
        conv = Converter(input, output, book_ids=book_ids,
            convert_data_files=convert_data_files,
            use_native_tags=use_native_tags,
            )
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
