#!/usr/bin/env python3
"""The WGSI application.

   Ways to host this app:
   1. run server.serve()
   2. set application = get_app() in a .wsgi
"""
import sys
import os
import traceback
import shutil
import mimetypes
import re
import zipfile
import time
import email.utils
import hashlib
import json
from base64 import b64decode
from urllib.parse import urlsplit, urlunsplit, urljoin, quote, unquote, parse_qs

# dependency
from .lib.patch import bottle
import bottle
from bottle import request, redirect, template
from bottle import HTTPResponse, HTTPError
import commonmark

# this package
from . import *
from . import util

try:
    from time import time_ns
except ImportError:
    from .lib.shim.time import time_ns

# runtime variables
# initializated in get_app() just before app is started
runtime = {}

# main app instance
app = bottle.Bottle()


def static_file(*args, **kwargs):
    """Wrap bottle.static_file for customized behaviors.

    - Use header 'Cache-Control: no-cache'.
    """
    result = bottle.static_file(*args, **kwargs)
    result.set_header('Cache-Control', 'no-cache')
    return result


def http_response(body='', status=None, headers=None, format=None, **more_headers):
    """Handles formatted response.

    ref: https://jsonapi.org
    """
    if format == 'json':
        more_headers['Content-type'] = 'application/json'

        body = {
            'success': True,
            'data': body,
            }

        body = json.dumps(body, ensure_ascii=False)

    return HTTPResponse(body, status, headers, **more_headers)


def http_error(
         status=500,
         body=None,
         exception=None,
         traceback=None,
         format=None, **more_headers):
    """Handles formatted error response.
    """
    if format == 'json':
        more_headers['Content-type'] = 'application/json'

        body = {
            'error': {
                'status': status,
                'message': body,
                },
            }
        body = json.dumps(body, ensure_ascii=False)
        return HTTPResponse(body, status, **more_headers)

    else:
        return HTTPError(status, body, exception, traceback, **more_headers)


def get_base():
    return (config['app']['base'] or request.environ.get('SCRIPT_NAME', '')).rstrip('/')


def get_pathname():
    """Revise request.pathname of Bottle

    When visiting http://example.com/app, request.pathname returns '/app/',
    while we want '/app'.

    http://example.com effectively means http://example.com/, so keep at least
    '/' as final fallback.
    """
    return (request.environ.get('SCRIPT_NAME', '') + request.environ.get('PATH_INFO', '')) or '/'


def get_archive_path(filepath, localpath):
    """Parse archive file path and the sub-archive path.

    - Priority:
      /path/to/fileordir.htz!
      /path/to/fileordir.htz
      /path/to/fileordir.htz!/path/to/fileordir.htz!
      /path/to/fileordir.htz!/path/to/fileordir.htz
      ...

    - Returns a tuple (archivefile, subarchivepath).
    """
    if not os.path.lexists(localpath):
        for m in re.finditer(r'![/\\]', filepath, flags=re.I):
            archivefile = os.path.join(runtime['root'], filepath[:m.start(0)].strip('/\\'))
            if os.path.isdir(archivefile + '!'):
                return (None, None)

            if zipfile.is_zipfile(archivefile):
                subarchivepath = filepath[m.end(0):].rstrip('/')
                return (archivefile, subarchivepath)

    return (None, None)


def is_local_access():
    """Determine if the client is in same device.
    """
    return request.urlparts.hostname in ('localhost', '127.0.0.1', request.remote_addr)


def handle_authorization(format=None):
    """Check if authorized or not.

    Return None if authorization passed, otherwise the header and body for authorization.

    Also modify runtime['permission'] for further access control.
    """
    if not len(config.subsections.get('auth', {})):
        return

    auth_pass = False
    user, pw = request.auth or ('', '')

    # The higher level (e.g. Apache if this is run via Apache WSGI) may remove
    # the password and gets None. Revise to '' to prevent further error.
    if pw is None: pw = ''

    if user:
        for _, entry in config.subsections['auth'].items():
            entry_user = entry.get('user', '')
            entry_pw = entry.get('pw', '')
            entry_pw_salt = entry.get('pw_salt', '')
            entry_pw_type = entry.get('pw_type', '')
            entry_permission = entry.get('permission', 'all')
            if (user == entry_user and
                    util.encrypt(pw, entry_pw_salt, entry_pw_type) == entry_pw):
                auth_pass = True
                runtime['permission'] = entry.get('permission', '')
                break

    if not auth_pass:
        headers = {
            'WWW-Authenticate': 'Basic realm="Authentication required.", charset="UTF-8"',
            'Content-type': 'text/html',
            }
        return http_error(401, "You are not authorized.", format=format, **headers)


