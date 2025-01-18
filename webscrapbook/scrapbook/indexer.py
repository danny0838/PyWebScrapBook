"""Generator to generate item metadata from files.
"""
import io
import os
import re
import shutil
import traceback
from base64 import b64encode
from datetime import datetime
from functools import partial
from urllib.error import URLError
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import pathname2url, url2pathname, urlopen

from lxml import etree

from .. import util
from .._polyfill import mimetypes, zipfile
from ..util import Info
from ..util.css import CssRewriter
from ..util.html import REGEX_ASCII_WHITESPACES, HtmlRewriter

HTML_TITLE_EXCLUDE_PARENTS = {
    'xmp',
    'svg',
    'template',
}

ALLOWED_ROOT_META_ATTRS = {
    'data-scrapbook-id',
    'data-scrapbook-title',
    'data-scrapbook-type',
    'data-scrapbook-create',
    'data-scrapbook-modify',
    'data-scrapbook-source',
    'data-scrapbook-icon',
    'data-scrapbook-comment',
    'data-scrapbook-charset',
}

REGEX_IE_DOC_COMMENT = re.compile(r'^\s*saved from url=\((\d+)\)(\S+)\s*')

REGEX_SF_DOC_COMMENT = re.compile(r'^\s+Page saved with SingleFile\s+url: (\S+)\s+saved date: ([^()]+)')

REGEX_MAOXIAN_DOC_COMMENT = re.compile(r'^\s*OriginalSrc: (\S+)')

REGEX_JS_DATE = re.compile(r'^([^()]+)')

COMMON_MIME_EXTENSION = {
    'application/octet-stream': '',
    'text/html': '.html',
    'application/xhtml+xml': '.xhtml',
    'image/svg+xml': '.svg',
    'image/jpeg': '.jpg',
    'audio/mpeg': '.mp3',
    'audio/ogg': '.oga',
    'video/mpeg': '.mpeg',
    'video/mp4': '.mp4',
    'video/ogg': '.ogv',
    'application/ogg': '.ogx',
}

SUPPORT_FOLDER_SUFFIXES = ['.files', '_files']


def generate_item_title(book, id):
    # infer from source
    if book.meta[id].get('source'):
        parts = urlsplit(book.meta[id].get('source'))
        if parts.scheme:
            title = os.path.basename(unquote(parts.path))
            if title:
                return title

    return None


def generate_item_create(book, id):
    # infer from standard timestamp ID
    dt = util.id_to_datetime(id)
    if dt:
        return util.datetime_to_id(dt)

    # infer from ctime of index file
    index = book.meta[id].get('index')
    if index:
        file = os.path.join(book.data_dir, index)
        try:
            ts = os.stat(file).st_ctime
        except OSError:
            pass
        else:
            dt = datetime.fromtimestamp(ts)
            return util.datetime_to_id(dt)

    # infer from modify
    modify = book.meta[id].get('modify')
    if modify:
        return modify


def generate_item_modify(book, id):
    # infer from mtime of index file
    index = book.meta[id].get('index')
    if index:
        file = os.path.join(book.data_dir, index)
        try:
            ts = os.stat(file).st_mtime
        except OSError:
            pass
        else:
            dt = datetime.fromtimestamp(ts)
            return util.datetime_to_id(dt)

    # infer from create (and then ID)
    create = book.meta[id].get('create')
    if create:
        return create


def iter_title_elems(tree):
    """Iterate over valid title elements."""
    def check(elem):
        p = elem.getparent()
        while p is not None:
            if p.tag in HTML_TITLE_EXCLUDE_PARENTS:
                return False
            p = p.getparent()
        return True

    for elem in tree.iter('title'):
        if check(elem):
            yield elem


def iter_favicon_elems(tree):
    """Iterate over valid favicon elements."""
    for elem in tree.iter('link'):
        if 'icon' in elem.attrib.get('rel', '').lower().split():
            yield elem


def mime_to_extension(mime):
    """Fix extension for some common MIME types.

    For example, Python may pick '.xht' instead of '.xhtml' as the primary
    extension for 'application/xhtml+xml'. This translates some common MIME
    types to a fixed mapped extension for better interoperability.
    """
    try:
        return COMMON_MIME_EXTENSION[mime]
    except KeyError:
        return mimetypes.guess_extension(mime) or ''


