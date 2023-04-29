import mimetypes as _mimetypes
import os
from mimetypes import *

from .. import WSB_USER_DIR

__all__ = _mimetypes.__all__


# add custom user MIME types mapping
_mimetypes.knownfiles += [os.path.join(WSB_USER_DIR, 'mime.types')]

# WebScrapBook related
_mimetypes.add_type('application/html+zip', '.htz')
_mimetypes.add_type('application/x-maff', '.maff')
_mimetypes.add_type('application/wsba+zip', '.wsba')

# Some common types
_mimetypes.add_type('text/markdown', '.md')
_mimetypes.add_type('text/markdown', '.mkd')
_mimetypes.add_type('text/markdown', '.mkdn')
_mimetypes.add_type('text/markdown', '.mdwn')
_mimetypes.add_type('text/markdown', '.mdown')
_mimetypes.add_type('text/markdown', '.markdown')
_mimetypes.add_type('application/rss+xml', '.rss')
_mimetypes.add_type('application/atom+xml', '.atom')
_mimetypes.add_type('font/woff', '.woff')
_mimetypes.add_type('font/woff2', '.woff2')
_mimetypes.add_type('image/webp', '.webp')
_mimetypes.add_type('audio/weba', '.weba')
_mimetypes.add_type('video/webm', '.webm')
_mimetypes.add_type('audio/ogg', '.oga')
_mimetypes.add_type('video/ogg', '.ogv')
_mimetypes.add_type('application/ogg', '.ogx')  # IANA
_mimetypes.add_type('application/ogg', '.ogg')  # MAFF
_mimetypes.add_type('text/vtt', '.vtt')
_mimetypes.add_type('application/java-archive', '.jar')
_mimetypes.add_type('application/java-vm', '.class')
_mimetypes.add_type('application/epub+zip', '.epub')
_mimetypes.add_type('application/x-7z-compressed', '.7z')
_mimetypes.add_type('application/vnd.rar', '.rar')

# .js is mapped to application/x-javascript in some mime types sources
# ref: https://www.ietf.org/rfc/rfc9239.txt
_mimetypes.add_type('text/javascript', '.js')

# .bmp is mapped to image/x-ms-bmp on POSIX
# ref: https://bugs.python.org/issue42028
_mimetypes.add_type('image/bmp', '.bmp')

# .ico is mapped to image/vnd.microsoft.icon on POSIX
_mimetypes.add_type('image/x-icon', '.ico')

# .zip is mapped to application/x-zip-compressed on Windows
_mimetypes.add_type('application/zip', '.zip')