def handle_directory_listing(localpath, format=None):
    """List contents in a directory.
    """
    # ensure directory has trailing '/'
    pathname = get_pathname()
    if not pathname.endswith('/'):
        parts = request.urlparts
        new_parts = (parts[0], parts[1], quote(pathname) + '/', parts[3], parts[4])
        new_url = urlunsplit(new_parts)
        return redirect(new_url)

    if not os.path.exists(localpath):
        return http_error(404, "Directory does not exist.", format=format)

    if not os.access(localpath, os.R_OK):
        return http_error(403, "You do not have permission to view this directory.", format=format)

    # headers
    headers = {}
    headers['Cache-Control'] = 'no-store'
    stats = os.stat(localpath)
    headers['Last-Modified'] = email.utils.formatdate(stats.st_mtime, usegmt=True)
    headers['Date'] = email.utils.formatdate(time.time(), usegmt=True)

    # output index
    subentries = util.listdir(localpath)

    if format:
        data = []
        for entry in subentries:
            data.append({
                    'name': entry.name,
                    'type': entry.type,
                    'size': entry.size,
                    'last_modified': entry.last_modified,
                    })
        return http_response(data, format=format, **headers)

    body = template('index.tpl',
            sitename=runtime['name'],
            is_local=is_local_access(),
            base=get_base(),
            path=request.path,
            subarchivepath=None,
            subentries=subentries,
            )

    return HTTPResponse(body, **headers)


def handle_zip_directory_listing(zip, archivefile, subarchivepath, format=None):
    """List contents in a directory.
    """
    # ensure directory has trailing '/'
    pathname = get_pathname()
    if not pathname.endswith('/'):
        parts = request.urlparts
        new_parts = (parts[0], parts[1], quote(pathname) + '/', parts[3], parts[4])
        new_url = urlunsplit(new_parts)
        return redirect(new_url)

    from bottle import parse_date, tob

    headers = {}
    headers['Cache-Control'] = 'no-cache'

    # check 304
    stats = os.stat(archivefile)
    headers['Last-Modified'] = email.utils.formatdate(stats.st_mtime, usegmt=True)

    getenv = request.environ.get

    etag = '%d:%d:%d:%d:%s' % (stats.st_dev, stats.st_ino, stats.st_mtime,
                               stats.st_size, archivefile)
    etag = hashlib.sha1(tob(etag)).hexdigest()

    headers['ETag'] = etag
    check = getenv('HTTP_IF_NONE_MATCH')
    if check and check == etag:
        return HTTPResponse(status=304, **headers)

    if not check:
        ims = getenv('HTTP_IF_MODIFIED_SINCE')
        if ims:
            ims = parse_date(ims.split(";")[0].strip())
        if ims is not None and ims >= int(stats.st_mtime):
            return HTTPResponse(status=304, **headers)

    subentries = util.zip_listdir(zip, subarchivepath)

    try:
        body = template('index.tpl',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=get_base(),
                path=request.path,
                subarchivepath=subarchivepath,
                subentries=subentries,
                )
        return HTTPResponse(body, **headers)
    except util.ZipDirNotFoundError:
        return http_error(404, "File does not exist.", format=format)