class Indexer:
    """A class that generates item metadata for files.
    """
    def __init__(self, book, *,
                 handle_ie_meta=True,
                 handle_singlefile_meta=True,
                 handle_savepagewe_meta=True,
                 handle_maoxian_meta=True,
                 ):
        self.book = book
        self.handle_ie_meta = handle_ie_meta
        self.handle_singlefile_meta = handle_singlefile_meta
        self.handle_savepagewe_meta = handle_savepagewe_meta
        self.handle_maoxian_meta = handle_maoxian_meta

    def run(self, files):
        self.book.load_meta_files()

        indexed = {}
        for file in files:
            id = yield from self._index_file(file)
            if id:
                yield Info('info', f'Added item {id!r} for {self.book.get_subpath(file)!r}.')
                indexed[id] = True

        return indexed

    def _index_file(self, file):
        subpath = self.book.get_subpath(file)
        yield Info('debug', f'Indexing {subpath!r}...')

        if not os.path.isfile(file):
            yield Info('error', f'File {subpath!r} does not exist.')
            return None

        _, ext = os.path.splitext(file.lower())
        is_webpage = ext in self.book.ITEM_INDEX_ALLOWED_EXT

        if is_webpage:
            try:
                tree = self.book.get_tree_from_index_file(file)
                if tree is None:
                    raise ValueError('document is empty')

                tree_root = tree.getroot()
                if tree_root is None:
                    raise ValueError('no root element')
                if tree_root.tag not in ('html', '{http://www.w3.org/2000/svg}svg'):
                    raise ValueError('invalid root element')
            except Exception as exc:
                yield Info('error', f'Failed to read file {subpath!r}: {exc}', exc=exc)
                return None

        # prepare meta
        # use empty create and modify to prevent auto-generated by book.add_item()
        meta = {
            'create': '',
            'modify': '',
        }

        if is_webpage:
            # attempt to load metadata generated by certain applications
            if self.handle_ie_meta:
                self._handle_ie_meta(meta, tree_root)

            if self.handle_singlefile_meta:
                self._handle_singlefile_meta(meta, tree_root)

            if self.handle_savepagewe_meta:
                self._handle_savepagewe_meta(meta, tree_root)

            if self.handle_maoxian_meta:
                self._handle_maoxian_meta(meta, tree_root)

            # merge properties from [data-scrapbook-*] attributes of the root
            for key, value in tree_root.attrib.items():
                if key in ALLOWED_ROOT_META_ATTRS:
                    meta[key[15:]] = value

        # id
        id = meta.get('id')
        if id is not None:
            # if explicitly specified in html attributes, use it or fail out.
            if id in self.book.meta:
                yield Info('error', f'Specified ID {id!r} is already used.')
                return None

            if id in self.book.SPECIAL_ITEM_ID:
                yield Info('error', f'Specified ID {id!r} is invalid.')
                return None

        else:
            # Take base filename as id if it corresponds to standard timestamp
            # format and not used; otherwise generate a new one.
            basepath = os.path.relpath(file, self.book.data_dir)
            basename = os.path.basename(basepath)
            if basename == 'index.html':
                basename = os.path.basename(os.path.dirname(basepath))
            id, _ = os.path.splitext(basename)

            if util.id_to_datetime(id) and id not in self.book.meta:
                meta['id'] = id

        # add to book
        new_items = self.book.add_item(meta, None)
        id, meta = next(iter(new_items.items()))

        # index
        meta['index'] = os.path.relpath(file, self.book.data_dir).replace('\\', '/')

        # type
        if meta.get('type') is None:
            meta['type'] = '' if is_webpage else 'file'

        # title
        if meta.get('title') is None:
            title = None
            if is_webpage:
                title_elem = next(iter_title_elems(tree), None)
                if title_elem is not None:
                    try:
                        title = (
                            (title_elem.text or '')
                            + ''.join(etree.tostring(e, encoding='unicode') for e in title_elem)
                        )
                    except UnicodeDecodeError as exc:
                        yield Info('error', f'Failed to extract title for {id!r}: {exc}', exc=exc)
            if not title or not title.strip():
                title = generate_item_title(self.book, id)
            meta['title'] = title or ''

        # create
        if not meta.get('create'):
            meta['create'] = generate_item_create(self.book, id) or ''

        # modify
        if not meta.get('modify'):
            meta['modify'] = generate_item_modify(self.book, id) or ''

        # icon
        if meta.get('icon') is None:
            if is_webpage:
                try:
                    favicon_elem = next(iter_favicon_elems(tree))
                except StopIteration:
                    pass
                else:
                    meta['icon'] = favicon_elem.attrib.get('href', '')

        generator = FavIconCacher(self.book, cache_archive=True)
        yield from generator.run([id])

        return id

    def _handle_ie_meta(self, meta, root):
        doc_comment = root.getprevious()

        if doc_comment is None:
            return

        if doc_comment.tag != etree.Comment:
            return

        m = REGEX_IE_DOC_COMMENT.search(doc_comment.text)
        if m is None:
            return

        length = m.group(1)
        source = m.group(2)
        try:
            if len(source) == int(length, 10):
                meta['source'] = source
        except ValueError:
            pass

    def _handle_singlefile_meta(self, meta, root):
        try:
            doc_comment = root[0]
        except IndexError:
            return

        if doc_comment.tag != etree.Comment:
            return

        m = REGEX_SF_DOC_COMMENT.search(doc_comment.text)
        if m is None:
            return

        source = m.group(1)
        date_str = m.group(2)
        dt = datetime.strptime(date_str, '%a %b %d %Y %H:%M:%S GMT%z ')

        meta['source'] = source
        meta['create'] = util.datetime_to_id(dt)

    def _handle_savepagewe_meta(self, meta, root):
        node = root.find('.//meta[@name="savepage-url"][@content]')
        if node is not None:
            meta['source'] = node.attrib['content']

        node = root.find('.//meta[@name="savepage-title"][@content]')
        if node is not None:
            meta['title'] = node.attrib['content']

        node = root.find('.//meta[@name="savepage-date"][@content]')
        if node is not None:
            m = REGEX_JS_DATE.match(node.attrib['content'])
            if m:
                dt = datetime.strptime(m.group(1), '%a %b %d %Y %H:%M:%S GMT%z ')
                meta['create'] = util.datetime_to_id(dt)

    def _handle_maoxian_meta(self, meta, root):
        try:
            doc_comment = root[0]
        except IndexError:
            return

        if doc_comment.tag != etree.Comment:
            return

        m = REGEX_MAOXIAN_DOC_COMMENT.search(doc_comment.text)
        if m is None:
            return

        source = m.group(1)

        meta['source'] = source


