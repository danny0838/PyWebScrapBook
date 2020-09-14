#!/usr/bin/env python3
"""Command line interface of WebScrapBook toolkit.
"""
import sys
import os
import argparse
import json
from getpass import getpass
import time
import traceback

# this package
from . import __package_name__, __version__
from . import *
from . import server
from . import util
from ._compat.time import time_ns


def log(*args):
    print(*args)


def die(*args):
    print(f'Error:', *args, file=sys.stderr)
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
    """Serve the root directory."""
    server.serve(args['root'])


def cmd_config(args):
    """Show, generate, or edit config."""
    if args['book']:
        fdst = os.path.normpath(os.path.join(args['root'], WSB_DIR, WSB_LOCAL_CONFIG))
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
    """Generate encrypted password string."""
    if args['password'] is None:
        pw1 = getpass('Enter a password: ')
        pw2 = getpass('Confirm the password: ')

        if pw1 != pw2:
            die('Entered passwords do not match.')

        args['password'] = pw1

    print(util.encrypt(args['password'], salt=args['salt'], method=args['method']))


def cmd_help(args):
    """Show detailed information."""
    root = os.path.join(os.path.dirname(__file__), 'resources')

    if args['topic'] == 'config':
        file = os.path.join(root, 'config.md')
        with open(file, 'r', encoding='UTF-8') as f:
            text = f.read()
            f.close()
        print(text)


def cmd_view(args):
    """View archive file(s) in the browser."""
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
    import shutil
    from urllib.request import pathname2url

    cache_prefix = config['browser']['cache_prefix']
    cache_expire = config['browser']['cache_expire'] * 10 ** 9
    use_jar = config['browser']['use_jar']
    browser = webbrowser.get(config['browser']['command'] or None)

    temp_dir = tempfile.gettempdir()
    urls = []

    for file in dict.fromkeys(os.path.normcase(os.path.abspath(file)) for file in files):
        mime, _ = mimetypes.guess_type(file)
        if not mime in ("application/html+zip", "application/x-maff"):
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
    parser = argparse.ArgumentParser(description=view_archive_files.__doc__)
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
        help="""The sub-command to run.
Add -h (--help) after a sub-command for help message.
(E.g. %(prog)s config -h)""")

    # subcommand: serve
    parser_serve = subparsers.add_parser('serve', aliases=['s'],
        help=cmd_serve.__doc__, description=cmd_serve.__doc__)
    parser_serve.set_defaults(func=cmd_serve)

    # subcommand: config
    parser_config = subparsers.add_parser('config', aliases=['c'],
        help=cmd_config.__doc__, description=cmd_config.__doc__)
    parser_config.set_defaults(func=cmd_config)
    parser_config.add_argument('name', nargs='?',
        help="""show value of the given config name. (in the form of <section>[.<subsection>].<key>)""")
    parser_config.add_argument('-b', '--book', default=False, action='store_true',
        help="""generate book config file.""")
    parser_config.add_argument('-u', '--user', default=False, action='store_true',
        help="""generate user config file.""")
    parser_config.add_argument('-a', '--all', default=False, action='store_true',
        help="""generate more assistant files. (with --book)""")
    parser_config.add_argument('-e', '--edit', default=False, action='store_true',
        help="""edit the config file. (with --book or --user)""")

    # subcommand: encrypt
    parser_encrypt = subparsers.add_parser('encrypt', aliases=['e'],
        help=cmd_encrypt.__doc__, description=cmd_encrypt.__doc__)
    parser_encrypt.set_defaults(func=cmd_encrypt)
    parser_encrypt.add_argument('-p', '--password', nargs='?', default=None, action='store',
        help="""the password to encrypt.""")
    parser_encrypt.add_argument('-m', '--method', default='sha1', action='store',
        help="""the encrypt method to use, which is one of: plain, md5, sha1,
sha224, sha256, sha384, sha512, sha3_224, sha3_256, sha3_384, and sha3_512.
(default: %(default)s)""")
    parser_encrypt.add_argument('-s', '--salt', default='', action='store',
        help="""the salt to add during encryption.""")

    # subcommand: help
    parser_help = subparsers.add_parser('help',
        help=cmd_help.__doc__, description=cmd_help.__doc__)
    parser_help.set_defaults(func=cmd_help)
    parser_help.add_argument('topic', default=None, action='store',
        choices=['config'],
        help="""detailed help topic.""")

    # subcommand: view
    parser_view = subparsers.add_parser('view',
        help=cmd_view.__doc__, description=cmd_view.__doc__)
    parser_view.set_defaults(func=cmd_view)
    parser_view.add_argument('files', nargs='+',
        help="""files to view.""")

    # parse the command
    args = vars(parser.parse_args())
    try:
        func = args.pop('func')
        func(args)
    except KeyError:
        parser.parse_args(['-h'])


if __name__ == '__main__':
    main()
