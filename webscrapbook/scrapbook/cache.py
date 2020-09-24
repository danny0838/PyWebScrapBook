"""Generator of fulltext cache and/or static site pages.
"""
import os
import traceback
import io
import zipfile
import mimetypes
import time
import re
import copy
import itertools
import functools
from collections import namedtuple, UserDict
from urllib.parse import urlsplit, urljoin, quote, unquote

from lxml import etree

from .host import Host
from .. import util
from ..util import Info
from .._compat import zip_stream
from .._compat.contextlib import nullcontext


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


FulltextCacheItem = namedtuple('FulltextCacheItem', ['id', 'meta', 'index', 'indexfile', 'files_to_update'])

class FulltextCacheGenerator():
    """Main class for fulltext cache generation.
    """
    FULLTEXT_SPACE_REPLACER = functools.partial(re.compile(r'\s+').sub, ' ')
    FULLTEXT_EXCLUDE_TAGS = {
        'title', 'style', 'script',
        'frame', 'iframe',
        'object', 'applet',
        'audio', 'video',
        'canvas',
        'noframes', 'noscript', 'noembed',
        # 'parsererror',
        'svg', 'math',
        }
    URL_SAMPLE_LENGTH = 256

    def __init__(self, book, *, inclusive_frames=True):
        self.book = book
        self.inclusive_frames = inclusive_frames
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
        book.load_fulltext_files()

        book_fulltext_orig = copy.deepcopy(book.fulltext)

        # generate cache for each item
        if item_ids:
            id_pool = dict.fromkeys(id for id in item_ids if id in book.meta or id in book.fulltext)
        else:
            id_pool = dict.fromkeys(itertools.chain(book.meta, book.fulltext))

        for id in id_pool:
            yield from self._cache_item(id)

        # update fulltext files
        if book.fulltext != book_fulltext_orig:
            # changed => save new files
            yield Info('info', f'Saving fulltext files...')
            book.save_fulltext_files()
        else:
            # no change => touch files to prevent falsely detected as outdated
            yield Info('info', f'Touching fulltext files...')
            for file in book.iter_fulltext_files():
                os.utime(file)

    def _cache_item(self, id):
        yield Info('debug', f'Checking item "{id}"')
        book = self.book

        # remove id if no meta
        meta = book.meta.get(id)
        if meta is None:
            yield Info('debug', f'Purging item "{id}" (missing metadata)')
            yield from self._delete_item(id)
            return

        # remove id if no index
        index = meta.get('index')
        if not index:
            yield Info('debug', f'Purging item "{id}" (no index)')
            yield from self._delete_item(id)
            return

        # remove id if no index file
        indexfile = os.path.join(book.data_dir, index)
        if not os.path.exists(indexfile):
            yield Info('debug', f'Purging item "{id}" (missing index file)')
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
            yield Info('info', f'Removing stale cache for "{id}".')
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
                    yield Info('debug', f'Skipped "{id}" (archive file older than cache)')
                    return

        # add index file(s) to update list
        try:
            for path in book.get_index_paths(index):
                yield Info('debug', f'Adding "{path}" of "{id}" to check list (from index)')
                files_to_update[path] = True
        except zipfile.BadZipFile:
            # MAFF file corrupted.
            # Skip adding index files.
            # Treat as no file exists and remove all indexes later on.
            yield Info('error', f'Archive file for "{id}" is corrupted')

        # add files in cache to update list
        for path in book.fulltext[id]:
            yield Info('debug', f'Adding "{path}" of "{id}" to check list (from cache)')
            files_to_update[path] = True

    def _handle_files_to_update(self, item):
        def report_update():
            nonlocal has_update
            if has_update:
                return
            if book.fulltext[id]:
                yield Info('info', f'Updating cache for "{id}"...')
            else:
                yield Info('info', f'Creating cache for "{id}"...')
            has_update = True

        book = self.book
        id, meta, index, indexfile, files_to_update = item
        has_update = False

        for path in files_to_update:
            yield Info('debug', f'Checking "{path}" of "{id}"')
            # remove from cache if marked False
            if not files_to_update[path]:
                yield Info('debug', f'Purging "{path}" of "{id}" (inlined)')
                if path in book.fulltext[id]:
                    yield from report_update()
                    del book.fulltext[id][path]
                continue

            # mark False to prevent added otherwhere
            files_to_update[path] = False

            mtime = yield from self._get_mtime(item, path)
            if mtime is None:
                # path not exist => delete from cache
                yield Info('debug', f'Purging "{path}" of "{id}" (file not exist)')
                if path in book.fulltext[id]:
                    yield from report_update()
                    del book.fulltext[id][path]
                continue

            # skip update if the file is not newer
            # - A file hasn't been cached may be newly refrenced by another
            #   updated file, and thus needs update even if it's mtime is not
            #   newer.
            if path in book.fulltext[id] and mtime <= self.cache_last_modified:
                yield Info('debug', f'Skipped "{path}" of "{id}" (file older than cache)')
                continue

            yield from report_update()

            # set updated fulltext
            yield Info('debug', f'Generating cache for "{path}" of "{id}"')
            try:
                fulltext = yield from self._get_fulltext_cache(item, path)
            except Exception as exc:
                fulltext = ''
                traceback.print_exc()
                yield Info('error', f'Failed to generate cache for "{id}" ({path}): {exc}', exc=exc)

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
                yield Info('error', f'Failed to open zip file "{item.index}" for "{item.id}": {exc}', exc=exc)
                return None
            except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as exc:
                yield Info('error', f'Failed to open zip file "{item.index}" for "{item.id}": [Errno {exc.args[0]}] {exc.args[1]}', exc=exc)
                return None

            try:
                with zh as zh:
                    info = zh.getinfo(path)
                    return util.zip_timestamp(info)
            except KeyError:
                return None
            except Exception as exc:
                yield Info('error', f'Failed to access in-zip-file for "{path}" of "{item.id}": {exc}', exc=exc)
                return None

        file = os.path.join(self.book.data_dir, os.path.dirname(item.index), path)
        try:
            return os.stat(file).st_mtime
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            return None
        except OSError:
            yield Info('error', f'Failed to access file for "{path}" of "{item.id}": [Errno {exc.args[0]}] {exc.args[1]}', exc=exc)
            return None

    def _open_file(self, item, path):
        if util.is_archive(item.index):
            try:
                zh = zipfile.ZipFile(os.path.join(self.book.data_dir, item.index))
            except zipfile.BadZipFile as exc:
                yield Info('error', f'Failed to open zip file "{item.index}" for "{item.id}": {exc}', exc=exc)
                return None
            except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as exc:
                yield Info('error', f'Failed to open zip file "{item.index}" for "{item.id}": [Errno {exc.args[0]}] {exc.args[1]}', exc=exc)
                return None

            try:
                with zh as zh:
                    return zh.open(path)
            except KeyError:
                return None
            except Exception as exc:
                yield Info('error', f'Failed to open in-zip-file for "{path}" of "{item.id}": {exc}', exc=exc)
                return None

        file = os.path.join(self.book.data_dir, os.path.dirname(item.index), path)
        try:
            return open(file, 'rb')
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            return None
        except OSError as exc:
            yield Info('error', f'Failed to open file for "{path}" of "{item.id}": [Errno {exc.args[0]}] {exc.args[1]}', exc=exc)
            return None

    def _get_fulltext_cache(self, item, path):
        fh = yield from self._open_file(item, path)
        if not fh:
            yield Info('debug', f'Skipped "{path}" of "{item.id}" (file not exist or accessible)')
            return None

        fh = zip_stream(fh)
        try:
            mime, _ = mimetypes.guess_type(path)
            return (yield from self._get_fulltext_cache_for_fh(item, path, fh, mime))
        finally:
            fh.close()

    def _get_fulltext_cache_for_fh(self, item, path, fh, mime):
        if not mime:
            yield Info('debug', f'Skipped "{path}" of "{item.id}" (unknown type)')
            return None

        if util.mime_is_html(mime):
            return (yield from self._get_fulltext_cache_html(item, path, fh))

        if mime.startswith('text/'):
            return (yield from self._get_fulltext_cache_txt(item, path, fh))

        yield Info('debug', f'Skipped "{path}" of "{item.id}" ("{mime}" not supported)')
        return None

    def _get_fulltext_cache_html(self, item, path, fh):
        def get_relative_file_path(url):
            # skip when inside a data URL page (can't resolve)
            if path is None:
                return None

            urlparts = urlsplit(url)

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
                yield Info('error', f'Skipped malformed data URL "{url[:self.URL_SAMPLE_LENGTH]}": {exc}', exc=exc)
                return
            fh = io.BytesIO(data.bytes)
            fulltext = yield from self._get_fulltext_cache_for_fh(item, None, fh, data.mime)
            if fulltext:
                results.append(fulltext)

        yield Info('debug', f'Retrieving HTML content for "{path}" of "{item.id}"')

        # Seek for the correct charset (encoding).
        # If a charset is not specified, lxml may select a wrong encoding for
        # the entire document if there is text before first meta charset.
        # Priority: BOM > meta charset > item charset > assume UTF-8
        charset = util.sniff_bom(fh)
        if charset:
            # lxml does not accept "UTF-16-LE" or so, but can auto-detect
            # encoding from BOM if encoding is None
            # ref: https://bugs.launchpad.net/lxml/+bug/1463610
            charset = None
            fh.seek(0)
        else:
            charset = util.get_charset(fh) or item.meta.get('charset') or 'UTF-8'
            charset = util.fix_codec(charset)
            fh.seek(0)

        results = []
        has_instant_redirect = False
        for time_, url, context in util.iter_meta_refresh(fh):
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
                    yield Info('debug', f'Adding "{target}" of "{item.id}" to check list (from <meta>)')
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
        exclusion_stack = []
        for event, elem in etree.iterparse(fh, html=True, events=('start', 'end'),
                remove_comments=True, encoding=charset):
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
                                yield Info('debug', f'Adding "{target}" of "{item.id}" to check list (from <{elem.tag}>)')
                                item.files_to_update[target] = True

                elif elem.tag in ('iframe', 'frame'):
                    # include frame page in fulltext index
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
                                        yield Info('debug', f'Caching "{target}" of "{item.id}" as inline (from <{elem.tag}>)')
                                        item.files_to_update[target] = False
                                        fulltext = yield from self._get_fulltext_cache(item, target)
                                        if fulltext:
                                            results.append(fulltext)
                                else:
                                    if target not in item.files_to_update:
                                        yield Info('debug', f'Adding "{target}" of "{item.id}" to check list (from <{elem.tag}>)')
                                        item.files_to_update[target] = True

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
        yield Info('debug', f'Retrieving text content for "{path}" of "{item.id}"')
        charset = util.sniff_bom(fh) or item.meta.get('charset') or 'UTF-8'
        charset = util.fix_codec(charset)
        text = fh.read().decode(charset, errors='replace')
        return self.FULLTEXT_SPACE_REPLACER(text).strip()


def generate(root, book_ids=None, item_ids=None, *, config=None, no_lock=False,
        fulltext=True, inclusive_frames=True):
    start = time.time()

    host = Host(root, config)

    # cache all book_ids if none specified
    if not book_ids:
        book_ids = list(host.books)

    avail_book_ids = set(host.books)
    for book_id in book_ids:
        # skip invalid book ID
        if book_id not in avail_book_ids:
            yield Info('warn', f'Skipped invalid book "{book_id}".')
            continue

        yield Info('info', f'Checking book "{book_id}".')

        try:
            book = host.books[book_id]

            if book.no_tree:
                yield Info('info', f'Skipped book "{book_id}" (no_tree).')
                continue

            yield Info('info', f'Caching book "{book_id}".')
            lh = nullcontext() if no_lock else book.get_tree_lock().acquire()
            with lh:
                if fulltext:
                    generator = FulltextCacheGenerator(
                        book,
                        inclusive_frames=inclusive_frames,
                        )
                    yield from generator.run(item_ids)
        except Exception as exc:
            traceback.print_exc()
            yield Info('critical', str(exc), exc=exc)
        else:
            yield Info('info', 'Done.')

        yield Info('info', '----------------------------------------------------------------------')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
