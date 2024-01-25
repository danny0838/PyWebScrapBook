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
_mimetypes.add_type('application/x-shockwave-flash', '.swf')  # Apache, nginx, etc.
_mimetypes.add_type('application/java-archive', '.jar')
_mimetypes.add_type('application/java-vm', '.class')
_mimetypes.add_type('application/epub+zip', '.epub')
_mimetypes.add_type('application/x-7z-compressed', '.7z')
_mimetypes.add_type('application/vnd.rar', '.rar')

# .js is mapped to application/javascript or application/x-javascript in some OS
# ref: https://www.ietf.org/rfc/rfc9239.txt
# text/javascript is mapped to .es in Debian 12
_mimetypes.add_type('text/javascript', '.js')

# .bmp is mapped to image/x-ms-bmp in Python < 3.11
# ref: https://github.com/python/cpython/issues/86194
_mimetypes.add_type('image/bmp', '.bmp')

# .ico is mapped to image/vnd.microsoft.icon in Python,
# which is not actually used by Microsoft softwares and causes
# a compatibility issue in IE9.
# ref: https://en.wikipedia.org/wiki/ICO_%28file_format%29#MIME_type
_mimetypes.add_type('image/x-icon', '.ico')

# .zip is mapped to application/x-zip-compressed in Windows
_mimetypes.add_type('application/zip', '.zip')