class FavIconCacher:
    def __init__(self, book, cache_url=True, cache_archive=False, cache_file=False):
        self.book = book
        self.cache_url = cache_url
        self.cache_archive = cache_archive
        self.cache_file = cache_file

        self.favicons = {}
        self.favicon_dir = os.path.normcase(os.path.join(self.book.tree_dir, 'favicon', ''))

    def run(self, item_ids=None):
        self.book.load_meta_files()
        cached = {}

        # handle all items if none specified
        for id in item_ids or self.book.meta:
            if id not in self.book.meta:
                continue

            cache_file = yield from self._cache_favicon(id)
            if cache_file:
                cached[id] = cache_file

        return cached

    def _cache_favicon(self, id):
        yield Info('debug', f'Caching favicon for {id!r}...')

        url = self.book.meta[id].get('icon')
        if not url:
            yield Info('debug', f'Skipped for {id!r}: no favicon to cache.')
            return None

        urlparts = urlsplit(url)

        index = self.book.meta[id].get('index', '')

        # absolute URL
        if urlparts.scheme:
            if self.cache_url:
                return (yield from self._cache_favicon_absolute_url(id, index, url))
            return None

        # skip protocol-relative URL
        if urlparts.netloc:
            return None

        # skip pure query or hash URL
        if not urlparts.path:
            return None

        if util.is_archive(index):
            if self.cache_archive:
                dataurl = yield from self._get_archive_favicon(id, index, url, unquote(urlparts.path))
                if dataurl:
                    return (yield from self._cache_favicon_absolute_url(id, index, dataurl, url))
            return None

        if self.cache_file:
            dataurl = yield from self._get_file_favicon(id, index, url, unquote(urlparts.path))
            if dataurl:
                return (yield from self._cache_favicon_absolute_url(id, index, dataurl, url))

        return None

    def _cache_favicon_absolute_url(self, id, index, url, source_url=None):
        """cache absolute URL (also works for data URL)
        """
        def verify_mime(mime):
            if not mime:
                yield Info('error', f'Unable to cache favicon {util.crop(source_url, 256)!r} for {id!r}: unknown MIME type')
                return False

            if not (mime.startswith('image/') or mime == 'application/octet-stream'):
                yield Info('error', f'Unable to cache favicon {util.crop(source_url, 256)!r} for {id!r}: invalid image MIME type {mime!r}')
                return False

            return True

        def cache_fh(fsrc):
            hash_ = util.checksum(fsrc)
            ext = mime_to_extension(mime)
            fdst = os.path.join(self.book.tree_dir, 'favicon', hash_ + ext)

            if os.path.isfile(fdst):
                yield Info('info', f'Use saved favicon for {util.crop(source_url, 256)!r} for {id!r} at {self.book.get_subpath(fdst)!r}.')
                return fdst

            yield Info('info', f'Saving favicon {util.crop(source_url, 256)!r} for {id!r} at {self.book.get_subpath(fdst)!r}.')
            fsrc.seek(0)
            os.makedirs(os.path.dirname(fdst), exist_ok=True)
            self.book.backup(fdst)
            with open(fdst, 'wb') as fw:
                shutil.copyfileobj(fsrc, fw)
            return fdst

        if source_url is None:
            source_url = url

        try:
            r = urlopen(url)
        except URLError as exc:
            yield Info('error', f'Unable to cache favicon {util.crop(source_url, 256)!r} for {id!r}: unable to fetch favicon URL.', exc=exc)
            return None
        except ValueError as exc:
            yield Info('error', f'Unable to cache favicon {util.crop(source_url, 256)!r} for {id!r}: unsupported or malformatted URL: {exc}', exc=exc)
            return None

        with r as r:
            mime, _ = util.parse_content_type(r.info()['content-type'])
            if not (yield from verify_mime(mime)):
                return None

            # get a seekable fh
            # r is not seekable for a general absolute URL
            # r is seekable for a data URL
            if r.seekable():
                fh = r.fp
            else:
                fh = io.BytesIO()
                shutil.copyfileobj(r, fh)

            cache_file = yield from cache_fh(fh)

        self.book.meta[id]['icon'] = util.get_relative_url(
            cache_file,
            os.path.join(self.book.data_dir, os.path.dirname(index)),
            path_is_dir=False,
        )
        return cache_file

    def _get_archive_favicon(self, id, index, url, subpath):
        """Convert in-zip relative favicon path to data URL.
        """
        file = os.path.join(self.book.data_dir, index)

        try:
            if util.is_maff(index):
                page = next(iter(util.get_maff_pages(file)), None)
                if not page:
                    raise RuntimeError('page not found in MAFF')

                refpath = page.indexfilename
                if not refpath:
                    raise RuntimeError('index file not found in MAFF')

                subpath = os.path.dirname(refpath) + '/' + subpath

            try:
                with zipfile.ZipFile(file) as zh:
                    bytes_ = zh.read(subpath)
            except OSError as exc:
                raise RuntimeError(exc.strerror) from exc
        except Exception as exc:
            yield Info('error', f'Failed to read archive favicon {util.crop(url, 256)!r} for {id!r}: {exc}', exc=exc)
            return None

        mime, _ = mimetypes.guess_type(subpath)
        mime = mime or 'application/octet-stream'
        return f'data:{mime};base64,{b64encode(bytes_).decode("ascii")}'

    def _get_file_favicon(self, id, index, url, subpath):
        """Convert relative favicon path to data URL.
        """
        file = os.path.normpath(os.path.join(self.book.data_dir, index, '..', subpath))

        # skip if already in favicon dir
        if os.path.normcase(file).startswith(self.favicon_dir):
            yield Info('debug', f'Skipped favicon {util.crop(url, 256)!r} for {id!r}: already in favicon folder')
            return None

        try:
            with open(file, 'rb') as fh:
                bytes_ = fh.read()
        except OSError as exc:
            yield Info('error', f'Failed to read archive favicon {util.crop(url, 256)!r} for {id!r}: {exc.strerror}', exc=exc)

        mime, _ = mimetypes.guess_type(subpath)
        mime = mime or 'application/octet-stream'
        return f'data:{mime};base64,{b64encode(bytes_).decode("ascii")}'


