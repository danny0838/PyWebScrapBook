"""Command line interface of WebScrapBook toolkit.
"""
import argparse
import os
import shutil
import sys
import time
import traceback
from getpass import getpass
from inspect import getdoc

from . import WSB_CONFIG, WSB_DIR, WSB_USER_CONFIG, __version__, config, util
from ._polyfill.argparse import BooleanOptionalAction


def log(*args):
    print(*args)


def die(*args):
    print('Error:', *args, file=sys.stderr)
    sys.exit(1)


def get_umask():
    """Get configured umask.
    """
    umask = os.umask(0)
    os.umask(umask)
    return umask


def fcopy(fsrc, fdst):
    """Copy a script file to target

    - Auto generate ancestor directories.
    - Use universal linefeed.
    - Set last modified time to current time.
    """
    os.makedirs(os.path.dirname(os.path.abspath(fdst)), exist_ok=True)
    with open(fsrc, 'r', encoding='UTF-8') as fr:
        with open(fdst, 'w', encoding='UTF-8') as fw:
            for line in fr:
                fw.write(line)


def cmd_serve(args):
    """Serve the root directory forever. Shutdown via Ctrl+C or another killing
    technique.

    Note that this built-in server is designed only for local hosting, or remote
    hosting for personal or few people usage. For an opened world wide web hosting,
    a more specialized server should be used.
    """
    from . import server
    server.serve(**args)


def cmd_config(args):
    """Show, generate, or edit the config.

    Display the current config when used with no arguments.

    Run `wsb help config` for details about config.
    """
    if args['book']:
        fdst = os.path.normpath(os.path.join(args['root'], WSB_DIR, WSB_CONFIG))
        fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', 'config.ini'))
        if not os.path.isfile(fdst):
            log(f'Generating "{fdst}"...')
            try:
                fcopy(fsrc, fdst)
            except OSError:
                die(f'Unable to generate {fdst}.')

        if args['edit']:
            try:
                util.fs.launch(fdst)
            except OSError:
                pass

        if args['all']:
            fdst = os.path.normpath(os.path.join(args['root'], WSB_DIR, 'serve.py'))
            fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', 'serve.py'))
            if not os.path.isfile(fdst):
                log(f'Generating "{fdst}"...')
                try:
                    fcopy(fsrc, fdst)
                    os.chmod(fdst, os.stat(fdst).st_mode | (0o111 & ~get_umask()))
                except OSError:
                    die(f'Unable to generate {fdst}.')

            fdst = os.path.normpath(os.path.join(args['root'], WSB_DIR, 'app.py'))
            fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', 'app.py'))
            if not os.path.isfile(fdst):
                log(f'Generating "{fdst}"...')
                try:
                    fcopy(fsrc, fdst)
                    os.chmod(fdst, os.stat(fdst).st_mode | (0o111 & ~get_umask()))
                except OSError:
                    die(f'Unable to generate {fdst}.')

    elif args['user']:
        fdst = WSB_USER_CONFIG
        fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', 'config.ini'))
        if not os.path.isfile(fdst):
            log(f'Generating "{fdst}"...')
            try:
                fcopy(fsrc, fdst)
            except OSError:
                die(f'Unable to generate {fdst}.')

        if args['edit']:
            try:
                util.fs.launch(fdst)
            except OSError:
                pass

    elif args['edit']:
        die('Use --edit in combine with --book or --user.')

    elif args['all']:
        die('Use --all in combine with --book.')

    elif args['name']:
        config.load(args['root'])
        value = config.getname(args['name'])

        if value is None:
            die(f"""Config entry "{args['name']}" does not exist""")

        print(value)

    else:
        config.load(args['root'])
        config.dump(sys.stdout)


def cmd_encrypt(args):
    """Generate an encrypted password string.

    Primilarly to be used in auth config.
    """
    pw = args['password']
    if pw is None:
        pw1 = getpass('Enter a password: ')
        pw2 = getpass('Confirm the password: ')

        if pw1 != pw2:
            die('Entered passwords do not match.')

        pw = pw1

    print(util.encrypt(pw, salt=args['salt'], method=args['method']))


def cmd_cache(args):
    """Generate (or update) fulltext cache and/or static site pages."""
    kwargs = args.copy()
    debug = kwargs.pop('debug')
    kwargs['no_backup'] = not kwargs.pop('backup')

    from .scrapbook import cache
    for info in cache.generate(**kwargs):
        if info.type != 'debug' or debug:
            log(f'{info.type.upper()}: {info.msg}')


