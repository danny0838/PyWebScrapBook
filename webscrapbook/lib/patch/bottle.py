#!/usr/bin/env python3
"""Patch bugs in Bottle

Usage: import this module before importing bottle
"""
import bottle
from distutils.version import LooseVersion

def patch_bottle_0_12():
    """patch bugs in Bottle 0.12.*

    https://github.com/bottlepy/bottle/issues/1129
    https://github.com/bottlepy/bottle/issues/1132
    """
    if LooseVersion(bottle.__version__) >= LooseVersion("0.13"):
        return

    import os
    import mimetypes
    import time
    import email.utils
    import hashlib
    from bottle import request, redirect, template
    from bottle import HTTPResponse, HTTPError
    from bottle import parse_range_header, parse_date, _file_iter_range, tob

    # implement static_file() in 0.13
    # removed "close" param of _file_iter_range as it's not implemented in 0.12 yet.
    def static_file(filename, root,
                    mimetype=True,
                    download=False,
                    charset='UTF-8',
                    etag=None):
        """ Open a file in a safe way and return an instance of :exc:`HTTPResponse`
            that can be sent back to the client.
            :param filename: Name or path of the file to send, relative to ``root``.
            :param root: Root path for file lookups. Should be an absolute directory
                path.
            :param mimetype: Provide the content-type header (default: guess from
                file extension)
            :param download: If True, ask the browser to open a `Save as...` dialog
                instead of opening the file with the associated program. You can
                specify a custom filename as a string. If not specified, the
                original filename is used (default: False).
            :param charset: The charset for files with a ``text/*`` mime-type.
                (default: UTF-8)
            :param etag: Provide a pre-computed ETag header. If set to ``False``,
                ETag handling is disabled. (default: auto-generate ETag header)
            While checking user input is always a good idea, this function provides
            additional protection against malicious ``filename`` parameters from
            breaking out of the ``root`` directory and leaking sensitive information
            to an attacker.
            Read-protected files or files outside of the ``root`` directory are
            answered with ``403 Access Denied``. Missing files result in a
            ``404 Not Found`` response. Conditional requests (``If-Modified-Since``,
            ``If-None-Match``) are answered with ``304 Not Modified`` whenever
            possible. ``HEAD`` and ``Range`` requests (used by download managers to
            check or continue partial downloads) are also handled automatically.
        """

        root = os.path.join(os.path.abspath(root), '')
        filename = os.path.abspath(os.path.join(root, filename.strip('/\\')))
        headers = dict()

        if not filename.startswith(root):
            return HTTPError(403, "Access denied.")
        if not os.path.exists(filename) or not os.path.isfile(filename):
            return HTTPError(404, "File does not exist.")
        if not os.access(filename, os.R_OK):
            return HTTPError(403, "You do not have permission to access this file.")

        if mimetype is True:
            if download and download is not True:
                mimetype, encoding = mimetypes.guess_type(download)
            else:
                mimetype, encoding = mimetypes.guess_type(filename)
            if encoding: headers['Content-Encoding'] = encoding

        if mimetype:
            if (mimetype[:5] == 'text/' or mimetype == 'application/javascript')\
            and charset and 'charset' not in mimetype:
                mimetype += '; charset=%s' % charset
            headers['Content-Type'] = mimetype

        if download:
            download = os.path.basename(filename if download is True else download)
            headers['Content-Disposition'] = 'attachment; filename="%s"' % download

        stats = os.stat(filename)
        headers['Content-Length'] = clen = stats.st_size
        headers['Last-Modified'] = email.utils.formatdate(stats.st_mtime,
                                                          usegmt=True)
        headers['Date'] = email.utils.formatdate(time.time(), usegmt=True)

        getenv = request.environ.get

        if etag is None:
            etag = '%d:%d:%d:%d:%s' % (stats.st_dev, stats.st_ino, stats.st_mtime,
                                       clen, filename)
            etag = hashlib.sha1(tob(etag)).hexdigest()

        if etag:
            headers['ETag'] = etag
            check = getenv('HTTP_IF_NONE_MATCH')
            if check and check == etag:
                return HTTPResponse(status=304, **headers)

        if not (etag and check):
            ims = getenv('HTTP_IF_MODIFIED_SINCE')
            if ims:
                ims = parse_date(ims.split(";")[0].strip())
            if ims is not None and ims >= int(stats.st_mtime):
                return HTTPResponse(status=304, **headers)

        body = '' if request.method == 'HEAD' else open(filename, 'rb')

        headers["Accept-Ranges"] = "bytes"
        range_header = getenv('HTTP_RANGE')
        if range_header:
            ranges = list(parse_range_header(range_header, clen))
            if not ranges:
                return HTTPError(416, "Requested Range Not Satisfiable")
            offset, end = ranges[0]
            headers["Content-Range"] = "bytes %d-%d/%d" % (offset, end - 1, clen)
            headers["Content-Length"] = str(end - offset)
            if body: body = _file_iter_range(body, offset, end - offset)
            return HTTPResponse(body, status=206, **headers)
        return HTTPResponse(body, **headers)

    bottle.static_file = static_file

patch_bottle_0_12()
