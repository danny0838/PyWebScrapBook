from .treefiles import TreeFiles
from .datafiles import DataFiles
from .data import (
    IndexFile,
    IndexFileHtml,
    IndexFileText,
    IndexFileUnknown
)
from webscrapbook.util import (
    sniff_bom,
    fix_codec,
    get_charset,
    parse_datauri,
    DataUriMalformedError,
    iter_meta_refresh
)

from urllib.parse import urlsplit, urljoin, quote, unquote
import io, functools, re
from lxml import etree


class GenerateFulltext:

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

    def __init__(self, treefiles: TreeFiles, datafiles: DataFiles, inclusive_frames=True):
        self._updated_files = dict()
        self._fulltext = treefiles.files.fulltext
        self._meta = treefiles.file.meta
        self._data_items = datafiles.data_items

        self.inclusive_frames = inclusive_frames

    def _remove_fulltext_data_item(self, id_val):
        self._fulltext.data.remove_item(id_val)

    def _add_fulltext_data_item(self, id_val, index_file, fulltext_val):
        self._fulltext.data.add_item_content(id_val, index_file.indexpath, fulltext_val)

    def _clear_old_fulltext_data_items(self):
        fulltext_id_vals = set(self._fulltext.data.get_ids())
        data_item_id_vals = set(self._data_items.keys())
        old_fulltext_id_vals = fulltext_id_vals - data_item_id_vals
        for id_val in old_fulltext_id_vals:
            self._remove_fulltext_data_item(id_val)

    def _is_fulltext_stale(self, id_val, index_file_modify_time):
        return (index_file_modify_time > self._fulltext.modify_time) and self._fulltext.data.item_exists(id_val)

    def _get_data_items(self, id_vals=None):
        if id_vals:
            return [data_item for data_item in self._data_items if data_item.id in id_vals]
        else:
            return self._data_items

    def generate(self, id_vals=None):
        def are_fulltext_entries_for_index_files_stale(index_files):
            return all([self._is_fulltext_stale(index_file.get_modify_time(), index_file.id) for index_file in index_files])

        data_items = self._get_data_items(id_vals)

        self._clear_old_fulltext_data_items()

        for id_val, data_item in data_items:
            if not are_fulltext_entries_for_index_files_stale(data_item.index_files):
                data_item.resolve_index_files_to_openable()
                
                index_files = data_item.index_files
                for index_file in index_files:
                    if not self._is_fulltext_stale(index_file.get_modify_time(), index_file.id):
                        fulltext_val = self._get_fulltext_val(index_file)
                        self._add_fulltext_data_item(id_val, index_file, fulltext_val)


    def _get_fulltext_val(self, index_file: IndexFile):
        if isinstance(index_file, IndexFileUnknown):
            # cannot fulltext file of unknown mime type
            # silently fail
            return ''
        elif isinstance(index_file, IndexFileHtml):
            # is fulltextable using normal function
            fh = index_file.open_file()
            return self._get_fulltext_cache_html(item, path, fh)
        elif isinstance(index_file, IndexFileText):
            # is fulltextable using alternate function
            fh = index_file.open_file()
            return self._get_fulltext_cache_txt(index_file._id, fh)
        else:
            # silent fail
            return ''



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

        # @TODO: show message for malformed data URLs
        def datauri_content(url):
            try:
                data = parse_datauri(url)
            except DataUriMalformedError:
                return
            fh = io.BytesIO(data.bytes)
            fulltext = self._get_fulltext_cache_for_fh(item, None, fh, data.mime)
            return fulltext or ''

        def get_file_charset(fh):
            # Seek for the correct charset (encoding).
            # If a charset is not specified, lxml may select a wrong encoding for
            # the entire document if there is text before first meta charset.
            # Priority: BOM > meta charset > item charset > assume UTF-8
            charset = sniff_bom(fh)
            if charset:
                # lxml does not accept "UTF-16-LE" or so, but can auto-detect
                # encoding from BOM if encoding is None
                # ref: https://bugs.launchpad.net/lxml/+bug/1463610
                charset = None
                fh.seek(0)
            else:
                charset = get_charset(fh) or item.meta.get('charset') or 'UTF-8'
                charset = fix_codec(charset)
                fh.seek(0)
            return charset
        
        charset = get_file_charset(fh)

        results = []

        has_instant_redirect = False
        for time, url in iter_meta_refresh(fh):
            if time == 0:
                has_instant_redirect = True
            if url:
                if url.startswith('data:'):
                    results.append(datauri_content(url))
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
                            results.append(datauri_content(url))

                elif elem.tag in ('iframe', 'frame'):
                    # include frame page in fulltext index
                    try:
                        url = elem.attrib['src']
                    except KeyError:
                        pass
                    else:
                        if url.startswith('data:'):
                            results.append(datauri_content(url))
                        else:
                            target = get_relative_file_path(url)
                            if target:
                                if self.inclusive_frames:
                                    fulltext = self._get_fulltext_cache(item, target)
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

    def _get_fulltext_cache_txt(self, id_val, fh):
        charset = sniff_bom(fh) or self._meta.data.get(id_val, 'charset') or 'UTF-8'
        charset = fix_codec(charset)
        text = fh.read().decode(charset, errors='replace')
        return self.FULLTEXT_SPACE_REPLACER(text).strip()

