#!/usr/bin/env python3
"""Command line interface of WebScrapBook toolkit.
"""
import sys
import os
import argparse
import json
from getpass import getpass

# this package
from . import __package_name__, __version__
from . import *
from . import server
from . import util


class WebScrapBookInitError(Exception):
    pass


def fcopy(fsrc, fdst):
    """Copy a script file to target

    - Use universal linefeed.
    - Set last modified time to current time.
    """
    os.makedirs(os.path.dirname(os.path.abspath(fdst)), exist_ok=True)
    with open(fsrc, 'r', encoding='UTF-8') as f:
        content = f.read()
        f.close()
    with open(fdst, 'w', encoding='UTF-8') as f:
        f.write(content)
        f.close()


def cmd_serve(args):
    """Serve the directory."""
    server.serve(args['root'])


def cmd_config(args):
    """Show or edit config."""
    if args['book']:
        filename = WSB_LOCAL_CONFIG
        fdst = os.path.normpath(os.path.join(args['root'], WSB_DIR, filename))
        fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', filename))
        if not os.path.isfile(fdst):
            try:
                print('Generating "{}"...'.format(fdst))
                fcopy(fsrc, fdst)
            except:
                raise WebScrapBookInitError("Unable to generate {}.".format(fdst))

        try:
            util.launch(fdst)
        except OSError:
            pass

        if args['all']:
            filename = 'serve.py'
            fdst = os.path.normpath(os.path.join(args['root'], WSB_DIR, filename))
            fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', filename))
            if not os.path.isfile(fdst):
                try:
                    print('Generating "{}"...'.format(fdst))
                    fcopy(fsrc, fdst)
                except:
                    raise WebScrapBookInitError("Unable to generate {}.".format(fdst))

            filename = 'serve.wsgi'
            fdst = os.path.normpath(os.path.join(args['root'], WSB_DIR, filename))
            fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', filename))
            if not os.path.isfile(fdst):
                try:
                    print('Generating "{}"...'.format(fdst))
                    fcopy(fsrc, fdst)
                except:
                    raise WebScrapBookInitError("Unable to generate {}.".format(fdst))

    if args['user']:
        fdst = WSB_USER_CONFIG
        fsrc = os.path.normpath(os.path.join(__file__, '..', 'resources', WSB_LOCAL_CONFIG))
        if not os.path.isfile(fdst):
            try:
                print('Generating "{}"...'.format(fdst))
                fcopy(fsrc, fdst)
            except:
                raise WebScrapBookInitError("Unable to generate {}.".format(fdst))

        try:
            util.launch(fdst)
        except OSError:
            pass

    if not any(args[k] for k in ('book', 'user')):
        config.dump(sys.stdout)


def cmd_encrypt(args):
    """Generate encrypted password string."""
    if args['password'] is None:
        pw1 = getpass('Enter a password: ')
        pw2 = getpass('Confirm the password: ')

        if pw1 != pw2:
            print('Error: Entered passwords do not match.', file=sys.stderr)
            sys.exit(1)

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default=False, action='store_true',
        help="""show version information and exit""")
    parser.add_argument('--root', default=".",
        help="""root directory to manipulate (default: current working directory)""")
    subparsers = parser.add_subparsers(dest='command', metavar='COMMAND')

    # subcommand: serve
    parser_serve = subparsers.add_parser('serve', aliases=['s'],
        help=cmd_serve.__doc__, description=cmd_serve.__doc__)
    parser_serve.set_defaults(func=cmd_serve)

    # subcommand: config
    parser_config = subparsers.add_parser('config', aliases=['c'],
        help=cmd_config.__doc__, description=cmd_config.__doc__)
    parser_config.set_defaults(func=cmd_config)
    parser_config.add_argument('-b', '--book', default=False, action='store_true',
        help="""generate and edit book config.""")
    parser_config.add_argument('-u', '--user', default=False, action='store_true',
        help="""generate and edit user config.""")
    parser_config.add_argument('-a', '--all', default=False, action='store_true',
        help="""generate more assistent files.""")

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

    # parse the command
    args = vars(parser.parse_args())
    if args.get('func'):
        args['func'](args)
    elif args.get('version'):
        print('{} {}'.format(__package_name__, __version__))
    else:
        parser.parse_args(['-h'])


if __name__ == '__main__':
    main()