def cmd_export(args):
    """Export data items into archive files (*.wsba).

    The export/import utilities provide a basic way to backup and restore the
    data and metadata (i.e. item properties) of specific item(s). Nevertheless,
    a technical limitation is that: if an item is referenced (i.e. be put under
    another item) multiple times, exporting may results in duplicated archive
    files and re-importing all of them cannot perfectly restore the original
    tree structure.

    For a reliable way to backup and restore the scrapbook tree as well as the
    items, it's generally more recommended to create another scrapbook and copy
    items between them.
    """
    kwargs = args.copy()
    debug = kwargs.pop('debug')

    from .scrapbook import exporter
    for info in exporter.run(**kwargs):
        if info.type != 'debug' or debug:
            log(f'{info.type.upper()}: {info.msg}')


def cmd_import(args):
    """Import data items from archive files (*.wsba).

    To faithfully reconstruct the original scrapbook tree, the archive files
    should be imported together using the same Unicode filename order as how
    they have been exported.

    To faithfully restore the timestamps for the imported files, the system
    timezone should be configured to be identical to the original timezone
    (i.e. the one where the archive has been generated in), as the ZIP archive
    does not record timezone information for the internal files. The 'timezone'
    property of the internal 'export.json' in the archive file can be consulted
    to infer the original timezone.
    """
    kwargs = args.copy()
    debug = kwargs.pop('debug')

    from .scrapbook import importer
    for info in importer.run(**kwargs):
        if info.type != 'debug' or debug:
            log(f'{info.type.upper()}: {info.msg}')


def cmd_check(args):
    """Integrity check and fix for scrapbook data.

    (TOC = table of contents)
    """
    kwargs = args.copy()
    debug = kwargs.pop('debug')
    kwargs['no_backup'] = not kwargs.pop('backup')

    from .scrapbook import check
    for info in check.run(**kwargs):
        if info.type != 'debug' or debug:
            log(f'{info.type.upper()}: {info.msg}')


def cmd_convert(args):
    """Convert data between different formats.

    Do not perform any data operation for the input and/or output directory
    during the conversion process (and related backend server(s) should be shut
    down in prior) to prevent a potential conversion error.
    """
    kwargs = args.copy()
    kwargs.pop('root')
    mode = kwargs.pop('mode')
    force = kwargs.pop('force')
    debug = kwargs.pop('debug')

    if mode == 'sb2wsb':
        kwargs['no_data_files'] = not kwargs.pop('data_files')
        kwargs['no_backup'] = not kwargs.pop('backup')
    elif mode == 'wsb2sb':
        kwargs['no_data_files'] = not kwargs.pop('data_files')
    elif mode == 'file2wsb':
        kwargs['no_preserve_filename'] = not kwargs.pop('preserve_filename')

    import importlib
    conv = importlib.import_module(f'.scrapbook.convert.{mode}', __package__)

    # validate input and output directory
    input = args['input']
    input = os.path.realpath(input)

    if not os.path.isdir(input):
        die(f'''Input directory not available: "{input}"''')

    output = args['output']
    if output is not None:
        output = os.path.realpath(output)

        if os.path.normcase(output) == os.path.normcase(input):
            die("""Unable to output to the input directory""")

        if os.path.normcase(output).startswith(os.path.normcase(os.path.join(input, ''))):
            die("""Unable to output to a descendant of the input directory""")

        if os.path.normcase(input).startswith(os.path.normcase(os.path.join(output, ''))):
            die("""Unable to output to an ancestor of the input directory""")

        if not os.path.lexists(output):
            pass
        elif not os.path.isdir(output):
            die(f'''Output directory not available: "{output}"''')
        else:
            if force:
                # using os.rmtree() frequently cause an error on Windows
                with os.scandir(output) as dirs:
                    for entry in dirs:
                        try:
                            shutil.rmtree(entry)
                        except NotADirectoryError:
                            os.remove(entry)
            else:
                with os.scandir(output) as dirs:
                    if next(dirs, None):
                        die(f'''Output directory not empty: "{output}"''')

    for info in conv.run(**kwargs):
        if info.type != 'debug' or debug:
            log(f'{info.type.upper()}: {info.msg}')


