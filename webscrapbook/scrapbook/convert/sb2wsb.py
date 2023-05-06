import os
import re
import shutil
import time
import traceback
from datetime import datetime
from urllib.parse import unquote
from urllib.request import pathname2url

from lxml import etree

from ... import WSB_CONFIG, WSB_DIR, util
from ...util import Info
from ..host import Host

RDF = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'
NS1 = '{http://amb.vis.ne.jp/mozilla/scrapbook-rdf#}'
NS2 = '{scrapbee@163.com}'  # ScrapBee
NC = '{http://home.netscape.com/NC-rdf#}'
RES_PROTOCOL_BASE = 'resource://scrapbook/'
MOZ_ICON_BASE = 'moz-icon://'

REGEX_ID = re.compile(r'\d{14,23}')
REGEX_RDF_ID = re.compile(r'urn:scrapbook:item(\d{14,23})')
REGEX_RDF_SEQ_ID = re.compile(r'urn:scrapbook:(?:item(\d{14,23})|(root))')

LEGACY_TYPE_MAP = {
    'note': 'postit',
    'notex': 'note',
}

PRUNE_FILES = {
    'backup',
    'tree',
    'scrapbook.rdf',
    'cache.rdf',
    'folders.txt',
    'collection.html',
    'combine.html',
    'combine.css',
    'note.html',
    'search.html',
    'sitemap.xsl',
    'note_template.html',
    'notex_template.html',
}


class LegacyBook:
    """Main legacy scrapbook book controller.
    """
    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.meta = {}
        self.toc = {'root': []}
        self.rdf_mtime = 0
        self.sitemaps = {}
        self.modifies = {}

    def load(self):
        yield Info('info', "Loading 'scrapbook.rdf'...")
        yield from self._load_rdf()
        yield Info('info', 'Inspecting data directory...')
        yield from self._load_data_dir()

    def _load_rdf(self):
        rdf_file = os.path.join(self.root, 'scrapbook.rdf')
        try:
            self.rdf_mtime = os.stat(rdf_file).st_mtime
            with open(rdf_file, 'rb') as fh:
                yield from self._parse_rdf(fh)
        except OSError as exc:
            raise RuntimeError(f"Unable to load 'scrapbook.rdf': {exc.strerror}") from exc
        except etree.XMLSyntaxError as exc:
            raise RuntimeError(f"Malformed 'scrapbook.rdf': {exc.args[0]}") from exc

    def _parse_rdf(self, fh):
        for _event, elem in etree.iterparse(
            fh, events=('end',),
            remove_comments=True, encoding='UTF-8',
            tag=(f'{RDF}Description', f'{NC}BookmarkSeparator', f'{RDF}Seq'),
        ):
            yield Info('debug', f'Inspecting element: {elem.tag} ({elem.attrib.get(f"{RDF}about")})')
            if elem.tag in {f'{RDF}Description', f'{NC}BookmarkSeparator'}:
                rid = elem.attrib[f'{RDF}about']
                rid_match = REGEX_RDF_ID.match(rid)
                if not rid_match:
                    continue

                id = rid_match.group(1)
                meta = {'id': id}
                for attr, value in elem.attrib.items():
                    if attr.startswith(NS1) and attr != f'{NS1}id':
                        meta[attr[len(NS1):]] = value
                    elif attr.startswith(NS2) and attr != f'{NS2}id':
                        meta[attr[len(NS2):]] = value
                self.meta.setdefault(id, {}).update(meta)

            elif elem.tag == f'{RDF}Seq':
                rid = elem.attrib[f'{RDF}about']
                rid_match = REGEX_RDF_SEQ_ID.match(rid)
                if not rid_match:
                    continue

                id = rid_match.group(1) or rid_match.group(2)

                for child in elem:
                    if child.tag == f'{RDF}li':
                        ref_rid = child.attrib[f'{RDF}resource']
                        ref_rid_match = REGEX_RDF_ID.match(ref_rid)
                        if not ref_rid_match:
                            continue

                        ref_id = ref_rid_match.group(1)
                        self.toc.setdefault(id, []).append(ref_id)

            # clean up to save memory
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

    def _load_data_dir(self, load_index_dat=False):
        try:
            dirs = os.scandir(os.path.join(self.root, 'data'))
        except (FileNotFoundError, NotADirectoryError):
            yield Info('debug', 'Skipped inspecting data directory (not found)')
            return
        except OSError as exc:
            raise RuntimeError(f'Failed to scan data directory: {exc.strerror}') from exc

        with dirs as dirs:
            for dir in dirs:
                # check name as ID
                id = dir.name
                yield Info('debug', f'Inspecting item folder {id!r}')
                match_id = REGEX_ID.match(id)
                if not match_id:
                    yield Info('warn', f'Skipped item folder {id!r} (invalid ID)')
                    continue

                # check index.html
                index_file = os.path.join(dir, 'index.html')
                if not os.path.isfile(index_file):
                    yield Info('debug', f"Skipped item folder {id!r} (missing 'index.html')")
                    continue

                # record mtime of index.html
                ts = os.stat(index_file).st_mtime
                mtime = datetime.fromtimestamp(ts)
                modify = util.datetime_to_id(mtime)
                self.modifies[id] = modify

                # record seen sitemap.xml
                sitemap_file = os.path.join(dir, 'sitemap.xml')
                if os.path.isfile(sitemap_file):
                    self.sitemaps[id] = True

                # load index.dat
                if load_index_dat:
                    yield Info('debug', f"Checking 'index.dat' for {id!r}")
                    index_dat_file = os.path.join(dir, 'index.dat')
                    try:
                        assert os.stat(index_dat_file).st_mtime > self.rdf_mtime
                    except (FileNotFoundError, IsADirectoryError, NotADirectoryError, AssertionError):
                        continue
                    except OSError as exc:
                        yield Info('error', f"Failed to read 'index.dat' for {id!r}: {exc.strerror}", exc=exc)
                        continue

                    yield Info('info', f"Reading metadata from newer 'index.dat' for {id!r}")
                    try:
                        with open(index_dat_file, encoding='UTF-8') as fh:
                            meta = {}
                            for line in fh:
                                line = line.rstrip('\n')
                                key, _, value = line.partition('\t')
                                if not value:
                                    continue
                                meta[key] = value
                            self.meta.setdefault(id, {}).update(meta)
                    except OSError as exc:
                        yield Info('error', f"Failed to read 'index.dat' for {id!r}: {exc.strerror}", exc=exc)
                        continue


