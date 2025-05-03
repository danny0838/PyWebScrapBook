"""Generator of fulltext cache and/or static site pages.
"""
import html
import io
import itertools
import os
import re
import shutil
import time
import traceback
from collections import UserDict, namedtuple
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import partial
from urllib.parse import quote, unquote, urljoin, urlsplit

import jinja2
from lxml import etree

from .. import util
from .._polyfill import mimetypes, zipfile
from ..util import Info
from .host import Host


class MutatingDict(UserDict):
    """Support adding during dict iteration.
    """
    def __init__(self, *args, **kwargs):
        self._keys = []

        # this calls __setitem__ internally
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        if key not in self:
            self._keys.append(key)
        super().__setitem__(key, value)

    def __iter__(self):
        return iter(self._keys)

    def __delitem__(self, key):
        return NotImplemented


StaticIndexItem = namedtuple(
    'StaticIndexItem',
    ('event', 'level', 'id', 'type', 'marked', 'title', 'url', 'icon', 'source', 'comment'),
    defaults=(None, None, None, None, None, None, None, None))


class StaticSiteGenerator():
    """Main class for static site pages generation.
    """
    RESOURCES = {
        'icon/toggle.png': 'toggle.png',
        'icon/search.png': 'search.png',
        'icon/collapse.png': 'collapse.png',
        'icon/expand.png': 'expand.png',
        'icon/external.png': 'external.png',
        'icon/comment.png': 'comment.png',
        'icon/item.png': 'item.png',
        'icon/fclose.png': 'fclose.png',
        'icon/fopen.png': 'fopen.png',
        'icon/file.png': 'file.png',
        'icon/note.png': 'note.png',
        'icon/postit.png': 'postit.png',
    }
    ITEM_TYPE_ICON = {
        '': 'icon/item.png',
        'folder': 'icon/fclose.png',
        'file': 'icon/file.png',
        'image': 'icon/file.png',
        'note': 'icon/note.png',  # ScrapBook X notex
        'postit': 'icon/postit.png',  # ScrapBook X note
    }

    def __init__(self, book, *, static_index=None):
        self.host = book.host
        self.book = book
        self.locale = self.host.config['app']['locale']
        self.rss = bool(self.book.config['rss_root'])

        if static_index is None:
            static_index = self.book.config['static_index']
        self.static_index = static_index

        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.host.templates),
            autoescape=jinja2.select_autoescape(['html']),
        )
        self.template_env.globals.update({
            'format_string': util.format_string,
            'i18n': self.host.get_i18n(self.locale),
            'bookname': book.name,
        })

        book.load_meta_files()
        book.load_toc_files()

    def run(self):
        yield Info('info', 'Generating static site pages...')

        # copy resource files
        for dst, src in self.RESOURCES.items():
            yield from self._generate_resource_file(src, dst)

        # generate static site pages
        index_kwargs = {
            'rss': self.rss,
            'data_dir': util.get_relative_url(self.book.data_dir, self.book.tree_dir),
            'default_icons': self.ITEM_TYPE_ICON,
            'meta_cnt': max(sum(1 for _ in self.book.iter_meta_files()), 1),
            'toc_cnt': max(sum(1 for _ in self.book.iter_toc_files()), 1),
        }

        if self.static_index:
            yield from self._generate_page(
                'index.html', 'static_index.html', filename='index',
                static_index=self._generate_static_index(), **index_kwargs,
            )

        yield from self._generate_page(
            'map.html', 'static_map.html', filename='map',
            static_index=None, **index_kwargs,
        )

        yield from self._generate_page('frame.html', 'static_frame.html')

        yield from self._generate_page(
            'search.html', 'static_search.html',
            path=util.get_relative_url(self.book.top_dir, self.book.tree_dir),
            data_dir=util.get_relative_url(self.book.data_dir, self.book.top_dir),
            tree_dir=util.get_relative_url(self.book.tree_dir, self.book.top_dir),
            index=self.book.config['index'],
        )

    def _generate_resource_file(self, src, dst):
        yield Info('debug', f'Checking resource file {dst!r}')
        fsrc = self.host.get_static_file(src)
        fdst = os.path.normpath(os.path.join(self.book.tree_dir, dst))

        # check whether writing is required
        if os.path.isfile(fdst):
            if os.stat(fsrc).st_size == os.stat(fdst).st_size:
                if util.checksum(fsrc) == util.checksum(fdst):
                    yield Info('debug', f'Skipped resource file {dst!r} (up-to-date)')
                    return

        # save file
        yield Info('info', f'Generating resource file {dst!r}')
        try:
            os.makedirs(os.path.dirname(fdst), exist_ok=True)
            fsrc = self.host.get_static_file(src)
            self.book.backup(fdst)
            shutil.copyfile(fsrc, fdst)
        except OSError as exc:
            yield Info('error', f'Failed to create resource file {dst!r}: {exc.strerror}', exc=exc)

    def _generate_page(self, dst, tpl, **kwargs):
        yield Info('debug', f'Checking page {dst!r}')
        fsrc = io.BytesIO()
        fdst = os.path.normpath(os.path.join(self.book.tree_dir, dst))

        template = self.template_env.get_template(tpl)
        content = template.render(**kwargs)
        fsrc.write(content.encode('UTF-8'))

        # check whether writing is required
        if os.path.isfile(fdst):
            if fsrc.getbuffer().nbytes == os.stat(fdst).st_size:
                fsrc.seek(0)
                if util.checksum(fsrc) == util.checksum(fdst):
                    yield Info('debug', f'Skipped page {dst!r} (up-to-date)')
                    return

        # save file
        yield Info('info', f'Generating page {dst!r}')
        try:
            fsrc.seek(0)
            os.makedirs(os.path.dirname(fdst), exist_ok=True)
            self.book.backup(fdst)
            with open(fdst, 'wb') as fh:
                shutil.copyfileobj(fsrc, fh)
        except OSError as exc:
            yield Info('error', f'Failed to create page file {dst!r}: {exc.strerror}', exc=exc)

    def _generate_static_index(self):
        def get_class_text(classes, prefix=' '):
            if not classes:
                return ''

            c = html.escape(' '.join(classes))
            return f'{prefix}class="{c}"'

        def add_child_items(parent_id):
            nonlocal level

            try:
                toc = book.toc[parent_id]
            except KeyError:
                return

            toc = [id for id in toc if id in book.meta]
            if not toc:
                return

            yield StaticIndexItem('start-container', level)
            level += 1

            for id in toc:
                meta = book.meta[id]
                meta_type = meta.get('type', '')
                meta_index = meta.get('index', '')
                meta_title = meta.get('title', '')
                meta_source = meta.get('source', '')
                meta_icon = meta.get('icon', '')
                meta_comment = meta.get('comment', '')
                meta_marked = meta.get('marked', '')

                if meta_type != 'separator':
                    title = meta_title or id

                    if meta_type != 'folder':
                        if meta_type == 'bookmark' and meta_source:
                            href = meta_source
                        elif meta_index:
                            href = util.get_relative_url(os.path.join(book.data_dir, meta_index), book.tree_dir, path_is_dir=False)
                            hash = urlsplit(meta_source).fragment
                            if hash:
                                href += '#' + hash
                        else:
                            href = ''
                    else:
                        href = ''

                    # meta_icon is a URL
                    if meta_icon and not urlsplit(meta_icon).scheme:
                        # relative URL: tree_dir..index..icon
                        ref = util.get_relative_url(os.path.join(book.data_dir, os.path.dirname(meta_index)), book.tree_dir)
                        icon = ref + meta_icon
                    else:
                        icon = meta_icon

                else:
                    title = meta_title
                    href = ''
                    icon = ''

                yield StaticIndexItem('start', level, id, meta_type, meta_marked, title, href, icon, meta_source, meta_comment)

                # do not output children of a circular item
                if id not in id_chain:
                    level += 1
                    id_chain.add(id)
                    yield from add_child_items(id)
                    id_chain.remove(id)
                    level -= 1

                yield StaticIndexItem('end', level, id, meta_type, meta_marked, title, href, icon, meta_source, meta_comment)

            level -= 1
            yield StaticIndexItem('end-container', level)

        book = self.book
        level = 0
        id_chain = {book.ROOT_ITEM_ID}
        yield from add_child_items(book.ROOT_ITEM_ID)