def cmd_help(args):
    """Show detailed information about certain topics."""
    root = os.path.join(os.path.dirname(__file__), 'resources')

    if args['topic'] == 'config':
        file = os.path.join(root, 'config.md')
    elif args['topic'] == 'themes':
        file = os.path.join(root, 'themes.md')
    elif args['topic'] == 'mimetypes':
        file = os.path.join(root, 'mimetypes.md')

    if file:
        with open(file, 'r', encoding='UTF-8') as fh:
            text = fh.read()
        print(text)


def cmd_view(args):
    """View archive file(s) in the browser.

    Supported formats: *.htz, *.maff
    """
    config.load(args['root'])
    view_archive_files(args['files'])


def view_archive_files(files):
    """View archive file(s) in the browser.

    Set default application of MAFF/HTZ archive files to this command to open
    them in the browser directly.
    """
    import tempfile
    import webbrowser
    from urllib.request import pathname2url

    from ._polyfill import mimetypes, zipfile

    cache_prefix = config['browser']['cache_prefix']
    cache_expire = config['browser']['cache_expire'] * 10 ** 9
    use_jar = config['browser']['use_jar']
    browser = webbrowser.get(config['browser']['command'] or None)

    temp_dir = tempfile.gettempdir()
    urls = []

    for file in dict.fromkeys(os.path.normcase(os.path.abspath(file)) for file in files):
        mime, _ = mimetypes.guess_type(file)
        if mime not in ('application/html+zip', 'application/x-maff'):
            continue

        if use_jar:
            base_url = 'jar:file:' + pathname2url(file) + '!/'
            if mime == 'application/html+zip':
                urls.append(base_url + 'index.html')
            elif mime == 'application/x-maff':
                urls.extend(base_url + f.indexfilename for f in util.get_maff_pages(file))
            continue

        # extract zip contents to dest_dir if not done yet
        hash = util.checksum(file)
        dest_prefix = cache_prefix + hash + '_'
        with os.scandir(temp_dir) as entries:
            for entry in entries:
                if not entry.name.startswith(dest_prefix):
                    continue

                dest_dir = entry.path

                # update atime
                atime = time.time_ns()
                stat = os.stat(entry)
                os.utime(entry, ns=(atime, stat.st_mtime_ns))
                break
            else:
                dest_dir = tempfile.mkdtemp(prefix=dest_prefix)
                with zipfile.ZipFile(file) as zh:
                    zh.extractall(dest_dir)

        # get URL of every index page
        base_url = 'file:' + pathname2url(dest_dir) + '/'
        if mime == 'application/html+zip':
            urls.append(base_url + 'index.html')
        elif mime == 'application/x-maff':
            urls.extend(base_url + f.indexfilename for f in util.get_maff_pages(file))

    # open pages in the browser
    for url in urls:
        browser.open(url)

    # remove stale caches
    if not use_jar:
        t = time.time_ns()
        with os.scandir(temp_dir) as entries:
            for entry in entries:
                if not entry.name.startswith(cache_prefix):
                    continue

                atime = os.stat(entry).st_atime_ns
                if t <= atime + cache_expire:
                    continue

                # cache may be created by another user and undeletable
                try:
                    shutil.rmtree(entry)
                except OSError:
                    traceback.print_exc()


def view():
    """CLI entry point for viewing archive files.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(view_archive_files))
    parser.add_argument(
        'files', metavar='file', nargs='+',
        help="""file(s) to view.""")
    args = vars(parser.parse_args())
    view_archive_files(args['files'])


def parse_args(argv=None):
    # Improve program name when executed through python -m
    # NOTE: We don't expect a bad command name such as having a space.
    if os.path.basename(sys.argv[0]) == '__main__.py':
        prog = f'{os.path.basename(sys.executable)} -m webscrapbook'
    else:
        prog = None

    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    parser.add_argument(
        '--version', action='version', version=f'{__package__} {__version__}',
        help="""show version information and exit""")
    parser.add_argument(
        '--root', default='.',
        help="""root directory to manipulate (default: current working directory)""")
    subparsers = parser.add_subparsers(
        metavar='COMMAND',
        help="""the sub-command to run. Get usage help with e.g. %(prog)s config -h""")

    # subcommand: serve
    parser_serve = subparsers.add_parser(
        'serve', aliases=['s'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_serve),
        help="""serve the root directory""")
    parser_serve.add_argument(
        '--browse', default=None, action=BooleanOptionalAction,
        help="""launch the browser to visit the served directory (default:
as `server.browse` config)""")
    parser_serve.set_defaults(func=cmd_serve)

    # subcommand: config
    parser_config = subparsers.add_parser(
        'config', aliases=['c'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_config),
        help="""show, generate, or edit the config""")
    parser_config.set_defaults(func=cmd_config)
    parser_config.add_argument(
        'name', nargs='?',
        help="""show value of the given config name (in the form of <section>[.<subsection>].<key>)""")
    parser_config.add_argument(
        '-b', '--book', default=False, action='store_true',
        help="""generate book (host) config file""")
    parser_config.add_argument(
        '-u', '--user', default=False, action='store_true',
        help="""generate user config file""")
    parser_config.add_argument(
        '-a', '--all', default=False, action='store_true',
        help="""generate more assistant files (with --book)""")
    parser_config.add_argument(
        '-e', '--edit', default=False, action='store_true',
        help="""edit the config file (with --book or --user)""")

    # subcommand: encrypt
    parser_encrypt = subparsers.add_parser(
        'encrypt', aliases=['e'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_encrypt),
        help="""generate an encrypted password""")
    parser_encrypt.set_defaults(func=cmd_encrypt)
    parser_encrypt.add_argument(
        '-p', '--password', nargs='?', default=None, action='store',
        help="""the password to encrypt. Skip to provide via an interactive prompt.""")
    parser_encrypt.add_argument(
        '-m', '--method', default='sha1', action='store',
        help="""the encrypt method to use, which is one of: plain, md5, sha1,