def handle_subarchive_path(
        archivefile,
        subarchivepath,
        mimetype,
        encoding,
        download=False,
        charset='UTF-8',
        etag=None,
        format=None):
    """Show content of a path in a zip file.
    """
    from bottle import parse_range_header, parse_date, _file_iter_range, tob

    if not os.access(archivefile, os.R_OK):
        return http_error(403, "You do not have permission to access this file.", format=format)

    try:
        zip = zipfile.ZipFile(archivefile)
    except:
        return http_error(500, "Unable to open the ZIP file.", format=format)

    try:
        # KeyError is raised if subarchivepath does not exist
        info = zip.getinfo(subarchivepath)
    except KeyError:
        # subarchivepath does not exist
        # possibility a missing directory entry?
        return handle_zip_directory_listing(zip, archivefile, subarchivepath)

    fh = zip.open(subarchivepath, 'r')

    headers = dict()
    headers['Cache-Control'] = 'no-cache'

    if encoding: headers['Content-Encoding'] = encoding

    if mimetype is True:
        if download and download is not True:
            mimetype, encoding = mimetypes.guess_type(download)
        else:
            mimetype, encoding = mimetypes.guess_type(subarchivepath)
        if encoding: headers['Content-Encoding'] = encoding

    if mimetype:
        if (mimetype[:5] == 'text/' or mimetype == 'application/javascript')\
        and charset and 'charset' not in mimetype:
            mimetype += '; charset=%s' % charset
        headers['Content-Type'] = mimetype

    if download:
        download = os.path.basename(subarchivepath if download is True else download)
        headers['Content-Disposition'] = 'attachment; filename="%s"' % download

    headers['Content-Length'] = clen = info.file_size

    lm = info.date_time
    epoch = int(time.mktime((lm[0], lm[1], lm[2], lm[3], lm[4], lm[5], 0, 0, -1)))
    headers['Last-Modified'] = email.utils.formatdate(epoch, usegmt=True)

    headers['Date'] = email.utils.formatdate(time.time(), usegmt=True)

    getenv = request.environ.get

    if etag is None:
        etag = '%d:%d:%s' % (epoch, clen, subarchivepath)
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
        if ims is not None and ims >= int(epoch):
            return HTTPResponse(status=304, **headers)

    body = '' if request.method == 'HEAD' else fh

    headers["Accept-Ranges"] = "bytes"
    range_header = getenv('HTTP_RANGE')
    if range_header:
        ranges = list(parse_range_header(range_header, clen))
        if not ranges:
            return http_error(416, "Requested Range Not Satisfiable")
        offset, end = ranges[0]
        headers["Content-Range"] = "bytes %d-%d/%d" % (offset, end - 1, clen)
        headers["Content-Length"] = str(end - offset)
        if body: body = _file_iter_range(body, offset, end - offset)
        return HTTPResponse(body, status=206, **headers)
    return HTTPResponse(body, **headers)


def handle_archive_viewing(localpath, mimetype):
    """Handle direct visit of HTZ/MAFF file.
    """
    def list_maff_pages(pages):
        """List available web pages in a MAFF file.
        """
        return template('maff_index.tpl',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=get_base(),
                path=request.path,
                pages=pages,
                )

    if not os.access(localpath, os.R_OK):
        return http_error(403, "You do not have permission to access this file.")

    if mimetype == "application/html+zip":
        subpath = "index.html"
    else:
        pages = util.get_maff_pages(localpath)

        if len(pages) > 1:
            # multiple index files
            return list_maff_pages(pages)
        elif len(pages) > 0:
            subpath = pages[0].indexfilename
        else:
            # no valid index file found
            return list_maff_pages([])

    parts = request.urlparts
    new_parts = (parts[0], parts[1], parts[2] + '!/' + quote(subpath), parts[3], parts[4])
    new_url = urlunsplit(new_parts)
    return redirect(new_url)


def handle_markdown_output(filepath, filename):
    """Output processed markdown.
    """
    from bottle import parse_date, tob

    headers = {}

    # check 304
    stats = os.stat(filename)
    headers['Last-Modified'] = email.utils.formatdate(stats.st_mtime, usegmt=True)

    getenv = request.environ.get

    etag = '%d:%d:%d:%d:%s' % (stats.st_dev, stats.st_ino, stats.st_mtime,
                               stats.st_size, filename)
    etag = hashlib.sha1(tob(etag)).hexdigest()

    headers['ETag'] = etag
    check = getenv('HTTP_IF_NONE_MATCH')
    if check and check == etag:
        return HTTPResponse(status=304, **headers)

    if not check:
        ims = getenv('HTTP_IF_MODIFIED_SINCE')
        if ims:
            ims = parse_date(ims.split(";")[0].strip())
        if ims is not None and ims >= int(stats.st_mtime):
            return HTTPResponse(status=304, **headers)

    # output processed content
    with open(filename, 'r', encoding='UTF-8') as f:
        body = f.read()
        f.close()
    
    body = template('markdown',
            sitename=runtime['name'],
            is_local=is_local_access(),
            base=get_base(),
            path=request.path,
            content=commonmark.commonmark(body),
            )

    return HTTPResponse(body, **headers)