class RssFeedGenerator():
    """Main class for RSS feed generation.
    """
    NS = 'http://www.w3.org/2005/Atom'

    def __init__(self, book):
        self.book = book
        self.rss_root = book.config['rss_root'].rstrip('/') + '/'
        self.item_count = book.config['rss_item_count']

    def run(self):
        yield Info('info', 'Generating RSS feed...')

        book = self.book
        rss_root = self.rss_root

        # RSS root must be an absolute URL
        u = urlsplit(rss_root)
        if not (u.scheme and u.netloc):
            yield Info('error', f'Invalid RSS root URL {rss_root!r}')
            return

        id_prefix = re.sub(r'/+$', '', f'urn:webscrapbook:{u.netloc}{u.path}')
        data_url = urljoin(rss_root, util.get_relative_url(book.data_dir, book.root))
        tree_url = urljoin(rss_root, util.get_relative_url(book.tree_dir, book.root))

        book.load_meta_files()

        # get latest updated item entries
        entries = []
        for id, meta in book.meta.items():
            # show only items with content,
            # either with index or a bookmark with source
            if meta.get('type') in {'folder', 'separator'}:
                continue

            if meta.get('type') != 'bookmark' and meta.get('index'):
                pass
            elif meta.get('type') == 'bookmark' and meta.get('source'):
                pass
            else:
                continue

            entries.append({
                'id': id,
                'modify': meta.get('modify', meta.get('create', '')),
                'item': meta,
            })
        entries = sorted(entries, key=lambda d: d['modify'])
        entries = tuple(reversed(entries))[:self.item_count]

        # generate tree
        root = etree.XML(f'<feed xmlns="{self.NS}"></feed>'.encode('UTF-8'))

        elem = etree.SubElement(root, 'id')
        elem.text = id_prefix

        elem = etree.SubElement(root, 'link')
        elem.attrib['rel'] = 'self'
        elem.attrib['href'] = urljoin(tree_url, 'feed.atom')

        elem = etree.SubElement(root, 'link')
        elem.attrib['href'] = urljoin(tree_url, 'map.html')

        elem = etree.SubElement(root, 'title')
        elem.attrib['type'] = 'text'
        elem.text = book.name

        elem = etree.SubElement(root, 'updated')
        if entries:
            dt = util.id_to_datetime(entries[0]['modify'])
        else:
            dt = datetime.now(timezone.utc)
        elem.text = dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        for entry in entries:
            entry_elem = etree.SubElement(root, 'entry')

            elem = etree.SubElement(entry_elem, 'id')
            elem.text = f'{id_prefix}:{quote(entry["id"])}'

            elem = etree.SubElement(entry_elem, 'link')
            if entry['item'].get('type') == 'bookmark':
                elem.attrib['href'] = entry['item']['source']
            else:
                elem.attrib['href'] = urljoin(data_url, quote(entry['item']['index']))

            elem = etree.SubElement(entry_elem, 'title')
            elem.attrib['type'] = 'text'
            elem.text = entry['item'].get('title', '')

            elem = etree.SubElement(entry_elem, 'published')
            dt = util.id_to_datetime(entry['item'].get('create', '')) or datetime.fromtimestamp(0, timezone.utc)
            elem.text = dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            elem = etree.SubElement(entry_elem, 'updated')
            dt = util.id_to_datetime(entry['modify']) or datetime.fromtimestamp(0, timezone.utc)
            elem.text = dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            elem = etree.SubElement(entry_elem, 'author')
            elem = etree.SubElement(elem, 'name')
            elem.text = 'Anonymous'

        # check whether writing is required
        fsrc = io.BytesIO(etree.tostring(root, xml_declaration=True, encoding='UTF-8'))
        fdst = os.path.normpath(os.path.join(self.book.tree_dir, 'feed.atom'))

        if os.path.isfile(fdst):
            if fsrc.getbuffer().nbytes == os.stat(fdst).st_size:
                fsrc.seek(0)
                if util.checksum(fsrc) == util.checksum(fdst):
                    yield Info('debug', 'Skipped RSS feed (up-to-date)')
                    return

        # save file
        yield Info('info', "Generating RSS feed file 'feed.atom'")
        try:
            fsrc.seek(0)
            os.makedirs(os.path.dirname(fdst), exist_ok=True)
            self.book.backup(fdst)
            with open(fdst, 'wb') as fh:
                shutil.copyfileobj(fsrc, fh)
        except OSError as exc:
            yield Info('error', f"Failed to create RSS feed file 'feed.atom': {exc.strerror}", exc=exc)


