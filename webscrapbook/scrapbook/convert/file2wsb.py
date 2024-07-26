import html
import os
import shutil
import time
import traceback
from urllib.parse import quote

from lxml import etree

from ... import WSB_DIR, util
from ..._polyfill import zipfile
from ...util import Info
from ..host import Host
from ..indexer import ALLOWED_ROOT_META_ATTRS, SUPPORT_FOLDER_SUFFIXES, Indexer


class Converter:
    def __init__(self, input, output, *,
                 data_folder_suffixes=None,
                 preserve_filename=True,
                 handle_ie_meta=True,
                 handle_singlefile_meta=True,
                 handle_savepagewe_meta=True,
                 handle_maoxian_meta=True,
                 ):
        self.input = os.path.abspath(input)
        self.output = os.path.abspath(output)
        self.data_folder_suffixes = (
            [k for k in dict.fromkeys(os.path.normcase(s.strip()) for s in data_folder_suffixes) if k]
            if data_folder_suffixes is not None else SUPPORT_FOLDER_SUFFIXES)
        self.preserve_filename = preserve_filename
        self.handle_ie_meta = handle_ie_meta
        self.handle_singlefile_meta = handle_singlefile_meta
        self.handle_savepagewe_meta = handle_savepagewe_meta
        self.handle_maoxian_meta = handle_maoxian_meta
        self.wsb_dir = os.path.join(self.input, WSB_DIR)
        self.host = None
        self.book = None

    def run(self):
        os.makedirs(self.output, exist_ok=True)
        self.host = Host(self.output)
        self.book = self.host.books['']

        self.book.load_meta_files()
        self.book.load_toc_files()

        yield Info('info', 'Inspecting data files...')
        paths = []
        yield from self._inspect_data_dir(self.input, paths)

        yield Info('info', 'Saving tree files...')
        self.book.save_meta_files()
        self.book.save_toc_files()

    def _inspect_data_dir(self, data_dir, paths):
        yield Info('debug', f'Inspecting directory {data_dir!r}')

        if not os.path.samefile(data_dir, self.input):
            # add data_dir as an item if index.html exists
            index = os.path.join(data_dir, 'index.html')
            if os.path.isfile(index):
                yield from self._index_entry(data_dir, paths)
                return

            # create folder item
            basename = os.path.basename(data_dir)
            basename, ext = os.path.splitext(basename)
            if ext.lower() == '.htd':
                ext = ''

            parent_id = paths[-1]
            new_items = self.book.add_item({
                'type': 'folder',
                'title': basename + ext,
            }, parent_id)
            id = next(iter(new_items))
            yield Info('info', f'Generated folder item {id!r} under {parent_id!r}')
        else:
            id = self.book.ROOT_ITEM_ID

        try:
            entries = os.scandir(data_dir)
        except FileNotFoundError:
            return
        except OSError as exc:
            yield Info('error', f'Failed to scan folder {self.book.get_subpath(exc.filename)!r}: {exc.strerror}', exc=exc)
            return

        entries_to_handle = set()
        entries_to_exclude = set()
        with entries as entries:
            for entry in entries:
                if os.path.normcase(entry.path) == os.path.normcase(self.wsb_dir):
                    yield Info('debug', f'Skipped special {self.book.get_subpath(entry)!r}')
                    continue

                if entry.is_dir():
                    entries_to_handle.add(entry)

                elif entry.is_file():
                    if self._get_index_path_key(entry) in entries_to_exclude:
                        continue

                    entries_to_handle.add(entry)

                    if not util.is_html(entry.path):
                        continue

                    basename, _ = os.path.splitext(entry.name)
                    for suffix in self.data_folder_suffixes:
                        p = self._get_index_path_key(os.path.join(data_dir, f'{basename}{suffix}'))
                        yield Info('debug', f'Excluding {p!r} from index finding')
                        entries_to_exclude.add(p)

        paths.append(id)

        for entry in sorted(entries_to_handle, key=lambda x: x.path):
            if self._get_index_path_key(entry) in entries_to_exclude:
                continue

            if entry.is_dir():
                yield from self._inspect_data_dir(entry.path, paths)
            elif entry.is_file():
                yield from self._index_entry(entry.path, paths)

        paths.pop()

    def _index_entry(self, entry, paths):
        yield Info('debug', f'Generating item for {entry!r}...')

        basename = os.path.basename(entry)
        _, ext = os.path.splitext(entry)
        ext = ext.lower()

        # special handling for *.htd folders
        if ext == '.htd':
            ext = ''

        # Special handling for self-extracting html/zip of SingleFile.
        # Treat as HTZ as an HTML file with binary data cannot be correctly
        # read with lxml.
        is_singlefilez = (
            self.handle_singlefile_meta
            and util.is_html(entry)
            and zipfile.is_zipfile(entry)
        )
        if is_singlefilez:
            ext = '.htz'

        # generate a unique ID
        id = self.book.get_unique_id()

        # copy data files
        supporting_folder = self._get_supporting_folder(entry)
        if (supporting_folder or (
            self.preserve_filename and os.path.isfile(entry) and not (util.is_archive(entry) or is_singlefilez)
        )):
            dst_dir = os.path.join(self.book.data_dir, id)
            os.makedirs(dst_dir, exist_ok=True)

            src = entry
            dst = os.path.join(dst_dir, basename)
            yield Info('info', f'Copying data file: {src!r} => {dst!r}')
            try:
                shutil.copy2(src, dst)
            except OSError as exc:
                yield Info('error', f'Failed to copy data file {entry!r}: {exc.strerror}', exc=exc)

            index_file = os.path.join(dst_dir, 'index.html')
            if ext in self.book.ITEM_INDEX_ALLOWED_EXT:
                # copy entry to index.html for the indexer to retrieve original metadata
                yield Info('debug', f'Generating index.html from {src!r}')
                try:
                    if util.is_svg(src):
                        self._copy_svg_to_index(src, index_file)
                    else:
                        shutil.copy2(src, index_file)
                except OSError as exc:
                    yield Info('error', f'Failed to generate index.html for {entry!r}: {exc.strerror}', exc=exc)

                if supporting_folder:
                    src = supporting_folder
                    dst = os.path.join(dst_dir, os.path.basename(supporting_folder))
                    yield Info('info', f'Copying data folder: {src!r} => {dst!r}')
                    try:
                        shutil.copytree(src, dst)
                    except OSError as exc:
                        yield Info('error', f'Failed to copy data folder {entry!r}: {exc.strerror}', exc=exc)

                # generate meta
                indexer = Indexer(
                    self.book,
                    handle_ie_meta=self.handle_ie_meta,
                    handle_singlefile_meta=self.handle_singlefile_meta,
                    handle_savepagewe_meta=self.handle_savepagewe_meta,
                    handle_maoxian_meta=self.handle_maoxian_meta,
                )
                indexed = yield from indexer.run([index_file])

                if os.path.normcase(basename) != os.path.normcase('index.html'):
                    with open(index_file, 'w', encoding='UTF-8') as fh:
                        fh.write(f'<!DOCTYPE html><meta charset="UTF-8"><meta http-equiv="refresh" content="0; url={quote(basename)}">')
            else:
                # generate new index.html (with same file time) for the indexer
                with open(index_file, 'w', encoding='UTF-8') as fh:
                    fh.write(f'<!DOCTYPE html><meta charset="UTF-8"><meta http-equiv="refresh" content="0; url={quote(basename)}">')
                st = os.stat(entry)
                os.utime(index_file, (st.st_atime, st.st_mtime))

                # generate meta
                indexer = Indexer(
                    self.book,
                    handle_ie_meta=self.handle_ie_meta,
                    handle_singlefile_meta=self.handle_singlefile_meta,
                    handle_savepagewe_meta=self.handle_savepagewe_meta,
                    handle_maoxian_meta=self.handle_maoxian_meta,
                )
                indexed = yield from indexer.run([index_file])

        else:
            src = entry
            dst = os.path.join(self.book.data_dir, id + ext)
            yield Info('info', f'Copying data files: {src!r} => {dst!r}')
            try:
                try:
                    shutil.copytree(src, dst)
                except NotADirectoryError:
                    shutil.copy2(src, dst)
            except OSError as exc:
                yield Info('error', f'Failed to copy data files for {entry!r}: {exc.strerror}', exc=exc)

            index_file = os.path.join(dst, 'index.html') if os.path.isdir(entry) else dst

            # generate meta
            indexer = Indexer(
                self.book,
                handle_ie_meta=self.handle_ie_meta,
                handle_singlefile_meta=self.handle_singlefile_meta,
                handle_savepagewe_meta=self.handle_savepagewe_meta,
                handle_maoxian_meta=self.handle_maoxian_meta,
            )
            indexed = yield from indexer.run([index_file])

        for id in indexed:
            # special handle of metadata
            meta = self.book.meta[id]
            if not meta.get('title'):
                meta['title'] = basename

            if os.path.isfile(entry) and ext not in self.book.ITEM_INDEX_ALLOWED_EXT:
                meta['type'] = 'file'

            # add to parent
            parent_id = paths[-1]
            self.book.toc.setdefault(parent_id, []).append(id)
            yield Info('info', f'Appended item {id!r} under {parent_id!r}')

    def _get_index_path_key(self, path):
        return self.book.get_subpath(os.path.normcase(path))

    def _get_supporting_folder(self, file):
        if os.path.isfile(file) and util.is_html(file):
            base = os.path.splitext(file)[0]

            for suffix in self.data_folder_suffixes:
                supporting_folder = f'{base}{suffix}'
                if os.path.isdir(supporting_folder):
                    return supporting_folder

        return None

    def _copy_svg_to_index(self, src, dst):
        with open(src, 'rb') as fh:
            try:
                tree = etree.parse(fh)
            except etree.Error:
                # generate an empty (invalid) file if SVG is malformed
                attrs = None
            else:
                attrs = ''.join(
                    f' {k}="{html.escape(v)}"'
                    for k, v in tree.getroot().attrib.items()
                    if k in ALLOWED_ROOT_META_ATTRS
                )

        with open(dst, 'w', encoding='UTF-8') as fh:
            if attrs is not None:
                fh.write(f"""<!DOCTYPE html><html{attrs}></html>""")

        shutil.copystat(src, dst)