class Converter:
    def __init__(self, input, output, *, data_files=True, backup=True):
        self.input = os.path.realpath(input)
        self.output = os.path.realpath(output)
        self.data_files = data_files
        self.backup = backup

        self.index_files = {}

    def run(self):
        fsrc = os.path.normpath(os.path.join(__file__, '..', '..', '..', 'resources', 'config.ini'))
        fdst = os.path.normpath(os.path.join(self.output, WSB_DIR, WSB_CONFIG))

        yield Info('info', 'Generating directory...')
        os.makedirs(os.path.dirname(fdst), exist_ok=True)

        if not os.path.isfile(fdst):
            yield Info('info', 'Generating config file...')
            try:
                shutil.copyfile(fsrc, fdst)
            except OSError as exc:
                yield Info('error', f'Unable to generate config file: {exc}', exc=exc)

        yield Info('info', 'Setting up new scrapbook...')
        host = Host(self.output)
        book = host.books['']
        book.load_meta_files()
        book.load_toc_files()

        if self.backup:
            host.init_auto_backup(note='convert-sb2wsb')

        try:
            yield Info('info', 'Loading legacy scrapbook data...')
            book0 = LegacyBook(self.input)
            yield from book0.load()

            yield Info('info', 'Calculating tree data...')
            yield from self._merge_meta(book, book0)
            yield from self._merge_toc(book, book0)

            yield Info('info', 'Copying data files...')
            yield from self._copy_data_files(book, book0)

            if self.data_files:
                yield from self._convert_data_files(book, book0)

            yield Info('info', 'Saving tree files...')
            book.save_meta_files()
            book.save_toc_files()
        finally:
            if self.backup:
                host.init_auto_backup(False)

    def _merge_meta(self, book, book0):
        for id0, meta0 in book0.meta.items():
            yield Info('debug', f'Inspecting item metadata for {id0!r}')
            id = id0
            meta = meta0.copy()

            # meta['type'], meta['marked']
            meta['type'] = LEGACY_TYPE_MAP.get(meta.get('type'), meta.get('type', ''))
            if meta['type'] == 'marked':
                # if sitemap exists, type should be site
                meta['type'] = 'site' if id in book0.sitemaps else ''
                meta['marked'] = True

            # meta['index']
            if meta['type'] not in book.ITEM_TYPES_WITH_OPTIONAL_INDEX:
                meta['index'] = f'{id}/index.html'
            elif meta.get('icon', '').startswith(f'{RES_PROTOCOL_BASE}data/{id}/'):
                # Add a dummy index.html to relate the icon file with the item
                # if it's saved in the item directory. (mainly for ScrapBee)
                meta['index'] = f'{id}/index.html'
                self.index_files[os.path.normpath(os.path.join(book.data_dir, id, 'index.html'))] = True
                yield Info('debug', f'Registering dummy file {meta["index"]!r}')

            # meta['create']
            # fallback to id
            if meta.get('create'):
                meta['create'] = util.datetime_to_id(util.id_to_datetime_legacy(meta['create']))
            else:
                meta['create'] = util.datetime_to_id(util.id_to_datetime_legacy(id))

            # meta['modify']
            # fallback to mtime of index.html and then create (and then id)
            if meta.get('modify'):
                meta['modify'] = util.datetime_to_id(util.id_to_datetime_legacy(meta['modify']))
            else:
                try:
                    meta['modify'] = book0.modifies[id]
                except KeyError:
                    meta['modify'] = meta['create']

            # meta['icon']
            # resolve resource://scrapbook/* and moz-icon://*
            if meta.get('icon', '').startswith(RES_PROTOCOL_BASE):
                if meta.get('index'):
                    src = os.path.normpath(os.path.join(book.data_dir, id))
                else:
                    src = os.path.normpath(book.data_dir)
                dst = os.path.normpath(os.path.join(book.top_dir, unquote(meta['icon'][len(RES_PROTOCOL_BASE):])))
                rel_path = os.path.relpath(dst, src)
                meta['icon'] = pathname2url(rel_path)  # this quotes URL
            elif meta.get('icon', '').startswith(MOZ_ICON_BASE):
                meta['icon-moz'] = meta['icon']
                meta['icon'] = ''

            # meta['comment']
            try:
                if meta['comment']:
                    meta['comment'] = meta['comment'].replace(' __BR__ ', '\n')
            except KeyError:
                pass

            # meta['charset']
            try:
                if meta['chars']:
                    meta['charset'] = meta['chars']
                del meta['chars']
            except KeyError:
                pass

            # meta['lock']
            try:
                if meta['lock']:
                    meta['locked'] = True
                del meta['lock']
            except KeyError:
                pass

            # meta['folder']
            # this should not appear in scrapbook.rdf normally
            try:
                del meta['folder']
            except KeyError:
                pass

            # meta['exported']
            # this should not appear in scrapbook.rdf normally
            try:
                del meta['exported']
            except KeyError:
                pass

            # meta['container']
            # this should not appear in scrapbook.rdf normally
            try:
                del meta['container']
            except KeyError:
                pass

            # add to book
            book.add_item(meta, None)

    def _merge_toc(self, book, book0):
        book.toc.update(book0.toc)
        return
        yield

    def _copy_data_files(self, book, book0):
        with os.scandir(self.input) as dirs:
            for src in dirs:
                if src.name == WSB_DIR:
                    yield Info('warn', f'Skipped copying special directory {WSB_DIR!r}')
                    continue

                if src.name in PRUNE_FILES:
                    if self.backup:
                        yield Info('debug', f'Backup legacy scrapbook entry {src.name!r}')
                        book.backup(src, base=self.input)
                        continue
                    else:
                        yield Info('debug', f'Skipped legacy scrapbook entry {src.name!r}')
                        continue

                dst = os.path.join(book.top_dir, src.name)

                try:
                    shutil.copytree(src, dst)
                except NotADirectoryError:
                    shutil.copy2(src, dst)

        # generate registered dummy index files
        for path in self.index_files:
            if not os.path.lexists(path):
                yield Info('debug', f'Generating registered dummy file {path!r}')
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'wb'):
                    pass

    def _convert_data_files(self, book, book0):
        from .migrate import ConvertDataFilesLegacy
        converter = ConvertDataFilesLegacy(book)
        yield from converter.run()


def run(input, output, *, data_files=True, backup=True):
    start = time.time()
    yield Info('info', 'conversion mode: ScrapBook --> WebScrapBook')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output)}')
    yield Info('info', f'data-files: {data_files}')
    yield Info('info', f'backup: {backup}')
    yield Info('info', '')

    try:
        conv = Converter(input, output, data_files=data_files, backup=backup)
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