FulltextCacheItem = namedtuple('FulltextCacheItem', ('id', 'meta', 'index', 'indexfile', 'files_to_update'))


class FulltextCacheGenerator():
    """Main class for fulltext cache generation.
    """
    FULLTEXT_SPACE_REPLACER = staticmethod(partial(re.compile(r'\s+').sub, ' '))
    FULLTEXT_EXCLUDE_TAGS = {
        'title',
        'style', 'script', 'template',
        'frame', 'iframe',
        'object', 'applet',
        'audio', 'video',
        'canvas',
        'noframes', 'noscript', 'noembed',
        'textarea',
        # 'parsererror',
        'svg', 'math',
    }

    def __init__(self, book, *, recreate=False):
        self.book = book
        self.inclusive_frames = self.book.config['inclusive_frames']
        self.recreate = recreate
        self.cache_last_modified = 0

    def run(self, item_ids=None):
        """Update fulltext cache for item_ids

        Args:
            item_ids: a list of item IDs to update, invalid ones will be
                skipped. None to update all IDs.
        """
        yield Info('info', 'Generating fulltext cache...')

        book = self.book

        try:
            self.cache_last_modified = max(os.stat(f).st_mtime for f in book.iter_fulltext_files())
        except ValueError:
            # no fulltext file
            self.cache_last_modified = 0

        book.load_meta_files()
        book.load_toc_files()
        if self.recreate:
            book.fulltext = {}
            book_fulltext_orig = None
        else:
            book.load_fulltext_files()
            book_fulltext_orig = book.checksum(book.fulltext)

        # generate cache for each item
        if item_ids:
            id_pool = dict.fromkeys(id for id in item_ids if id in book.meta or id in book.fulltext)
        else:
            id_pool = dict.fromkeys(itertools.chain(book.meta, book.fulltext))

        for id in id_pool:
            yield from self._cache_item(id)

        # update fulltext files
        if book.checksum(book.fulltext) != book_fulltext_orig:
            # changed => save new files
            yield Info('info', 'Saving fulltext files...')
            book.save_fulltext_files()
        else:
            # no change => touch files to prevent falsely detected as outdated
            yield Info('info', 'Touching fulltext files...')
            for file in book.iter_fulltext_files():
                os.utime(file)

    def _cache_item(self, id):
        yield Info('debug', f'Checking item {id!r}')
        book = self.book

        # remove id if no meta
        meta = book.meta.get(id)
        if meta is None:
            yield Info('debug', f'Purging item {id!r} (missing metadata)')
            yield from self._delete_item(id)
            return

        # remove id if no index
        index = meta.get('index')
        if not index:
            yield Info('debug', f'Purging item {id!r} (no index)')
            yield from self._delete_item(id)
            return

        # remove id if no index file
        indexfile = os.path.join(book.data_dir, index)
        if not os.path.exists(indexfile):
            yield Info('debug', f'Purging item {id!r} (missing index file)')
            yield from self._delete_item(id)
            return

        # a mapping file path => status
        # status: True for a file to be checked; False for a file (mostly
        # an inclusive iframe) that is not available as inline,
        # (already added to cache or to be removed from cache)
        files_to_update = MutatingDict()

        item = FulltextCacheItem(id, meta, index, indexfile, files_to_update)
        yield from self._collect_files_to_update(item)
        yield from self._handle_files_to_update(item)

    def _delete_item(self, id):
        if id in self.book.fulltext:
            yield Info('info', f'Removing stale cache for {id!r}.')
            del self.book.fulltext[id]

    def _collect_files_to_update(self, item):
        book = self.book
        id, meta, index, indexfile, files_to_update = item

        # create cache for this id if not exist yet
        if book.fulltext.get(id) is None:
            book.fulltext[id] = {}
        else:
            # unless newly created, presume no change if archive file not newer
            # than cache file, for better performance
            if util.is_archive(indexfile):
                if os.stat(indexfile).st_mtime <= self.cache_last_modified:
                    yield Info('debug', f'Skipped {id!r} (archive file older than cache)')
                    return

        # add index file(s) to update list
        try:
            for path in book.get_index_paths(index):
                yield Info('debug', f'Adding {path!r} of {id!r} to check list (from index)')
                files_to_update[path] = True
        except zipfile.BadZipFile:
            # MAFF file corrupted.
            # Skip adding index files.
            # Treat as no file exists and remove all indexes later on.
            yield Info('error', f'Archive file for {id!r} is corrupted')

        # add files in cache to update list
        for path in book.fulltext[id]:
            yield Info('debug', f'Adding {path!r} of {id!r} to check list (from cache)')
            files_to_update[path] = True

    def _handle_files_to_update(self, item):
        def report_update():
            nonlocal has_update
            if has_update:
                return
            if book.fulltext[id]:
                yield Info('info', f'Updating cache for {id!r}...')
            else:
                yield Info('info', f'Generating cache for {id!r}...')
            has_update = True

        book = self.book
        id, meta, index, indexfile, files_to_update = item
        has_update = False

        for path in files_to_update:
            yield Info('debug', f'Checking {path!r} of {id!r}')
            # remove from cache if marked False
            if not files_to_update[path]:
                yield Info('debug', f'Purging {path!r} of {id!r} (inlined)')
                if path in book.fulltext[id]:
                    yield from report_update()
                    del book.fulltext[id][path]
                continue

            # mark False to prevent added otherwhere
            files_to_update[path] = False

            mtime = yield from self._get_mtime(item, path)
            if mtime is None:
                # path not exist => delete from cache
                yield Info('debug', f'Purging {path!r} of {id!r} (file not exist)')
                if path in book.fulltext[id]:
                    yield from report_update()
                    del book.fulltext[id][path]
                continue

            # skip update if the file is not newer
            # - A file hasn't been cached may be newly refrenced by another
            #   updated file, and thus needs update even if it's mtime is not
            #   newer.
            if path in book.fulltext[id] and mtime <= self.cache_last_modified:
                yield Info('debug', f'Skipped {path!r} of {id!r} (file older than cache)')
                continue

            yield from report_update()

            # set updated fulltext
            yield Info('debug', f'Generating cache for {path!r} of {id!r}')
            fulltext = yield from self._get_fulltext_cache(item, path)

            if fulltext is not None:
                book.fulltext[id][path] = {
                    'content': fulltext,
                }
            else:
                try:
                    del book.fulltext[id][path]
                except KeyError:
                    pass

    def _get_mtime(self, item, path):
        if util.is_archive(item.index):
            try:
                zh = zipfile.ZipFile(os.path.join(self.book.data_dir, item.index))
            except zipfile.BadZipFile as exc:
                yield Info('error', f'Failed to open zip file {item.index!r} for {item.id!r}: {exc}', exc=exc)
                return None
            except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as exc:
                yield Info('error', f'Failed to open zip file {item.index!r} for {item.id!r}: {exc.strerror}', exc=exc)
                return None

            try:
                with zh as zh:
                    info = zh.getinfo(path)
                    return util.fs.zip_timestamp(info)
            except KeyError:
                return None
            except Exception as exc:
                yield Info('error', f'Failed to access in-zip-file for {path!r} of {item.id!r}: {exc}', exc=exc)
                return None

        file = os.path.join(self.book.data_dir, os.path.dirname(item.index), path)
        try:
            return os.stat(file).st_mtime
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            return None
        except OSError as exc:
            yield Info('error', f'Failed to access file for {path!r} of {item.id!r}: {exc.strerror}', exc=exc)
            return None

    def _open_file(self, item, path):
        if util.is_archive(item.index):
            try:
                zh = zipfile.ZipFile(os.path.join(self.book.data_dir, item.index))
            except zipfile.BadZipFile as exc:
                yield Info('error', f'Failed to open zip file {item.index!r} for {item.id!r}: {exc}', exc=exc)
                return None
            except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as exc:
                yield Info('error', f'Failed to open zip file {item.index!r} for {item.id!r}: {exc.strerror}', exc=exc)
                return None

            try:
                with zh as zh:
                    return zh.open(path)
            except KeyError:
                return None
            except Exception as exc:
                yield Info('error', f'Failed to open in-zip-file for {path!r} of {item.id!r}: {exc}', exc=exc)
                return None

        file = os.path.join(self.book.data_dir, os.path.dirname(item.index), path)
        try:
            return open(file, 'rb')
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            return None
        except OSError as exc:
            yield Info('error', f'Failed to open file for {path!r} of {item.id!r}: {exc.strerror}', exc=exc)
            return None

    def _get_fulltext_cache(self, item, path):
        fh = yield from self._open_file(item, path)
        if not fh:
            yield Info('debug', f'Skipped {path!r} of {item.id!r} (file not exist or accessible)')
            return None

        try:
            mime, _ = mimetypes.guess_type(path)
            return (yield from self._get_fulltext_cache_for_fh(item, path, fh, mime))
        except Exception as exc:
            yield Info('error', f'Failed to generate cache for {item.id!r} ({path!r}): {exc}', exc=exc)
            return ''
        finally:
            fh.close()

    def _get_fulltext_cache_for_fh(self, item, path, fh, mime, *, is_srcdoc=False):
        if not mime:
            yield Info('debug', f'Skipped {path!r} of {item.id!r} (unknown type)')
            return None

        if util.mime_is_html(mime):
            return (yield from self._get_fulltext_cache_html(item, path, fh, is_srcdoc=is_srcdoc))

        if mime.startswith('text/'):
            return (yield from self._get_fulltext_cache_txt(item, path, fh))

        yield Info('debug', f'Skipped {path!r} of {item.id!r} ({mime!r} not supported)')
        return None

    def _get_fulltext_cache_html(self, item, path, fh, *, is_srcdoc=False):
        def get_relative_file_path(url):
            # skip when inside a data URL page (can't resolve)
            if path is None:
                return None

            try:
                urlparts = urlsplit(url)
            except ValueError:
                return None

            # skip absolute URLs
            if urlparts.scheme != '':
                return None

            if urlparts.netloc != '':
                return None

            if urlparts.path.startswith('/'):
                return None

            base = get_relative_file_path.base = getattr(get_relative_file_path, 'base', 'file:///!/')
            ref = get_relative_file_path.ref = getattr(get_relative_file_path, 'ref', urljoin(base, quote(path)))
            target = urljoin(ref, urlparts.path)

            # skip if URL contains '..'
            if not target.startswith(base):
                return None

            target = unquote(target)

            # ignore referring self
            if target == ref:
                return None

            target = target[len(base):]

            return target

        def add_datauri_content(url):
            try:
                data = util.parse_datauri(url)
            except util.DataUriMalformedError as exc:
                yield Info('error', f'Skipped malformed data URL {util.crop(url, 256)!r}: {exc}', exc=exc)
                return
            fh = io.BytesIO(data.bytes)
            fulltext = yield from self._get_fulltext_cache_for_fh(item, None, fh, data.mime)
            if fulltext:
                results.append(fulltext)

        if is_srcdoc:
            yield Info('debug', f'Retrieving HTML content for {path!r} (srcdoc) of {item.id!r}')
        else:
            yield Info('debug', f'Retrieving HTML content for {path!r} of {item.id!r}')

        charset = util.get_html_charset(fh, default=item.meta.get('charset') or 'UTF-8')
        encoding = util.lxml_fix_codec(charset)

        results = []
        has_instant_redirect = False
        for time_, url, context in util.iter_meta_refresh(fh, encoding=encoding):
            if time_ == 0 and not context:
                has_instant_redirect = True

            if not url:
                continue

            if context and any(c in util.META_REFRESH_FORBID_TAGS for c in context):
                continue

            if url.startswith('data:'):
                yield from add_datauri_content(url)
            else:
                target = get_relative_file_path(url)
                if target and target not in item.files_to_update:
                    yield Info('debug', f'Adding {target!r} of {item.id!r} to check list (from <meta>)')
                    item.files_to_update[target] = True

        # Add data URL content of meta refresh targets to fulltext index if the
        # page has an instant meta refresh.
        if has_instant_redirect:
            return self.FULLTEXT_SPACE_REPLACER(' '.join(results)).strip()

        # add main content
        # Note: adding elem.text at start event or elem.tail at end event is
        # not reliable as the parser hasn't load full content of text or tail
        # at that time yet.
        # @TODO: better handle content
        # (no space between inline nodes, line break between block nodes, etc.)
        fh.seek(0)
        util.sniff_bom(fh)
        exclusion_stack = []

        def gen():
            try:
                yield from etree.iterparse(
                    fh, html=True, events=('start', 'end'),
                    remove_comments=True, encoding=encoding)
            except etree.Error:
                pass

        for event, elem in gen():
            if event == 'start':
                # skip if we are in an excluded element
                if exclusion_stack:
                    continue

                # Add last text before starting of this element.
                prev = elem.getprevious()
                attr = 'tail'
                if prev is None:
                    prev = elem.getparent()
                    attr = 'text'

                if prev is not None:
                    text = getattr(prev, attr)
                    if text:
                        results.append(text)
                        setattr(prev, attr, None)

                if elem.tag in ('a', 'area'):
                    # include linked pages in fulltext index
                    try:
                        url = elem.attrib['href']
                    except KeyError:
                        pass
                    else:
                        if url.startswith('data:'):
                            yield from add_datauri_content(url)
                        else:
                            target = get_relative_file_path(url)
                            if target and target not in item.files_to_update:
                                yield Info('debug', f'Adding {target!r} of {item.id!r} to check list (from <{elem.tag}>)')
                                item.files_to_update[target] = True

                elif elem.tag in ('iframe', 'frame'):
                    # include frame page in fulltext index
                    try:
                        srcdoc = elem.attrib['srcdoc']
                    except KeyError:
                        try:
                            url = elem.attrib['src']
                        except KeyError:
                            pass
                        else:
                            if url.startswith('data:'):
                                yield from add_datauri_content(url)
                            else:
                                target = get_relative_file_path(url)
                                if target:
                                    if self.inclusive_frames:
                                        # Add frame content to the current page
                                        # content if the targeted file hasn't
                                        # been indexed.
                                        if item.files_to_update.get(target) is not False:
                                            yield Info('debug', f'Caching {target!r} of {item.id!r} as inline (from <{elem.tag}>)')
                                            item.files_to_update[target] = False
                                            fulltext = yield from self._get_fulltext_cache(item, target)
                                            if fulltext:
                                                results.append(fulltext)
                                    else:
                                        if target not in item.files_to_update:
                                            yield Info('debug', f'Adding {target!r} of {item.id!r} to check list (from <{elem.tag}>)')
                                            item.files_to_update[target] = True
                    else:
                        fh = io.BytesIO(srcdoc.encode('UTF-8-SIG'))
                        fulltext = yield from self._get_fulltext_cache_for_fh(item, path, fh, 'text/html', is_srcdoc=True)
                        if fulltext:
                            results.append(fulltext)

                # exclude everything inside certain tags
                if elem.tag in self.FULLTEXT_EXCLUDE_TAGS:
                    exclusion_stack.append(elem)
                    continue

            elif event == 'end':
                # Add last text before ending of this element.
                if not exclusion_stack:
                    try:
                        prev = elem[-1]
                        attr = 'tail'
                    except IndexError:
                        prev = elem
                        attr = 'text'

                    if prev is not None:
                        text = getattr(prev, attr)
                        if text:
                            results.append(text)
                            setattr(prev, attr, None)

                # stop exclusion at the end of an excluding element
                try:
                    if elem is exclusion_stack[-1]:
                        exclusion_stack.pop()
                except IndexError:
                    pass

                # clean up to save memory
                # remember to keep tail
                try:
                    elem.clear(keep_tail=True)
                except TypeError:
                    # keep_tail is supported since lxml 4.4.0
                    pass
                while elem.getprevious() is not None:
                    try:
                        del elem.getparent()[0]
                    except TypeError:
                        # broken html may generate extra root elem
                        break

        return self.FULLTEXT_SPACE_REPLACER(' '.join(results)).strip()

    def _get_fulltext_cache_txt(self, item, path, fh):
        yield Info('debug', f'Retrieving text content for {path!r} of {item.id!r}')
        charset = util.sniff_bom(fh) or util.fix_codec(item.meta.get('charset', '')) or 'UTF-8'
        text = fh.read().decode(charset, errors='replace')
        return self.FULLTEXT_SPACE_REPLACER(text).strip()


