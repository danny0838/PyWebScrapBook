"""Command line interface of WebScrapBook toolkit.
"""
import sys
import os
import shutil
import argparse
from getpass import getpass
import traceback
from inspect import getdoc

# this package
from . import __package_name__, __version__
from . import *
from . import server
from . import util
from ._compat.time import time_ns


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

    By default the local browser will be launched to view the served (hosted) site.
    This behavior can be changed using the `server.browse` config.

    Note that this built-in server is designed only for local hosting, or remote
    hosting for personal or few people usage. For an opened world wide web hosting,
    a more specialized server should be used."""
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
                die(f"Unable to generate {fdst}.")

        if args['edit']:
            try:
                util.launch(fdst)
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
                    die(f"Unable to generate {fdst}.")

            fdst = os.path.normpath(os.path.join(args['root'], WSB_DIR, 'app.py'))
            fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', 'app.py'))
            if not os.path.isfile(fdst):
                log(f'Generating "{fdst}"...')
                try:
                    fcopy(fsrc, fdst)
                    os.chmod(fdst, os.stat(fdst).st_mode | (0o111 & ~get_umask()))
                except OSError:
                    die(f"Unable to generate {fdst}.")

    elif args['user']:
        fdst = WSB_USER_CONFIG
        fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', 'config.ini'))
        if not os.path.isfile(fdst):
            log(f'Generating "{fdst}"...')
            try:
                fcopy(fsrc, fdst)
            except OSError:
                die(f"Unable to generate {fdst}.")

        if args['edit']:
            try:
                util.launch(fdst)
            except OSError:
                pass

    elif args['edit']:
        die("Use --edit in combine with --book or --user.")

    elif args['all']:
        die("Use --all in combine with --book.")

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
    if args['password'] is None:
        pw1 = getpass('Enter a password: ')
        pw2 = getpass('Confirm the password: ')

        if pw1 != pw2:
            die('Entered passwords do not match.')

        args['password'] = pw1

    print(util.encrypt(args['password'], salt=args['salt'], method=args['method']))


def cmd_cache(args):
    """Generate (or update) fulltext cache and/or static site pages.
    """
    kwargs = args.copy()
    debug = kwargs.pop('debug')

    from .scrapbook import cache
    for info in cache.generate(**kwargs):
        if info.type != 'debug' or debug:
            log(f'{info.type.upper()}: {info.msg}')


def cmd_check(args):
    """Integrity check and fix for scrapbook data.

    (TOC = table of contents)
    """
    kwargs = args.copy()
    debug = kwargs.pop('debug')

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

    import importlib
    try:
        conv = importlib.import_module(f'.scrapbook.convert.{mode}', __package__)
    except ImportError:
        die(f'Unsupported conversion mode: "{mode}".')

    # validate input and output directory
    args['input'] = os.path.realpath(args['input'])
    args['output'] = os.path.realpath(args['output'])

    if os.path.normcase(args['output']) == os.path.normcase(args['input']):
        die(f'''Unable to output to the input directory''')

    if os.path.normcase(args['output']).startswith(os.path.normcase(os.path.join(args['input'], ''))):
        die(f'''Unable to output to a descendant of the input directory''')

    if os.path.normcase(args['input']).startswith(os.path.normcase(os.path.join(args['output'], ''))):
        die(f'''Unable to output to an ancestor of the input directory''')

    if not os.path.isdir(args['input']):
        die(f'''Input directory not available: "{args['input']}"''')

    if not os.path.lexists(args['output']):
        pass
    elif not os.path.isdir(args['output']):
        die(f'''Output directory not available: "{args['output']}"''')
    else:
        if force:
            # using os.rmtree() frequently cause an error on Windows
            with os.scandir(args['output']) as dirs:
                for entry in dirs:
                    try:
                        shutil.rmtree(entry)
                    except NotADirectoryError:
                        os.remove(entry)
        else:
            with os.scandir(args['output']) as dirs:
                if next(dirs, None):
                    die(f'''Output directory not empty: "{args['output']}"''')

    for info in conv.run(**kwargs):
        if info.type != 'debug' or debug:
            log(f'{info.type.upper()}: {info.msg}')


def cmd_help(args):
    """Show detailed information about certain topics.
    """
    root = os.path.join(os.path.dirname(__file__), 'resources')

    if args['topic'] == 'config':
        file = os.path.join(root, 'config.md')
        with open(file, 'r', encoding='UTF-8') as f:
            text = f.read()
        print(text)


def cmd_view(args):
    """View archive file(s) in the browser.
    """
    config.load(args['root'])
    view_archive_files(args['files'])


def view_archive_files(files):
    """View archive file(s) in the browser.

    Set default application of MAFF/HTZ archive files to this command to open
    them in the browser directly.
    """
    import tempfile
    import zipfile
    import mimetypes
    import webbrowser
    from urllib.request import pathname2url

    cache_prefix = config['browser']['cache_prefix']
    cache_expire = config['browser']['cache_expire'] * 10 ** 9
    use_jar = config['browser']['use_jar']
    browser = webbrowser.get(config['browser']['command'] or None)

    temp_dir = tempfile.gettempdir()
    urls = []

    for file in dict.fromkeys(os.path.normcase(os.path.abspath(file)) for file in files):
        mime, _ = mimetypes.guess_type(file)
        if mime not in ("application/html+zip", "application/x-maff"):
            continue

        if use_jar:
            base_url = 'jar:file:' + pathname2url(file) + '!/'
            if mime == "application/html+zip":
                urls.append(base_url + 'index.html')
            elif mime == "application/x-maff":
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
                atime = time_ns()
                stat = os.stat(entry)
                os.utime(entry, ns=(atime, stat.st_mtime_ns))
                break
            else:
                dest_dir = tempfile.mkdtemp(prefix=dest_prefix)
                with zipfile.ZipFile(file) as zip:
                    zip.extractall(dest_dir)

        # get URL of every index page
        base_url = 'file:' + pathname2url(dest_dir) + '/'
        if mime == "application/html+zip":
            urls.append(base_url + 'index.html')
        elif mime == "application/x-maff":
            urls.extend(base_url + f.indexfilename for f in util.get_maff_pages(file))

    # open pages in the browser
    for url in urls:
        browser.open(url)

    # remove stale caches
    if not use_jar:
        t = time_ns()
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
    parser.add_argument('files', nargs='+',
        help="""files to view.""")
    args = vars(parser.parse_args())
    view_archive_files(args['files'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=f'{__package_name__} {__version__}',
        help="""show version information and exit""")
    parser.add_argument('--root', default=".",
        help="""root directory to manipulate (default: current working directory)""")
    subparsers = parser.add_subparsers(metavar='COMMAND',
        help="""the sub-command to run. Get usage help with e.g. %(prog)s config -h""")

    # subcommand: serve
    parser_serve = subparsers.add_parser('serve', aliases=['s'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_serve),
        help="""serve the root directory""")
    parser_serve.add_argument('--browse', default=None, action='store_true',
        help="""launch the browser to visit the served directory""")
    parser_serve.add_argument('--no-browse', dest='browse', action='store_false',
        help="""do not launch the browser""")
    parser_serve.set_defaults(func=cmd_serve)

    # subcommand: config
    parser_config = subparsers.add_parser('config', aliases=['c'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_config),
        help="""show, generate, or edit the config""")
    parser_config.set_defaults(func=cmd_config)
    parser_config.add_argument('name', nargs='?',
        help="""show value of the given config name (in the form of <section>[.<subsection>].<key>)""")
    parser_config.add_argument('-b', '--book', default=False, action='store_true',
        help="""generate book (host) config file""")
    parser_config.add_argument('-u', '--user', default=False, action='store_true',
        help="""generate user config file""")
    parser_config.add_argument('-a', '--all', default=False, action='store_true',
        help="""generate more assistant files (with --book)""")
    parser_config.add_argument('-e', '--edit', default=False, action='store_true',
        help="""edit the config file (with --book or --user)""")

    # subcommand: encrypt
    parser_encrypt = subparsers.add_parser('encrypt', aliases=['e'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_encrypt),
        help="""generate an encrypted password""")
    parser_encrypt.set_defaults(func=cmd_encrypt)
    parser_encrypt.add_argument('-p', '--password', nargs='?', default=None, action='store',
        help="""the password to encrypt. Skip to provide via an interactive prompt.""")
    parser_encrypt.add_argument('-m', '--method', default='sha1', action='store',
        help="""the encrypt method to use, which is one of: plain, md5, sha1,