@app.route('<filepath:path>', method=['GET', 'HEAD', 'POST'])
def handle_request(filepath):
    """Handle an HTTP request (HEAD, GET, POST).
    """
    action = request.params.getunicode('a', encoding='UTF-8', default='view')
    action = request.params.getunicode('action', encoding='UTF-8', default=action)

    format = request.params.getunicode('f', encoding='UTF-8')
    format = request.params.getunicode('format', encoding='UTF-8', default=format)

    # handle authentication
    runtime['permission'] = 'all'
    auth_result = handle_authorization(format=format)
    if auth_result is not None:
        return auth_result

    # determine primary variables
    #
    # filepath: the URL path below app base (not percent encoded)
    # localpath: the file system path corresponding to filepath
    # localtargetpath: localpath with symbolic link resolved
    # mimetype: the mimetype from localtargetpath
    # archivefile: the file system path of the ZIP archive file, or None
    # subarchivepath: the URL path below archivefile (not percent encoded)
    localpath = os.path.abspath(os.path.join(runtime['root'], filepath.strip('/\\')))
    localtargetpath = os.path.realpath(localpath)
    archivefile, subarchivepath = get_archive_path(filepath, localpath)
    mimetype, encoding = mimetypes.guess_type(localtargetpath)

    # handle action
    if action == 'static':
        for i in runtime['statics']:
            r = static_file(filepath, root=i, charset=None)
            if type(r) is bottle.HTTPResponse:
                return r
        else:
            return r

    elif action == 'source':
        # show text-like files as plain text
        if mimetype and (
                mimetype.startswith('text/') or
                mimetype.endswith('+xml') or
                mimetype.endswith('+json') or
                mimetype in ('application/javascript',)
                ):
            mimetype = 'text/plain'

        if archivefile:
            return handle_subarchive_path(os.path.realpath(archivefile), subarchivepath,
                    mimetype, encoding, format=format)

        return static_file(filepath, root=runtime['root'], mimetype=mimetype, charset=None)

    elif action in ('exec', 'browse'):
        if is_local_access():
            if os.path.lexists(localpath):
                if action == 'browse':
                    util.view_in_explorer(localpath)

                elif action == 'exec':
                    util.launch(localpath)

                if format:
                    return http_response('Command run successfully.', format=format)
                else:
                    return http_response(status=204, format=format)
       
            return http_error(404, "File does not exist.", format=format)

        else:
            return http_error(400, "Command can only run on local device.", format=format)

    elif action == 'token':
        if runtime['permission'] != 'all':
            return http_error(401, "You are not permitted to do this.", format=format)

        return http_response(token_handler.acquire(), format=format)

    elif action == 'list':
        if not format:
            return http_error(400, "Action not supported.", format=format)

        if os.path.isdir(localpath):
            return handle_directory_listing(localtargetpath, format=format)

        return http_error(400, "This is not a directory.", format=format)

    elif action == 'config':
        if not format:
            return http_error(400, "Action not supported.", format=format)

        # slightly adjusted some value for client to better know the server
        data = config.dump_object()
        data['app']['is_local'] = is_local_access()
        data['app']['root'] = runtime['root']
        data['app']['base'] = get_base()
        data['WSB_DIR'] = WSB_DIR;
        data['WSB_LOCAL_CONFIG'] = WSB_LOCAL_CONFIG;
        return http_response(data, format=format)

    elif action == 'edit':
        if format:
            return http_error(400, "Action not supported.", format=format)

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            return http_error(400, "Found a non-file here.", format=format)

        if archivefile:
            with zipfile.ZipFile(archivefile, 'r') as zip:
                try:
                    info = zip.getinfo(subarchivepath)
                except:
                    body = b''
                else:
                    body = zip.read(info)
        else:
            try:
                with open(localpath, 'rb') as f:
                    body = f.read()
                    f.close()
            except FileNotFoundError:
                body = b''

        try:
            body = body.decode('UTF-8')
            is_utf8 = True
        except UnicodeDecodeError:
            body = body.decode('ISO-8859-1')
            is_utf8 = False

        body = template('edit.tpl',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=get_base(),
                path=request.path,
                body=body,
                is_utf8=is_utf8,
                )

        return http_response(body, format=format)

    elif action == 'editx':
        if format:
            return http_error(400, "Action not supported.", format=format)

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            return http_error(400, "Found a non-file here.", format=format)

        if not mimetype in ("text/html", "application/xhtml+xml"):
            return http_error(400, "This is not an HTML file.", format=format)

        if archivefile:
            with zipfile.ZipFile(archivefile, 'r') as zip:
                try:
                    info = zip.getinfo(subarchivepath)
                except:
                    return http_error(404, "File does not exist.", format=format)
        else:
            if not os.path.lexists(localpath):
                return http_error(404, "File does not exist.", format=format)

        body = template('editx.tpl',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=get_base(),
                path=request.path,
                )

        return http_response(body, format=format)

    elif action in ('lock', 'unlock', 'mkdir', 'save', 'delete', 'move', 'copy'):
        if request.method != 'POST':
            headers = {
                'Allow': 'POST',
                }
            return http_error(405, 'Method "{}" not allowed.'.format(request.method), format=format, **headers)

        # validate and revoke token
        token = request.params.get('token') or ''

        if not token_handler.validate(token):
            return http_error(401, 'Invalid access token.', format=format)

        token_handler.delete(token)

        # validate localpath
        if action not in ('lock', 'unlock'):
            if os.path.abspath(localpath) == runtime['root']:
                return http_error(403, "Unable to operate the root directory.", format=format)

        # validate targetpath
        if action in ('lock', 'unlock'):
            name = request.params.get('name')
            if name is None:
                return http_error(400, "Lock name is not specified.", format=format)

            targetpath = os.path.normpath(os.path.join(runtime['root'], WSB_DIR, 'server', 'locks', name))
            if not targetpath.startswith(os.path.join(runtime['root'], WSB_DIR, 'server', 'locks', '')):
                return http_error(400, 'Invalid lock name "{}".'.format(name), format=format)

        # handle action

        # action lock
        # name: name of the lock file.
        # chkt: recheck until the lock file not exist or fail out when time out.
        # chks: how long to treat the lock file as stale.
        if action == 'lock':
            check_stale = request.params.get('chks', 300, type=int)
            check_timeout = request.params.get('chkt', 5, type=int)
            check_expire = time.time() + check_timeout
            check_delta = min(check_timeout, 0.1)

            while True:
                if os.path.lexists(targetpath):
                    t = time.time()
                    if t >= os.stat(targetpath).st_mtime + check_stale:
                        os.rmdir(targetpath)
                    elif t >= check_expire:
                        return http_error(500, 'Unable to acquire lock "{}".'.format(name), format=format)
                    else:
                        time.sleep(check_delta)
                        continue

                try:
                    os.makedirs(targetpath)
                except:
                    traceback.print_exc()
                    return http_error(500, 'Unable to create lock "{}".'.format(name), format=format)
                else:
                    break

        elif action == 'unlock':
            try:
                os.rmdir(targetpath)
            except:
                pass

        elif action == 'mkdir':
            if os.path.lexists(localpath) and not os.path.isdir(localpath):
                return http_error(400, "Found a non-directory here.", format=format)

            if archivefile:
                try:
                    zip = zipfile.ZipFile(archivefile, 'a')
                    subarchivepath = subarchivepath + '/'

                    try:
                        info = zip.getinfo(subarchivepath)
                    except KeyError:
                        # subarchivepath does not exist
                        info = zipfile.ZipInfo(subarchivepath, time.localtime())
                        zip.writestr(info, b'', compress_type=zipfile.ZIP_STORED)
                except:
                    traceback.print_exc()
                    return http_error(500, "Unable to write to this ZIP file.", format=format)

            else:
                try:
                    os.makedirs(localpath, exist_ok=True)
                except OSError:
                    traceback.print_exc()
                    return http_error(500, "Unable to create a directory here.", format=format)

            if format:
                return http_response('Command run successfully.', format=format)

            return redirect(request.url)

        elif action == 'save':
            if os.path.lexists(localpath) and not os.path.isfile(localpath):
                return http_error(400, "Found a non-file here.", format=format)

            if archivefile:
                try:
                    zip0 = zip = zipfile.ZipFile(archivefile, 'a')

                    try:
                        info = zip.getinfo(subarchivepath)
                    except KeyError:
                        # subarchivepath does not exist
                        info = zipfile.ZipInfo(subarchivepath, time.localtime())
                    else:
                        info.date_time = time.localtime()
                        temp_path = archivefile + '.' + str(time_ns())
                        zip = zipfile.ZipFile(temp_path, 'w')

                    file = request.files.get('upload')
                    if file is not None:
                        fp = zip.open(info, 'w', force_zip64=True)
                        file.save(fp)
                        fp.close()
                    else:
                        bytes = request.forms.get('text', '').encode('ISO-8859-1')
                        zip.writestr(info, bytes, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

                    if zip is not zip0:
                        for info in zip0.infolist():
                            if info.filename == subarchivepath: continue
                            zip.writestr(info, zip0.read(info),
                                    compress_type=info.compress_type,
                                    compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9)

                        zip0.close()
                        zip.close()

                        temp_path = archivefile + '.' + str(time_ns())
                        os.rename(archivefile, temp_path)
                        os.rename(zip.filename, archivefile)
                        os.remove(temp_path)
                    else:
                        zip.close()
                except:
                    traceback.print_exc()
                    return http_error(500, "Unable to write to this ZIP file.", format=format)

            else:
                try:
                    os.makedirs(os.path.dirname(localpath), exist_ok=True)
                except:
                    traceback.print_exc()
                    return http_error(500, "Unable to write to this path.", format=format)

                try:
                    file = request.files.get('upload')
                    if file is not None:
                        if os.path.lexists(localpath):
                            os.remove(localpath)
                        file.save(localpath)
                    else:
                        bytes = request.forms.get('text', '').encode('ISO-8859-1')
                        with open(localpath, 'wb') as f:
                            f.write(bytes)
                            f.close()
                except:
                    traceback.print_exc()
                    return http_error(500, "Unable to write to this file.", format=format)

            if format:
                return http_response('Command run successfully.', format=format)

            return redirect(request.url)

        elif action == 'delete':
            if archivefile:
                try:
                    zip0 = zipfile.ZipFile(archivefile, 'r')
                    temp_path = archivefile + '.' + str(time_ns())
                    zip = zipfile.ZipFile(temp_path, 'w')

                    deleted = False
                    for info in zip0.infolist():
                        if (info.filename == subarchivepath or
                                info.filename.startswith(subarchivepath + '/')):
                            deleted = True
                            continue

                        zip.writestr(info, zip0.read(info),
                                compress_type=info.compress_type,
                                compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9)

                    zip0.close()
                    zip.close()

                    if not deleted:
                        os.remove(zip.filename)
                        return http_error(404, "Entry does not exist in this ZIP file.", format=format)

                    temp_path = archivefile + '.' + str(time_ns())
                    os.rename(archivefile, temp_path)
                    os.rename(zip.filename, archivefile)
                    os.remove(temp_path)
                except:
                    traceback.print_exc()
                    return http_error(500, "Unable to write to this ZIP file.", format=format)

            else:
                if not os.path.lexists(localpath):
                    return http_error(404, "File does not exist.", format=format)

                if os.path.islink(localpath):
                    try:
                        os.remove(localpath)
                    except:
                        traceback.print_exc()
                        return http_error(500, "Unable to delete this link.", format=format)
                elif os.path.isfile(localpath):
                    try:
                        os.remove(localpath)
                    except:
                        traceback.print_exc()
                        return http_error(500, "Unable to delete this file.", format=format)
                elif os.path.isdir(localpath):
                    try:
                        shutil.rmtree(localpath)
                    except:
                        traceback.print_exc()
                        return http_error(500, "Unable to delete this directory.", format=format)

            if format:
                return http_response('Command run successfully.', format=format)

            parts = request.urlparts
            new_parts = (parts[0], parts[1], re.sub(r'[^/]+/?$', r'', parts[2]), '', '')
            new_url = urlunsplit(new_parts)
            return redirect(new_url)

        elif action == 'move':
            if not os.path.lexists(localpath):
                return http_error(404, "File does not exist.", format=format)

            target = request.forms.get('target')

            if target is None:
                return http_error(400, 'Target is not specified.', format=format)

            targetpath = os.path.normpath(os.path.join(runtime['root'], target.strip('/')))

            if not targetpath.startswith(os.path.join(runtime['root'], '')):
                return http_error(403, "Unable to operate beyond the root directory.", format=format)

            if os.path.lexists(targetpath):
                return http_error(400, 'Found something at target "{}".'.format(target), format=format)

            ta, tsa = get_archive_path(target, targetpath)
            if ta:
                return http_error(400, "Move target is inside an archive file.", format=format)

            os.makedirs(os.path.dirname(targetpath), exist_ok=True)

            try:
                os.rename(localpath, targetpath)
            except:
                traceback.print_exc()
                return http_error(500, 'Unable to move to target "{}".'.format(target), format=format)

            if format:
                return http_response('Command run successfully.', format=format)

            parts = request.urlparts
            new_parts = (parts[0], parts[1], re.sub(r'[^/]+/?$', r'', parts[2]), '', '')
            new_url = urlunsplit(new_parts)
            return redirect(new_url)

        elif action == 'copy':
            if not os.path.lexists(localpath):
                return http_error(404, "File does not exist.", format=format)

            target = request.forms.get('target')

            if target is None:
                return http_error(400, 'Target is not specified.', format=format)

            targetpath = os.path.normpath(os.path.join(runtime['root'], target.strip('/')))

            if not targetpath.startswith(os.path.join(runtime['root'], '')):
                return http_error(403, "Unable to operate beyond the root directory.", format=format)

            if os.path.lexists(targetpath):
                return http_error(400, 'Found something at target "{}".'.format(target), format=format)

            ta, tsa = get_archive_path(target, targetpath)
            if ta:
                return http_error(400, "Copy target is inside an archive file.", format=format)

            os.makedirs(os.path.dirname(targetpath), exist_ok=True)

            try:
                shutil.copytree(localpath, targetpath)
            except:
                try:
                    shutil.copy2(localpath, targetpath)
                except:
                    traceback.print_exc()
                    return http_error(500, 'Unable to copy to target "{}".'.format(target), format=format)

            if format:
                return http_response('Command run successfully.', format=format)

            parts = request.urlparts
            new_parts = (parts[0], parts[1], re.sub(r'[^/]+/?$', r'', parts[2]), '', '')
            new_url = urlunsplit(new_parts)
            return redirect(new_url)

    # "view" or unknown actions
    else:
        # show file information for other output formats
        if format:
            info = util.file_info(localpath)
            data = {
                'name': info.name,
                'type': info.type,
                'size': info.size,
                'last_modified': info.last_modified,
                'mime': mimetype,
                }
            return http_response(data, format=format)

        # handle directory
        if os.path.isdir(localpath):
            return handle_directory_listing(localtargetpath, format=format)

        # handle file
        elif os.path.isfile(localpath):
            # view archive file
            if mimetype in ("application/html+zip", "application/x-maff"):
                return handle_archive_viewing(localtargetpath, mimetype)

            # view markdown
            if mimetype == "text/markdown":
                return handle_markdown_output(filepath, localtargetpath)

            # convert meta refresh to 302 redirect
            if localtargetpath.lower().endswith('.htm'):
                target = util.parse_meta_refresh(localtargetpath).target

                if target is not None:
                    # Keep several chars as javascript encodeURI do,
                    # plus "%" as target may have already been escaped.
                    new_url = urljoin(request.url, quote(target, ";,/?:@&=+$-_.!~*'()#%"))
                    return redirect(new_url)

            # show static file for other cases
            return static_file(filepath, root=runtime['root'], mimetype=mimetype, charset=None)

        # handle sub-archive path
        elif archivefile:
            return handle_subarchive_path(os.path.realpath(archivefile), subarchivepath,
                    mimetype, encoding, format=format)

        # probably 404 not found here
        return static_file(filepath, root=runtime['root'], mimetype=mimetype, charset=None)


def debug(*msg):
    """Quick dirty logging for testing purpose.
    """
    os.makedirs(os.path.dirname(runtime['log']), exist_ok=True)
    with open(runtime['log'], 'a', encoding='UTF-8') as f:
        f.write(' '.join(str(s) for s in msg))
        f.write('\n')
        f.close()


def init_app():
    """Run initialization and return the app.
    """
    runtime['root'] = os.path.abspath(config['app']['root'])
    runtime['name'] = config['app']['name']

    # add path for themes
    runtime['themes'] = [
        os.path.join(runtime['root'], WSB_DIR, 'themes', config['app']['theme']),
        os.path.join(os.path.dirname(__file__), 'themes', config['app']['theme']),
        ]
    runtime['statics'] = [os.path.join(t, 'static') for t in runtime['themes']]
    runtime['templates'] = [os.path.join(t, 'templates') for t in runtime['themes']]
    bottle.TEMPLATE_PATH = runtime['templates']

    # init token_handler
    global token_handler
    token_handler = util.TokenHandler(os.path.join(runtime['root'], WSB_DIR, 'server', 'token'))

    # init debugging logger
    runtime['log'] = os.path.join(runtime['root'], WSB_DIR, 'server', 'logs', 'debug.log')

    return app