def generate(host, book_items=None, *,
             lock=True, backup=True,
             fulltext=True, recreate=False,
             static_site=False, static_index=None,
             rss=None):
    start = time.time()

    if isinstance(host, Host):
        pass
    elif isinstance(host, str):
        host = Host(host)
    else:
        host = Host(*host)

    if backup:
        host.init_auto_backup(note='cache')
        yield Info('info', f'Prepared backup at {host.get_subpath(host._auto_backup_dir)!r}.')
        yield Info('info', '----------------------------------------------------------------------')

    try:
        first = True
        for book_id, item_ids in (book_items or dict.fromkeys(host.books)).items():
            if first:
                first = False
            else:
                yield Info('info', '----------------------------------------------------------------------')

            try:
                book = host.books[book_id]
            except KeyError:
                # skip invalid book ID
                yield Info('warn', f'Skipped invalid book {book_id!r}.')
                continue

            if book.no_tree:
                yield Info('info', f'Skipped book {book_id!r} ({book.name!r}) (no_tree).')
                continue

            yield Info('info', f'Caching book {book_id!r} ({book.name!r}).')
            lh = book.get_tree_lock(persist=lock).acquire() if lock else nullcontext()
            with lh:
                if fulltext:
                    generator = FulltextCacheGenerator(
                        book,
                        recreate=recreate,
                    )
                    yield from generator.run(item_ids)

                if static_site:
                    generator = StaticSiteGenerator(
                        book,
                        static_index=static_index,
                    )
                    yield from generator.run()

                _rss = static_site if rss is None else rss

                if _rss:
                    if not book.config['rss_root']:
                        yield Info('debug', 'Skipped RSS generating: RSS root not configured')
                        continue

                    generator = RssFeedGenerator(
                        book,
                    )
                    yield from generator.run()

            yield Info('info', 'Done.')
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    finally:
        if backup:
            host.init_auto_backup(False)

    yield Info('info', '----------------------------------------------------------------------')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