sha224, sha256, sha384, sha512, sha3_224, sha3_256, sha3_384, and sha3_512
(default: %(default)s)""")
    parser_encrypt.add_argument('-s', '--salt', default='', action='store',
        help="""the salt to add during encryption.""")

    # subcommand: cache
    parser_cache = subparsers.add_parser('cache', aliases=['a'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_cache),
        help="""update fulltext cache and/or static site pages""")
    parser_cache.set_defaults(func=cmd_cache)
    parser_cache.add_argument('book_ids', metavar='book', nargs='*', action='store',
        help="""the book ID(s) to generate cache. (default: all books)""")
    parser_cache.add_argument('--item', dest='item_ids',
        metavar='ID', action='store', default=None, nargs='+',
        help="""the items ID(s) to generate cache (default: all)""")
    parser_cache.add_argument('--fulltext', default=True, action='store_true',
        help="""generate fulltext cache. (default)""")
    parser_cache.add_argument('--no-fulltext', dest='fulltext', action='store_false',
        help="""inverse of --fulltext""")
    parser_cache.add_argument('--inclusive-frames', default=True, action='store_true',
        help="""cache frame content as part of the main page (default). It's
recommended to recreate fulltext cache when changing this option to prevent
inconsistency.""")
    parser_cache.add_argument('--no-inclusive-frames', dest='inclusive_frames', action='store_false',
        help="""inverse of --inclusive-frames""")
    parser_cache.add_argument('--recreate', dest='recreate', default=False, action='store_true',
        help="""ignore current fulltext cache and generate again""")
    parser_cache.add_argument('--no-recreate', dest='recreate', action='store_false',
        help="""inverse of --recreate (default)""")
    parser_cache.add_argument('--static-site', default=False, action='store_true',
        help="""generate static site pages""")
    parser_cache.add_argument('--no-static-site', dest='static_site', action='store_false',
        help="""inverse of --static-site (default)""")
    parser_cache.add_argument('--static-index', default=False, action='store_true',
        help="""generate static index.html page""")
    parser_cache.add_argument('--no-static-index', dest='static_index', action='store_false',
        help="""inverse of --static-index (default)""")
    parser_cache.add_argument('--rss-root', metavar='ROOT_URL', action='store',
        help="""generate an RSS feed file for the book, using the specified root URL
        (usually corresponds to webscrapbook app root)""")
    parser_cache.add_argument('--rss-item-count', default=50, type=int, action='store',
        help="""number of items the RSS feed should include (default: %(default)s)""")
    parser_cache.add_argument('--locale', action='store',
        help="""locale for the generated pages (default: system locale)""")
    parser_cache.add_argument('--backup', dest='no_backup', default=True, action='store_false',
        help="""backup changed files""")
    parser_cache.add_argument('--no-backup', action='store_true',
        help="""do not backup changed files (default)""")
    parser_cache.add_argument('--debug', default=False, action='store_true',
        help="""include debug output""")

    # subcommand: check
    parser_check = subparsers.add_parser('check', aliases=['k'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_check),
        help="""check and fix scrapbook data""")
    parser_check.set_defaults(func=cmd_check)
    parser_check.add_argument('book_ids', metavar='book', nargs='*', action='store',
        help="""the book ID(s) to check. (default: all books)""")

    parser_check.add_argument('-r', '--resolve', dest='resolve_all', default=False, action='store_true',
        help="""resolve all found issues (implies all --resolve-*)""")
    parser_check.add_argument('--resolve-invalid-id', default=False, action='store_true',
        help="""remove items with invalid ID from metadata entries""")
    parser_check.add_argument('--resolve-missing-index', default=False, action='store_true',
        help="""remove items with missing index property from metadata entries""")
    parser_check.add_argument('--resolve-missing-index-file', default=False, action='store_true',
        help="""remove items with missing index file from metadata entries""")
    parser_check.add_argument('--resolve-missing-date', default=False, action='store_true',
        help="""attempt to generate "create" and "modify" properties for items missing any of them""")
    parser_check.add_argument('--resolve-older-mtime', default=False, action='store_true',
        help="""update "modify" property if it's older than last modified time of the index file""")
    parser_check.add_argument('--resolve-toc-unreachable', default=False, action='store_true',
        help="""append items unreachable from TOC to the root tree""")
    parser_check.add_argument('--resolve-toc-invalid', default=False, action='store_true',
        help="""remove invalid items from TOC""")
    parser_check.add_argument('--resolve-toc-empty-subtree', default=False, action='store_true',
        help="""remove items with empty subtree from TOC""")
    parser_check.add_argument('--resolve-unindexed-files', default=False, action='store_true',
        help="""attempt to import unindexed files to metadata and TOC""")
    parser_check.add_argument('--resolve-absolute-icon', default=False, action='store_true',
        help="""cache "icon" property with absolute URL to local favicon directory""")
    parser_check.add_argument('--resolve-unused-icon', default=False, action='store_true',
        help="""remove unused favicon caches""")

    parser_check.add_argument('--no-backup', default=False, action='store_true',
        help="""do not backup changed files""")
    parser_check.add_argument('--debug', default=False, action='store_true',
        help="""include debug output""")

    # subcommand: convert
    parser_convert = subparsers.add_parser('convert', aliases=['v'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_convert),
        help="""convert scrapbook data between different formats""")
    parser_convert.set_defaults(func=cmd_convert)
    parser_convert_sub = parser_convert.add_subparsers(dest='mode', metavar='MODE', required=True,
        help="""the conversion mode. Get usage help with e.g. %(prog)s sb2wsb -h""")

    # -- sb2wsb
    parser_convert_sb2wsb = parser_convert_sub.add_parser('sb2wsb',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""Convert from legacy ScrapBook (X) to WebScrapBook.""",
        help="""convert from legacy ScrapBook (X) to WebScrapBook""")
    parser_convert_sb2wsb.add_argument('input', action='store',
        help="""the input directory""")
    parser_convert_sb2wsb.add_argument('output', action='store',
        help="""the output directory""")
    parser_convert_sb2wsb.add_argument('--no-backup', default=False, action='store_true',
        help="""do not backup unneeded legacy scrapbook files""")
    parser_convert_sb2wsb.add_argument('--force', default=False, action='store_true',
        help="""overwrite everything in the output directory""")
    parser_convert_sb2wsb.add_argument('--debug', default=False, action='store_true',
        help="""include debug output""")

    # -- wsb2sb
    parser_convert_wsb2sb = parser_convert_sub.add_parser('wsb2sb',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""Convert from WebScrapBook to legacy ScrapBook X

Note that certain information may lose permanently, such as:
* item appended to multiple parents (preserve only the first occurence)
* item in the recycle bin

Also note that compatibility validation of this tool is targeting ScrapBook X.
There may be minor compatibility issues if the output scrapbook is used by a
legacy ScrapBook implementation without features introduced by ScrapBook X,
such as:
* file with special or non-ASCII chars in filename
* container item whose type property is not "folder" """,
        help="""convert from WebScrapBook to legacy ScrapBook X""")
    parser_convert_wsb2sb.add_argument('input', action='store',
        help="""the input directory""")
    parser_convert_wsb2sb.add_argument('output', action='store',
        help="""the output directory""")
    parser_convert_wsb2sb.add_argument('--book', dest='book_id', metavar='ID',
        nargs='?', default='', action='store',
        help="""the book ID to convert. (default: "")""")
    parser_convert_wsb2sb.add_argument('--force', default=False, action='store_true',
        help="""overwrite everything in the output directory""")
    parser_convert_wsb2sb.add_argument('--debug', default=False, action='store_true',
        help="""include debug output""")

    # subcommand: help
    parser_help = subparsers.add_parser('help',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_help),
        help="""show detailed information about certain topics""")
    parser_help.set_defaults(func=cmd_help)
    parser_help.add_argument('topic', default=None, action='store',
        choices=['config'],
        help="""the topic for details""")

    # subcommand: view
    parser_view = subparsers.add_parser('view',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=getdoc(cmd_view),
        help="""view archive file in the browser""")
    parser_view.set_defaults(func=cmd_view)
    parser_view.add_argument('files', nargs='+',
        help="""files to view""")

    # parse the command
    args = vars(parser.parse_args())
    try:
        func = args.pop('func')
    except KeyError:
        parser.parse_args(['-h'])
    else:
        func(args)


if __name__ == '__main__':
    main()