sha224, sha256, sha384, sha512, sha3_224, sha3_256, sha3_384, and sha3_512
(default: %(default)s)""")
    parser_encrypt.add_argument(
        '-s', '--salt', default='', action='store',
        help="""the salt to add during encryption""")

    # subcommand: cache
    parser_cache = subparsers.add_parser(
        'cache', aliases=['a'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_cache),
        help="""update fulltext cache and/or static site pages""")
    parser_cache.set_defaults(func=cmd_cache)
    parser_cache.add_argument(
        'book_ids', metavar='book', nargs='*', action='store',
        help="""the book ID(s) to generate cache (default: all books)""")
    parser_cache.add_argument(
        '--item', dest='item_ids',
        metavar='ID', action='store', default=None, nargs='+',
        help="""the items ID(s) to generate cache (default: all)""")
    parser_cache.add_argument(
        '--fulltext', default=True, action=BooleanOptionalAction,
        help="""generate fulltext cache (default: %(default)s)""")
    parser_cache.add_argument(
        '--inclusive-frames', default=True, action=BooleanOptionalAction,
        help="""cache frame content as part of the main page. It's recommended
to recreate fulltext cache when changing this option to prevent an
inconsistency. (default: %(default)s)""")
    parser_cache.add_argument(
        '--recreate', dest='recreate', default=False, action=BooleanOptionalAction,
        help="""ignore current fulltext cache and generate again
