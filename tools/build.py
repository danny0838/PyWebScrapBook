#!/usr/bin/env python3
"""Compile executable.

NOTE: This package must be installed in non-editable mode.

It's generally more recommended to run through tox with:

    tox -e build [-- <args>]
"""
import argparse
import os
import platform
import shutil
import sys

import PyInstaller.__main__

from webscrapbook import __version__

root = os.path.abspath(os.path.join(__file__, '..', '..'))


def detect_os_arch():
    os_ = {
        'Windows': 'win',
        'Linux': 'linux',
        'Darwin': 'mac',
    }.get(platform.system(), 'unknown')

    arch = 'x64' if (sys.maxsize > 2 ** 32) else 'x86'

    if os_ == 'mac':
        if arch == 'x64' and platform.machine() in ('arm64', 'aarch64'):
            arch = 'arm64'
        else:
            raise RuntimeError(f'Unknown Python architecture under {platform.system()} {platform.machine()}')

    return os_, arch


def build_binary(args):
    build = os.path.join(root, 'build')
    dist = os.path.join(root, 'dist')
    assets = os.path.join(root, 'assets')

    # determine dist dir according to system information
    version = __version__
    pyver = f'{sys.version_info.major}.{sys.version_info.minor}'
    os_, arch = detect_os_arch()
    onefile = '-onefile' if args.onefile else ''

    pack_name = f'webscrapbook-{version}-py{pyver}-{os_}-{arch}{onefile}'
    dist = os.path.join(dist, pack_name)

    # run the compiler
    pyinstaller_args = [
        os.path.join(assets, 'wsb.py'),
        '--name', 'wsb',
        '--workpath', build,
        '--specpath', build,
        '--distpath', dist,
        '--hidden-import', 'webscrapbook.cli',
        '--add-data', ':'.join((os.path.join(root, 'webscrapbook', 'resources'), os.path.join('webscrapbook', 'resources'))),
        '--add-data', ':'.join((os.path.join(root, 'webscrapbook', 'themes'), os.path.join('webscrapbook', 'themes'))),
        '--icon', os.path.join(assets, 'icon32.ico'),
        *(['--onefile'] if args.onefile else []),
        '--noconfirm',
        '--clean',
    ]

    os.chdir(root)
    PyInstaller.__main__.run(pyinstaller_args)

    # pack as ZIP
    if args.pack:
        pack_root = dist if args.onefile else os.path.join(dist, 'wsb')
        shutil.make_archive(dist, 'zip', pack_root)
        shutil.rmtree(dist)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Build executable with PyInstaller')
    parser.add_argument('--onefile', action='store_true', help='Bundle the app into a single executable')
    parser.add_argument('--pack', action='store_true', help='Pack into a zip file')
    return parser.parse_args(argv)


def main():
    args = parse_args()
    build_binary(args)


if __name__ == '__main__':
    main()