class SingleHtmlConverter(HtmlRewriter):
    REGEX_SRCSET = re.compile(r"""(\s*)([^ ,][^ ]*[^ ,])(\s*(?: [^ ,]+)?\s*(?:,|$))""")

    def __init__(self, *args, is_svg=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.is_svg = is_svg

        if self.file:
            if is_svg is None:
                self.is_svg = util.is_svg(self.file)

        self.html_converter = SingleHtmlConverter
        self.css_converter = SingleHtmlCssConverter

    def run(self):
        """Overwrite parent to return rewritten HTML instead.
        """
        self.last_html_encoding = None

        markups = self.load(self.file)
        markups = self.rewrite(markups)
        return ''.join(str(m) for m in markups if not m.hidden)

    def rewrite(self, markups):
        def update_context():
            nonlocal context
            context = 'html'
            for tag in stack:
                if tag in {'template', 'svg', 'math'}:
                    context = tag
                    break

        # special handling for SVG
        if self.is_svg:
            return self.rewrite_svg(markups)

        # reset base_url according to the first base[href] element
        for markup in markups:
            if markup.type == 'starttag':
                if markup.tag == 'base':
                    url = markup.getattr('href')
                    if url is not None:
                        self.base_url = urljoin(self.base_url, url)
                    break

        stack = []
        context = 'html'
        i = 0
        while True:
            try:
                markup = markups[i]
            except IndexError:
                break

            if markup.type == 'starttag':
                stack.append(markup.tag)
                update_context()

                if context == 'html':
                    self.rewrite_markup(markup)
                elif context == 'svg':
                    self.rewrite_markup_svg(markup)

            elif markup.type == 'endtag':
                stack.pop()
                update_context()

            elif markup.type == 'data':
                if context in {'html', 'svg'}:
                    # rewrite content of style element
                    try:
                        last_markup = markups[i - 1]
                    except KeyError:
                        pass
                    else:
                        if last_markup.type == 'starttag' and last_markup.tag == 'style':
                            markup.data = self.rewrite_style_text(markup.data)
                            markup.src = None

            i += 1

        return markups

    def rewrite_svg(self, markups):
        i = 0
        while True:
            try:
                markup = markups[i]
            except IndexError:
                break

            if markup.type == 'starttag':
                self.rewrite_markup_svg(markup)

            elif markup.type == 'data':
                # rewrite content of style element
                try:
                    last_markup = markups[i - 1]
                except KeyError:
                    pass
                else:
                    if last_markup.type == 'starttag' and last_markup.tag == 'style':
                        markup.data = self.rewrite_style_text(markup.data)
                        markup.src = None

            i += 1

        return markups

    def rewrite_markup(self, markup):
        self.rewrite_attr(markup, 'style', self.rewrite_style_attr)
        self.rewrite_attr(markup, 'data-scrapbook-shadowdom', self.rewrite_shadowdom_attr)

        if markup.tag == 'meta':
            http_equiv = markup.getattr('http-equiv')
            if http_equiv and http_equiv.lower() == 'refresh':
                self.rewrite_attr(markup, 'content', self.rewrite_meta_refresh_content)
            return

        if markup.tag == 'link':
            rel = markup.getattr('rel')
            if rel:
                rels = REGEX_ASCII_WHITESPACES.split(rel)
                if 'stylesheet' in rels:
                    self.rewrite_attr(markup, 'href', partial(self.rewrite_url, rewrite_css=True))
                elif 'icon' in rels:
                    self.rewrite_attr(markup, 'href', self.rewrite_url)
            return

        if markup.tag in {'body', 'table', 'tr', 'th', 'td'}:
            self.rewrite_attr(markup, 'background', self.rewrite_url)
            return

        if markup.tag == 'frame':
            self.rewrite_attr(markup, 'src', partial(self.rewrite_url, rewrite_doc=True))
            return

        if markup.tag == 'iframe':
            self.rewrite_iframe(markup)
            return

        if markup.tag in {'a', 'area'}:
            self.rewrite_attr(markup, 'href', self.rewrite_url)
            return

        if markup.tag == 'script':
            self.rewrite_attr(markup, 'src', self.rewrite_url)
            return

        if markup.tag == 'img':
            self.rewrite_attr(markup, 'src', self.rewrite_url)
            self.rewrite_attr(markup, 'srcset', self.rewrite_srcset)
            return

        if markup.tag == 'audio':
            self.rewrite_attr(markup, 'src', self.rewrite_url)
            return

        if markup.tag == 'video':
            self.rewrite_attr(markup, 'src', self.rewrite_url)
            self.rewrite_attr(markup, 'poster', self.rewrite_url)
            return

        if markup.tag == 'source':
            self.rewrite_attr(markup, 'src', self.rewrite_url)
            self.rewrite_attr(markup, 'srcset', self.rewrite_srcset)
            return

        if markup.tag == 'track':
            self.rewrite_attr(markup, 'src', self.rewrite_url)
            return

        if markup.tag == 'embed':
            self.rewrite_attr(markup, 'src', self.rewrite_url)
            return

        if markup.tag == 'object':
            self.rewrite_attr(markup, 'data', partial(self.rewrite_url, rewrite_doc=True))
            return

        if markup.tag == 'applet':
            self.rewrite_attr(markup, 'code', self.rewrite_url)
            self.rewrite_attr(markup, 'archive', self.rewrite_url)
            return

        if markup.tag == 'input' and markup.getattr('type', '').lower() == 'image':
            self.rewrite_attr(markup, 'src', self.rewrite_url)
            return

    def rewrite_markup_svg(self, markup):
        self.rewrite_attr(markup, 'style', self.rewrite_style_attr)
        self.rewrite_attr(markup, 'href', self.rewrite_url)
        self.rewrite_attr(markup, 'xlink:href', self.rewrite_url)

    def rewrite_attr(self, markup, target_attr, callback):
        for i, attr_value in enumerate(markup.attrs):
            attr, value = attr_value
            if attr != target_attr:
                continue

            # there's no point to rewrite a boolean attribute
            if value is None:
                continue

            value_new = callback(value)
            if value_new != value:
                markup.attrs[i] = (attr, value_new)
                markup.src = None

    def remove_attr(self, markup, target_attr):
        attrs = []

        for attr_value in markup.attrs:
            attr, value = attr_value
            if attr == target_attr:
                markup.src = None
                continue

            attrs.append((attr, value))

        markup.attrs = attrs

    def rewrite_url(self, url, rewrite_doc=False, rewrite_css=False, meta_refresh=False):
        if meta_refresh:
            udst = urljoin(self.doc_url, url)
        else:
            udst = urljoin(self.base_url, url)

        urlparts = urlsplit(udst)

        # skip non-file URL
        if urlparts.scheme != 'file':
            return url

        fdst = url2pathname(urlparts.path)

        # query/hash only if targeting self
        if os.path.normcase(fdst) == os.path.normcase(url2pathname(urlsplit(self.doc_url).path)):
            return urlunsplit(('', '', '', urlparts.query, urlparts.fragment))

        if meta_refresh:
            return f'urn:scrapbook:convert:skip:url:{url}'

        mime, _ = mimetypes.guess_type(fdst)
        mime = mime or 'application/octet-stream'

        if rewrite_css:
            if udst in self.url_chain:
                return f'urn:scrapbook:convert:circular:url:{url}'

            try:
                conv = self.css_converter(fdst, url_chain=self.url_chain)
                content = conv.run()
                bytes_ = content.encode(conv.encoding)
                return f'data:{mime},{quote(bytes_)}'
            except OSError:
                return f'urn:scrapbook:convert:error:url:{url}'

        if rewrite_doc and util.mime_is_html(mime) or util.mime_is_svg(mime):
            if udst in self.url_chain:
                return f'urn:scrapbook:convert:circular:url:{url}'

            # handle possible meta refresh
            try:
                fdst_mr = util.get_meta_refreshed_file(fdst)
            except util.MetaRefreshError:
                return f'urn:scrapbook:convert:error:url:{url}'

            if fdst_mr:
                fdst = fdst_mr
                udst = urljoin('file:///', pathname2url(fdst))

                if udst in self.url_chain:
                    return f'urn:scrapbook:convert:circular:url:{url}'

                mime, _ = mimetypes.guess_type(fdst)
                mime = mime or 'application/octet-stream'

            if util.mime_is_html(mime) or util.mime_is_svg(mime):
                try:
                    conv = self.html_converter(fdst, url_chain=self.url_chain, parser=self.parser)
                    content = conv.run()
                    bytes_ = content.encode(conv.encoding)
                    self.last_html_encoding = conv.encoding
                    return f'data:{mime},{quote(bytes_)}'
                except OSError:
                    return f'urn:scrapbook:convert:error:url:{url}'

        try:
            with open(fdst, 'rb') as fh:
                bytes_ = fh.read()
        except OSError:
            return f'urn:scrapbook:converter:error:url:{url}'

        if util.is_compressible(mime):
            return f'data:{mime},{quote(bytes_)}'

        return f'data:{mime};base64,{b64encode(bytes_).decode("ascii")}'

    def rewrite_srcdoc(self, text):
        markups = self.loads(text)
        markups = self.rewrite(markups)
        return ''.join(str(m) for m in markups if not m.hidden)

    def rewrite_srcset(self, srcset):
        return self.REGEX_SRCSET.sub(self.rewrite_srcset_sub, srcset)

    def rewrite_srcset_sub(self, m):
        replacement = self.rewrite_url(m.group(2))
        return m.group(1) + replacement + m.group(3)

    def rewrite_style_text(self, text):
        conv = self.css_converter(ref_url=self.base_url, url_chain=self.url_chain)
        return conv.rewrite(
            text,
            rewrite_import_url=partial(conv.rewrite_url, rewrite_css=True),
            rewrite_font_face_url=conv.rewrite_url,
            rewrite_background_url=conv.rewrite_url,
        )

    def rewrite_style_attr(self, text):
        conv = self.css_converter(ref_url=self.base_url, url_chain=self.url_chain)
        return conv.rewrite(
            text,
            rewrite_background_url=conv.rewrite_url,
        )

    def rewrite_meta_refresh_content(self, text):
        time, url, context = util.parse_meta_refresh_content(text)
        if time is not None:
            url = self.rewrite_url(url, meta_refresh=True)
            return f'{time}; url={url}'
        return text

    def rewrite_iframe(self, markup):
        srcdoc = markup.getattr('srcdoc')

        if srcdoc is not None:
            self.rewrite_attr(markup, 'srcdoc', self.rewrite_srcdoc)
            self.remove_attr(markup, 'src')
            return

        for i, attr_value in enumerate(markup.attrs):
            attr, value = attr_value
            if attr != 'src':
                continue

            # there's no point to rewrite a boolean attribute
            if value is None:
                continue

            value_new = self.rewrite_url(value, rewrite_doc=True)
            if value_new != value:
                as_srcdoc = False
                if value_new.startswith('data:'):
                    bytes_, mime, _ = util.parse_datauri(value_new)
                    if util.mime_is_html(mime) and not util.mime_is_xhtml(mime):
                        markup.attrs[i] = ('srcdoc', bytes_.decode(self.last_html_encoding or 'UTF-8'))
                        as_srcdoc = True
                if not as_srcdoc:
                    markup.attrs[i] = (attr, value_new)
                markup.src = None

    def rewrite_shadowdom_attr(self, text):
        markups = self.loads(text)
        markups = self.rewrite(markups)
        return ''.join(str(m) for m in markups if not m.hidden)


class SingleHtmlCssConverter(CssRewriter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.css_converter = SingleHtmlCssConverter

    def run(self):
        return super().run(
            rewrite_import_url=partial(self.rewrite_url, rewrite_css=True),
            rewrite_font_face_url=self.rewrite_url,
            rewrite_background_url=self.rewrite_url,
        )

    def rewrite_url(self, url, rewrite_css=False):
        udst = urljoin(self.ref_url, url)

        urlparts = urlsplit(udst)

        # skip non-file URL
        if urlparts.scheme != 'file':
            return url

        fdst = url2pathname(urlparts.path)

        # query/hash only if targeting self
        if os.path.normcase(fdst) == os.path.normcase(url2pathname(urlsplit(self.ref_url).path)):
            return urlunsplit(('', '', urlparts.path, urlparts.query, urlparts.fragment))

        mime, _ = mimetypes.guess_type(fdst)
        mime = mime or 'application/octet-stream'

        if rewrite_css:
            if udst in self.url_chain:
                return f'urn:scrapbook:convert:circular:url:{url}'

            try:
                conv = self.css_converter(fdst, url_chain=self.url_chain)
                content = conv.run()
                bytes_ = content.encode(conv.encoding)
                return f'data:{mime},{quote(bytes_)}'
            except OSError:
                return f'urn:scrapbook:convert:error:url:{url}'

        try:
            with open(fdst, 'rb') as fh:
                bytes_ = fh.read()
        except OSError:
            return f'urn:scrapbook:converter:error:url:{url}'

        return f'data:{mime};base64,{b64encode(bytes_).decode("ascii")}'


class UnSingleHtmlConverter(SingleHtmlConverter):
    def __init__(self, *args, ref_file=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.ref_file = ref_file if ref_file is not None else self.file

        # bind ref_file to the constructor for derived conversions to inherit it
        self.html_converter = partial(UnSingleHtmlConverter, ref_file=self.ref_file)
        self.css_converter = partial(UnSingleHtmlCssConverter, ref_file=self.ref_file)

    def rewrite_url(self, url, rewrite_doc=False, rewrite_css=False, meta_refresh=False):
        if meta_refresh:
            udst = urljoin(self.doc_url, url)
        else:
            udst = urljoin(self.base_url, url)

        urlparts = urlsplit(udst)

        # skip non-data URL
        if urlparts.scheme != 'data':
            return url

        try:
            bytes_, mime, params = util.parse_datauri(url)
        except util.DataUriMalformedError:
            traceback.print_exc()
            return f'urn:scrapbook:convert:error:url:{url}'

        bytes_io = io.BytesIO(bytes_)

        if rewrite_css:
            try:
                conv = self.css_converter()
                text = conv.load(bytes_io)
                text = conv.rewrite(
                    text,
                    rewrite_import_url=partial(conv.rewrite_url, rewrite_css=True),
                    rewrite_font_face_url=conv.rewrite_url,
                    rewrite_background_url=conv.rewrite_url,
                )
                bytes_ = text.encode(conv.encoding)
                bytes_io = io.BytesIO(bytes_)
            except Exception:
                traceback.print_exc()
                return f'urn:scrapbook:convert:error:url:{url}'

        elif rewrite_doc and util.mime_is_html(mime) or util.mime_is_svg(mime):
            try:
                encoding = util.fix_codec(params['charset'])
            except KeyError:
                encoding = None
            try:
                conv = self.html_converter(
                    is_xhtml=util.mime_is_xhtml(mime),
                    is_svg=util.mime_is_svg(mime),
                    encoding=encoding, parser=self.parser)
                markups = conv.load(bytes_io)
                markups = conv.rewrite(markups)
                bytes_io = io.BytesIO()
                for markup in markups:
                    if not markup.hidden:
                        bytes_io.write(str(markup).encode(conv.encoding))
            except Exception:
                traceback.print_exc()
                return f'urn:scrapbook:convert:error:url:{url}'

        bytes_io.seek(0)
        sha = util.checksum(bytes_io)
        ext = mime_to_extension(mime)
        basename = f'{sha}{ext}'
        fdst = os.path.join(os.path.dirname(self.ref_file), basename)
        if not os.path.lexists(fdst):
            bytes_io.seek(0)
            with open(fdst, 'wb') as fh:
                shutil.copyfileobj(bytes_io, fh)

        return basename

    def rewrite_iframe(self, markup):
        srcdoc = markup.getattr('srcdoc')

        if srcdoc is not None:
            self.remove_attr(markup, 'src')

            for i, attr_value in enumerate(markup.attrs):
                attr, value = attr_value
                if attr != 'srcdoc':
                    continue

                if value is None:
                    value = ''

                content = self.rewrite_srcdoc(value)
                bytes_ = content.encode('UTF-8')
                dataurl = f'data:text/html;charset=utf-8,{quote(bytes_)}'
                value_new = self.rewrite_url(dataurl)
                markup.attrs[i] = ('src', value_new)
                markup.src = None

            return

        self.rewrite_attr(markup, 'src', partial(self.rewrite_url, rewrite_doc=True))


class UnSingleHtmlCssConverter(SingleHtmlCssConverter):
    def __init__(self, *args, ref_file=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.ref_file = ref_file if ref_file is not None else self.file

        # bind ref_file to the constructor for derived conversions to inherit it
        self.css_converter = partial(UnSingleHtmlCssConverter, ref_file=self.ref_file)

    def rewrite_url(self, url, rewrite_css=False):
        udst = urljoin(self.ref_url, url)

        urlparts = urlsplit(udst)

        # skip non-data URL
        if urlparts.scheme != 'data':
            return url

        try:
            bytes_, mime, params = util.parse_datauri(url)
        except util.DataUriMalformedError:
            traceback.print_exc()
            return f'urn:scrapbook:convert:error:url:{url}'

        bytes_io = io.BytesIO(bytes_)

        if rewrite_css:
            try:
                conv = self.css_converter()
                text = conv.load(bytes_io)
                text = conv.rewrite(
                    text,
                    rewrite_import_url=partial(conv.rewrite_url, rewrite_css=True),
                    rewrite_font_face_url=conv.rewrite_url,
                    rewrite_background_url=conv.rewrite_url,
                )
                bytes_ = text.encode(conv.encoding)
                bytes_io = io.BytesIO(bytes_)
            except Exception:
                traceback.print_exc()
                return f'urn:scrapbook:convert:error:url:{url}'

        bytes_io.seek(0)
        sha = util.checksum(bytes_io)
        ext = mime_to_extension(mime)
        basename = f'{sha}{ext}'
        fdst = os.path.join(os.path.dirname(self.ref_file), basename)
        if not os.path.lexists(fdst):
            bytes_io.seek(0)
            with open(fdst, 'wb') as fh:
                shutil.copyfileobj(bytes_io, fh)

        return basename