(default: %(default)s)""")
    parser_cache.add_argument(
        '--static-site', default=False, action=BooleanOptionalAction,
        help="""generate static site pages (default: %(default)s)""")
    parser_cache.add_argument(
        '--static-index', default=False, action=BooleanOptionalAction,
        help="""generate static index.html page (default: %(default)s)""")
    parser_cache.add_argument(
        '--rss-root', metavar='ROOT_URL', action='store',
        help="""generate an RSS feed file for the book, using the specified root URL
        (usually corresponds to webscrapbook app root)""")
    parser_cache.add_argument(
        '--rss-item-count', default=50, type=int, action='store',
        help="""number of items the RSS feed should include (default: %(default)s)""")
    parser_cache.add_argument(
        '--locale', action='store',
        help="""locale for the generated pages (default: as `app.locale` config)""")
    parser_cache.add_argument(
        '--backup', default=False, action=BooleanOptionalAction,
        help="""backup changed files (default: %(default)s)""")
    parser_cache.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # subcommand: check
    parser_check = subparsers.add_parser(
        'check', aliases=['k'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_check),
        help="""check and fix scrapbook data""")
    parser_check.set_defaults(func=cmd_check)
    parser_check.add_argument(
        'book_ids', metavar='book', nargs='*', action='store',
        help="""the book ID(s) to check (default: all books)""")

    parser_check.add_argument(
        '-r', '--resolve', dest='resolve_all', default=False, action='store_true',
        help="""resolve all found issues (implies all --resolve-*)""")
    parser_check.add_argument(
        '--resolve-invalid-id', default=False, action='store_true',
        help="""remove items with invalid ID from metadata entries""")
    parser_check.add_argument(
        '--resolve-missing-index', default=False, action='store_true',
        help="""remove items with missing index property from metadata entries""")
    parser_check.add_argument(
        '--resolve-missing-index-file', default=False, action='store_true',
        help="""remove items with missing index file from metadata entries""")
    parser_check.add_argument(
        '--resolve-missing-date', default=False, action='store_true',
        help="""attempt to generate "create" and "modify" properties for items missing any of them""")
    parser_check.add_argument(
        '--resolve-older-mtime', default=False, action='store_true',
        help="""update "modify" property if it's older than last modified time of the index file""")
    parser_check.add_argument(
        '--resolve-toc-unreachable', default=False, action='store_true',
        help="""append items unreachable from TOC to the root tree""")
    parser_check.add_argument(
        '--resolve-toc-invalid', default=False, action='store_true',
        help="""remove invalid items from TOC""")
    parser_check.add_argument(
        '--resolve-toc-empty-subtree', default=False, action='store_true',
        help="""remove items with empty subtree from TOC""")
    parser_check.add_argument(
        '--resolve-unindexed-files', default=False, action='store_true',
        help="""attempt to import unindexed files to metadata and TOC""")
    parser_check.add_argument(
        '--resolve-absolute-icon', default=False, action='store_true',
        help="""cache "icon" property with absolute URL to local favicon directory""")
    parser_check.add_argument(
        '--resolve-unused-icon', default=False, action='store_true',
        help="""remove unused favicon caches""")

    parser_check.add_argument(
        '--backup', default=True, action=BooleanOptionalAction,
        help="""backup changed files (default: %(default)s)""")
    parser_check.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # subcommand: export
    parser_export = subparsers.add_parser(
        'export', aliases=['x'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_export),
        help="""export data items into archive files (*.wsba)""")
    parser_export.set_defaults(func=cmd_export)
    parser_export.add_argument(
        'output', action='store',
        help="""the output directory""")
    parser_export.add_argument(
        '--book', dest='book_id', metavar='ID', default='', action='store',
        help="""the book ID to export (default: "")""")
    parser_export.add_argument(
        '--item', dest='item_ids',
        metavar='ID', action='store', default=None, nargs='+',
        help="""the items ID(s) to export (default: all)""")
    parser_export.add_argument(
        '-r', '--recursive', default=False, action='store_true',
        help="""recursively include descendant items of the provided item ID(s)""")
    parser_export.add_argument(
        '-s', '--singleton', default=False, action='store_true',
        help="""export only the first occurrence for an item referenced many times""")
    parser_export.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # subcommand: import
    parser_import = subparsers.add_parser(
        'import', aliases=['i'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_import),
        help="""import data items from archive files (*.wsba)""",
        epilog="""\
Available MODEs for --resolve-id-used:
  "skip": skip the import
  "replace": replace current metadata and data file(s)
  "new": import as a new item

Available placeholders for --filename PATTERN:
  "%%": a literal "%"
  "%ID%": item ID
  "%EID%": item export ID
  "%UUID%": a random UUID
  "%TITLE%": item title
  "%SOURCE%": item source URL
  "%CREATE%": item create time (allow SUBPATTERN)
  "%MODIFY%": item modify time (allow SUBPATTERN)
  "%EXPORT%": item export time (allow SUBPATTERN)

Datetime related ones can be written as %PATTERN:SUBPATTERN% for further
formatting with SUBPATTERN being one of these placeholders:
  "DATE": date (YYYY-MM-DD)
  "TIME": time (HH-MM-SS)
  "YEAR": year (YYYY)
  "MONTH": year (MM, 01-12)
  "DAY": day of month (DD, 01-31)
  "HOURS": hours (HH, 01-24)
  "MINUTES": minutes (MM, 00-59)
  "SECONDS": seconds (SS, 00-59)

All SUBPATTERNs can be prepended with "UTC_" for UTC time instead of local
time. For example, "%CREATE:UTC_DATE%".
""")
    parser_import.set_defaults(func=cmd_import)
    parser_import.add_argument(
        'files', metavar='file', action='store', nargs='+',
        help="""the file(s) to import in order. If a directory is provided, all
child files are imported in unicode filename order.""")
    parser_import.add_argument(
        '--book', dest='book_id', metavar='ID', default='', action='store',
        help="""the book ID to import into (default: "")""")
    parser_import.add_argument(
        '--target', dest='target_id', metavar='ID',
        default='root', action='store',
        help="""the target item ID to insert the imported items under (default: "%(default)s")""")
    parser_import.add_argument(
        '--target-index', metavar='INDEX',
        type=int, action='store',
        help="""the index number (starting from 0) the imported items will be
inserted at (default: last)""")
    parser_import.add_argument(
        '--rebuild-folders', default=False, action='store_true',
        help="""insert imported items under the original parent, and
auto-generate parent folders if not found (ignores --target and
--target-index)""")
    parser_import.add_argument(
        '--resolve-id-used', metavar='MODE',
        default='skip', action='store',
        choices={'skip', 'replace', 'new'},
        help="""what to do if an importing item ID already exists (default: "%(default)s")""")
    parser_import.add_argument(
        '--filename', dest='target_filename', metavar='PATTERN',
        default='%ID%', action='store',
        help="""formatter of the imported filename (default: "%(default)s")""")
    parser_import.add_argument(
        '--prune', default=False, action='store_true',
        help="""delete the archive file after successfully imported""")
    parser_import.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # subcommand: convert
    parser_convert = subparsers.add_parser(
        'convert', aliases=['v'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_convert),
        help="""convert scrapbook data between different formats""")
    parser_convert.set_defaults(func=cmd_convert)
    parser_convert_sub = parser_convert.add_subparsers(
        dest='mode', metavar='MODE',
        help="""the conversion mode. Get usage help with e.g. %(prog)s sb2wsb -h""")

    # -- migrate
    parser_convert_migrate = parser_convert_sub.add_parser(
        'migrate',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""\
Migrate a scrapbook to be compatible with the latest WebScrapBook version.
- WebScrapBook < 0.115: Migrate old shadow root loader and content data.
- WebScrapBook < 0.69: Migrate old canvas and shadow root loaders.

Also fix an incomplete conversion from legacy ScrapBook:
- Convert legacy annotations to be compatible with latest WebScrapBook.
- Convert legacy resources at chrome://scrapbook/skin/* to work in a browser
  without legacy ScrapBook add-on installed.
- Convert the index file of "postit" items for canonical wrapper and styling.
""",
        help="""migrate to latest WebScrapBook""")
    parser_convert_migrate.add_argument(
        'input', action='store',
        help="""the input directory""")
    parser_convert_migrate.add_argument(
        'output', action='store', nargs='?',
        help="""the output directory (default: in-place)""")
    parser_convert_migrate.add_argument(
        '--book', dest='book_ids', metavar='ID',
        nargs='+', action='store',
        help="""ID of the book(s) to convert (default: all books)""")
    parser_convert_migrate.add_argument(
        '--convert-legacy', default=True, action=BooleanOptionalAction,
        help="""convert data files from legacy ScrapBook (default: %(default)s)""")
    parser_convert_migrate.add_argument(
        '--convert-v1', default=True, action=BooleanOptionalAction,
        help="""convert data to latest WebScrapBook 1.* (default: %(default)s)""")
    parser_convert_migrate.add_argument(
        '--use-native-tags', default=False, action=BooleanOptionalAction,
        help="""use native HTML tags for converted legacy ScrapBook annotations for better
compatibility with very old browsers (e.g. IE < 9), with the cost of increased possibility
to conflict with the web page stylesheets (default: %(default)s)""")
    parser_convert_migrate.add_argument(
        '--force', default=False, action='store_true',
        help="""overwrite everything in the output directory""")
    parser_convert_migrate.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # -- items
    parser_convert_items = parser_convert_sub.add_parser(
        'items',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""Convert items in the scrapbook.""",
        help="""convert items in the scrapbook""",
        epilog="""\
Available FORMATs:
  "folder"       a folder with index.html and its resource files
  "htz"          a ZIP archive with index.html as entry
  "maff"         a ZIP archive with each page in an individial subfolder
  "single_file"  a single file with resources embedded in

* Conversion between "folder", "htz", and "maff" is mostly lostless (as long as
  no multi-page or arbitrary metadata is included in the MAFF file), while
  conversion between "single_file" and other formats may lose information
  permanently, such as filename and in-depth captured pages. Also note that
  some features are not supported for "single_file".

Available TYPEs:
  ""         a captured web page
  "site"     an in-depth captured web page set
  "file"     a captured or uploaded file
  "image"    an image file captured by legacy ScrapBook
  "note"     a note
  "postit"   a postit
  "combine"  a combined page generated by legacy ScrapBook
""")
    parser_convert_items.add_argument(
        'input', action='store',
        help="""the input directory""")
    parser_convert_items.add_argument(
        'output', action='store', nargs='?',
        help="""the output directory (default: in-place)""")
    parser_convert_items.add_argument(
        '--book', dest='book_ids', metavar='ID',
        nargs='+', action='store',
        help="""ID of the book(s) to convert (default: all books)""")
    parser_convert_items.add_argument(
        '--item', dest='item_ids', metavar='ID',
        nargs='+', action='store',
        help="""ID of the item(s) to convert (default: all items)""")
    parser_convert_items.add_argument(
        '--format', metavar='FORMAT', action='store',
        choices=['folder', 'htz', 'maff', 'single_file'],
        help="""file format to convert item(s) to (default: no conversion)""")
    parser_convert_items.add_argument(
        '--type', dest='types', metavar='TYPE', action='store', nargs='+',
        default=[''],
        choices=['', 'site', 'image', 'file', 'combine', 'note', 'postit', 'bookmark', 'folder', 'separator'],
        help="""item type(s) to convert (default: "")""")
    parser_convert_items.add_argument(
        '--force', default=False, action='store_true',
        help="""overwrite everything in the output directory""")
    parser_convert_items.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # -- sb2wsb
    parser_convert_sb2wsb = parser_convert_sub.add_parser(
        'sb2wsb',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""\
Convert a scrapbook from legacy ScrapBook to WebScrapBook.

The conversion is safe and lossless, with a few caveats:
- In-depth capture information is not converted and cannot be reused
  for a merge capture.
- Fulltext cache is not converted and requires a manual rebuild.

Known supported legacy scrapbook implementations:
- ScrapBook X (legacy Firefox Add-on)
- ScrapBook (legacy Firefox Add-on)
- ScrapBook Plus (legacy Firefox Add-on)
- ScrapBee (Firefox Quantum Add-on)""",
        help="""convert from legacy ScrapBook to WebScrapBook""")
    parser_convert_sb2wsb.add_argument(
        'input', action='store',
        help="""the input directory""")
    parser_convert_sb2wsb.add_argument(
        'output', action='store',
        help="""the output directory""")
    parser_convert_sb2wsb.add_argument(
        '--data-files', default=True, action=BooleanOptionalAction,
        help="""convert data files (set this if there's something wrong with
the conversion, and run "wsb convert migrate" afterwards for advanced options)
(default: %(default)s)""")
    parser_convert_sb2wsb.add_argument(
        '--backup', default=True, action=BooleanOptionalAction,
        help="""copy legacy ScrapBook files not needed by WebScrapBook
(default: %(default)s)""")
    parser_convert_sb2wsb.add_argument(
        '--force', default=False, action='store_true',
        help="""overwrite everything in the output directory""")
    parser_convert_sb2wsb.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # -- wsb2sb
    parser_convert_wsb2sb = parser_convert_sub.add_parser(
        'wsb2sb',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""\
Convert a scrapbook from WebScrapBook to legacy ScrapBook.

Fulltext cache is not converted and requires a manual rebuild.

Note that certain information may lose permanently, such as:
* items appended to multiple parents (preserve only the first occurence)
* items in the recycle bin
* inter-item links may break

Also note that compatibility validation of this tool is targeting ScrapBook X.
There may be minor compatibility issues if the output scrapbook is used by a
legacy ScrapBook implementation without features introduced by ScrapBook X,
such as:
* file with special or non-ASCII chars in filename
* container item whose type property is not "folder" """,
        help="""convert from WebScrapBook to legacy ScrapBook""")
    parser_convert_wsb2sb.add_argument(
        'input', action='store',
        help="""the input directory""")
    parser_convert_wsb2sb.add_argument(
        'output', action='store',
        help="""the output directory""")
    parser_convert_wsb2sb.add_argument(
        '--book', dest='book_id', metavar='ID',
        default='', action='store',
        help="""ID of the book to convert (default: "")""")
    parser_convert_wsb2sb.add_argument(
        '--data-files', default=True, action=BooleanOptionalAction,
        help="""convert data files (set this if there's something wrong for the
conversion) (default: %(default)s)""")
    parser_convert_wsb2sb.add_argument(
        '--force', default=False, action='store_true',
        help="""overwrite everything in the output directory""")
    parser_convert_wsb2sb.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # -- file2wsb
    parser_convert_file2wsb = parser_convert_sub.add_parser(
        'file2wsb',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""\
Convert hierarchical files to a WebScrapBook scrapbook.

This "imports" a folder with web page captures and possibly supporting folders
or sub-folders into structured scrapbook items. Metadata recorded by the
original capture tool, such as WebScrapBook, SingleFile, or native browser
saving, are translated into item metadata as much as possible. This is a lossy
conversion—the folder structure are changed and interlinkings may be broken.
""",
        help="""convert from hierarchical files to WebScrapBook""")
    parser_convert_file2wsb.add_argument(
        'input', action='store',
        help="""the input directory""")
    parser_convert_file2wsb.add_argument(
        'output', action='store',
        help="""the output directory""")
    parser_convert_file2wsb.add_argument(
        '--data-folder-suffix', dest='data_folder_suffixes',
        metavar='SUFFIX', default=None, action='store', nargs='*',
        help="""suffixes of the associated support folder (default: .files _files)""")
    parser_convert_file2wsb.add_argument(
        '--preserve-filename', default=True, action=BooleanOptionalAction,
        help="""keep the original filename and generate a wrapping subfolder
and redirecting index file for non-HTML files (default: %(default)s)""")
    parser_convert_file2wsb.add_argument(
        '--ignore-ie-meta', default=False, action='store_true',
        help="""ignore metadata generated by built-in save of Internet
Explorer or a Chromium-based browser""")
    parser_convert_file2wsb.add_argument(
        '--ignore-singlefile-meta', default=False, action='store_true',
        help="""ignore metadata generated by SingleFile browser extension""")
    parser_convert_file2wsb.add_argument(
        '--ignore-savepagewe-meta', default=False, action='store_true',
        help="""ignore metadata generated by Save Page WE browser extension""")
    parser_convert_file2wsb.add_argument(
        '--ignore-maoxian-meta', default=False, action='store_true',
        help="""ignore metadata generated by MaoXian web clipper browser extension""")
    parser_convert_file2wsb.add_argument(
        '--force', default=False, action='store_true',
        help="""overwrite everything in the output directory""")
    parser_convert_file2wsb.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # -- wsb2file
    parser_convert_wsb2file = parser_convert_sub.add_parser(
        'wsb2file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""\
Convert a WebScrapBook scrapbook to hierarchical files.

This turns the scrapbook items into structured physical folders and files to be
browsable with a file manager. Every output folder and file is prefixed with a
number (by default) to keep the original order in the tree. This is a lossy
conversion—item metadata are not preserved and interlinkings may be broken.

* For an item titled `MyItem` with index file `*/index.html`, its descendant
  items will be put under the `MyItem` subfolder, while its data files will be
  put under the `MyItem.htd` folder.
* A separator titled `MySep` will become the empty file `MySep.-`.
""",
        help="""convert from WebScrapBook to hierarchical files""")
    parser_convert_wsb2file.add_argument(
        'input', action='store',
        help="""the input directory""")
    parser_convert_wsb2file.add_argument(
        'output', action='store',
        help="""the output directory""")
    parser_convert_wsb2file.add_argument(
        '--book', dest='book_id', metavar='ID',
        default='', action='store',
        help="""ID of the book to convert (default: "")""")
    parser_convert_wsb2file.add_argument(
        '--prefix', default=True, action=BooleanOptionalAction,
        help="""prefix the output files with digits to keep the original tree
order (default: %(default)s)""")
    parser_convert_wsb2file.add_argument(
        '--force', default=False, action='store_true',
        help="""overwrite everything in the output directory""")
    parser_convert_wsb2file.add_argument(
        '--debug', default=False, action='store_true',
        help="""include debug output""")

    # subcommand: help
    parser_help = subparsers.add_parser(
        'help',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_help),
        help="""show detailed information about certain topics""",
        epilog="""\
Available TOPICs:
  "config"
  "themes"
  "mimetypes"
""")
    parser_help.set_defaults(func=cmd_help)
    parser_help.add_argument(
        'topic', metavar='TOPIC', default=None, action='store',
        choices=['config', 'themes', 'mimetypes'],
        help="""the topic for details""")

    # subcommand: view
    parser_view = subparsers.add_parser(
        'view',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_view),
        help="""view archive file in the browser""")
    parser_view.set_defaults(func=cmd_view)
    parser_view.add_argument(
        'files', metavar='file', nargs='+',
        help="""file(s) to view""")

    return parser.parse_args(argv)


def main(argv=None):
    args = vars(parse_args(argv))
    try:
        func = args.pop('func')
    except KeyError:
        parse_args(['-h'])
        return
    else:
        if func is cmd_convert and args['mode'] is None:
            parse_args(['convert', '-h'])
            return

        func(args)


if __name__ == '__main__':
    main()
