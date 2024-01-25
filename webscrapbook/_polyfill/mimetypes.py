import mimetypes as _mimetypes
import os

from .. import Config

WSB_USER_MIMETYPES = 'mime.types'


def _patch_mimetypes():
    patch_types_map = {
        # WebScrapBook related
        '.htz': 'application/html+zip',
        '.maff': 'application/x-maff',
        '.wsba': 'application/wsba+zip',

        # Some common types
        '.md': 'text/markdown',
        '.mkd': 'text/markdown',
        '.mkdn': 'text/markdown',
        '.mdwn': 'text/markdown',
        '.mdown': 'text/markdown',
        '.markdown': 'text/markdown',
        '.rss': 'application/rss+xml',
        '.atom': 'application/atom+xml',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.webp': 'image/webp',
        '.weba': 'audio/weba',
        '.webm': 'video/webm',
        '.oga': 'audio/ogg',
        '.ogv': 'video/ogg',
        '.ogx': 'application/ogg',  # IANA
        '.ogg': 'application/ogg',  # MAFF
        '.vtt': 'text/vtt',
        '.swf': 'application/x-shockwave-flash',  # Apache, nginx, etc.
        '.jar': 'application/java-archive',
        '.class': 'application/java-vm',
        '.epub': 'application/epub+zip',
        '.7z': 'application/x-7z-compressed',
        '.rar': 'application/vnd.rar',

        # .js is mapped to application/javascript or application/x-javascript in some OS
        # ref: https://www.ietf.org/rfc/rfc9239.txt
        # text/javascript is mapped to .es in Debian 12
        '.js': 'text/javascript',

        # .bmp is mapped to image/x-ms-bmp in Python < 3.11
        # ref: https://github.com/python/cpython/issues/86194
        '.bmp': 'image/bmp',

        # .ico is mapped to image/vnd.microsoft.icon in Python,
        # which is not actually used by Microsoft softwares and causes
        # a compatibility issue in IE9.
        # ref: https://en.wikipedia.org/wiki/ICO_%28file_format%29#MIME_type
        '.ico': 'image/x-icon',

        # .zip is mapped to application/x-zip-compressed in Windows
        '.zip': 'application/zip',
    }

    def patch_db(db):
        # apply the patch
        patch_types_map_inv = {}
        for ext, type in patch_types_map.items():
            db.types_map[True][ext] = type
            patch_types_map_inv.setdefault(type, []).append(ext)
        for type, exts in patch_types_map_inv.items():
            entry = db.types_map_inv[True].setdefault(type, [])
            for ext in exts:
                try:
                    entry.remove(ext)
                except ValueError:
                    pass
            entry[0:0] = exts

        # load user mappings
        for file in (os.path.join(Config.user_config_dir(), WSB_USER_MIMETYPES),):
            if os.path.isfile(file):
                db.read(file)

    if _mimetypes.inited:
        patch_db(_mimetypes._db)
    else:
        # patch init
        patched = False
        _init = _mimetypes.init

        def init(files=None):
            nonlocal patched
            _init(files)
            if not patched:
                patch_db(_mimetypes._db)
                patched = True

        _mimetypes.init = init


_patch_mimetypes()

# export all attributes
from mimetypes import *  # noqa: E402

__all__ = _mimetypes.__all__