def run(input, output, *,
        data_folder_suffixes=None,
        preserve_filename=True,
        handle_ie_meta=True,
        handle_singlefile_meta=True,
        handle_savepagewe_meta=True,
        handle_maoxian_meta=True,
        ):
    start = time.time()
    yield Info('info', 'conversion mode: hierarchical files --> WebScrapBook')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output)}')
    yield Info('info', f'data_folder_suffixes: {SUPPORT_FOLDER_SUFFIXES if data_folder_suffixes is None else data_folder_suffixes}')
    yield Info('info', f'preserve filename: {preserve_filename}')
    yield Info('info', f'handle IE meta: {handle_ie_meta}')
    yield Info('info', f'handle SingleFile meta: {handle_singlefile_meta}')
    yield Info('info', f'handle Save Page WE meta: {handle_savepagewe_meta}')
    yield Info('info', f'handle MaoXian web clipper meta: {handle_maoxian_meta}')
    yield Info('info', '')

    try:
        conv = Converter(
            input, output,
            data_folder_suffixes=data_folder_suffixes,
            preserve_filename=preserve_filename,
            handle_ie_meta=handle_ie_meta,
            handle_singlefile_meta=handle_singlefile_meta,
            handle_savepagewe_meta=handle_savepagewe_meta,
            handle_maoxian_meta=handle_maoxian_meta,
        )
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
