#!/usr/bin/env python3
"""The WGSI application.
"""
import os
import traceback
import shutil
import io
import mimetypes
import re
import zipfile
import tempfile
import time
import json
import functools
from urllib.parse import urlsplit, urlunsplit, urljoin, quote, unquote
from zlib import adler32
from contextlib import contextmanager

# dependency
import flask
from flask import request, Response, redirect, abort, render_template
from flask import current_app
from werkzeug.local import LocalProxy
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.datastructures import WWWAuthenticate
from werkzeug.exceptions import HTTPException
from werkzeug.http import is_resource_modified
from werkzeug.http import http_date
from werkzeug.http import parse_options_header, dump_options_header
from werkzeug.utils import cached_property
import jinja2
import commonmark

# this package
from . import *
from . import __version__
from . import Config
from . import util
from ._compat.contextlib import nullcontext
from ._compat import zip_stream

# see: https://url.spec.whatwg.org/#percent-encoded-bytes
quote_path = functools.partial(quote, safe=":/[]@!$&'()*+,;=")
quote_path.__doc__ = "Escape reserved chars for the path part of a URL."

bp = flask.Blueprint('default', __name__)
runtime = LocalProxy(lambda: current_app.config['WEBSCRAPBOOK_RUNTIME'])


def static_file(filename, mimetype=None):
    """Output the specified file to the client.

    Args:
        filename: absolute path of the file to output.
    """
    if not os.path.isfile(filename):
        abort(404)
    response = flask.send_file(filename, conditional=True, mimetype=mimetype)
    response.headers.set('Accept-Ranges', 'bytes')
    response.headers.set('Cache-Control', 'no-cache')
    if runtime['config']['app']['content_security_policy'] == 'strict':
        response.headers.set('Content-Security-Policy', "connect-src 'none'; form-action 'none';")
    return response


def zip_static_file(zip, subpath, mimetype=None):
    """Output the specified file in a ZIP to the client.

    Args:
        zip: an opened zipfile.ZipFile
        subpath: str or zipfile.ZipInfo
    """
    if not isinstance(subpath, zipfile.ZipInfo):
        try:
            info = zip.getinfo(subpath)
        except KeyError:
            abort(404)
    else:
        info = subpath

    fh = zip.open(info, 'r')

    lm = info.date_time
    lm = int(time.mktime((lm[0], lm[1], lm[2], lm[3], lm[4], lm[5], 0, 0, -1)))
    last_modified = http_date(lm)

    etag = "%s-%s-%s" % (
        lm,
        info.file_size,
        adler32(info.filename.encode("utf-8")) & 0xFFFFFFFF,
        )

    headers = {
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'no-cache',
        'Last-Modified': last_modified,
        'ETag': etag,
        }
    if runtime['config']['app']['content_security_policy'] == 'strict':
        headers['Content-Security-Policy'] = "connect-src 'none'; form-action 'none';"

    response = Response(fh, headers=headers, mimetype=mimetype)
    response.make_conditional(request.environ, accept_ranges=True, complete_length=info.file_size)
    return response


def http_response(body='', status=None, headers=None, format=None):
    """Handle formatted response.

    ref: https://jsonapi.org
    """
    if not format:
        mimetype = None

    # expect body to be a JSON-serializable object
    elif format == 'json':
        mimetype = 'application/json'

        body = {
            'success': True,
            'data': body,
            }

        body = json.dumps(body, ensure_ascii=False)

    # expect body to be a generator of text (mostly JSON) data
    elif format == 'sse':
        mimetype = 'text/event-stream'

        def wrapper(gen):
            try:
                for data in gen:
                    yield "data: " + data + "\n\n"
            except Exception:
                traceback.print_exc()
                err = {'error': {'message': 'Internal Server Error'}}
                yield "data: " + json.dumps(err, ensure_ascii=False) + "\n\n"

            yield "event: complete" + "\n"
            yield "data: " + "\n\n"

        body = wrapper(body)

    else:
        abort(400, f'Output format "{format}" is not supported.')

    return Response(body, status, headers, mimetype=mimetype)


def get_archive_path(filepath):
    """Parse archive file path and the sub-archive path.

    - Priority:
      entry.zip!/entry1.zip!/ = entry.zip!/entry1.zip! >
      entry.zip!/entry1.zip >
      entry.zip!/ = entry.zip! >
      entry.zip

    Returns:
        a list [path-to-directory-or-file]
        or [path-to-zip-file, subpath1, subpath2, ...]
    """
    for m in reversed(list(re.finditer(r'!/', filepath, flags=re.I))):
        archivepath = filepath[:m.start(0)].rstrip('/')
        archivefile = os.path.normpath(os.path.join(runtime['root'], archivepath.lstrip('/')))
        conflicting = archivefile + '!'
        if os.path.lexists(conflicting):
            break

        # if parent directory does not exist, FileNotFoundError is raised on
        # Windows, while NotADirectoryError is raised on Linux
        try:
            zip = zipfile.ZipFile(archivefile, 'r')
        except (zipfile.BadZipFile, FileNotFoundError, NotADirectoryError):
            pass
        else:
            with zip as zip:
                def get_subpath(zp, filepath):
                    for m in reversed(list(re.finditer(r'!/', filepath, flags=re.I))):
                        archivepath = filepath[:m.start(0)]
                        conflicting = archivepath + '!/'
                        if any(i.startswith(conflicting) for i in zp.namelist()):
                            break
                        try:
                            with zp.open(archivepath, 'r') as f:
                                f = zip_stream(f)
                                with zipfile.ZipFile(f, 'r') as zip:
                                    rv.append(archivepath)
                                    get_subpath(zip, filepath[m.end(0):])
                                    return
                        except (KeyError, zipfile.BadZipFile):
                            pass
                    rv.append(filepath.rstrip('/'))

                rv = [archivepath]
                get_subpath(zip, filepath[m.end(0):])
                return rv

    return [filepath.rstrip('/')]


@contextmanager
def open_archive_path(paths, mode='r', filters=None):
    """Open the innermost zip.

    Args:
        paths: [path-to-zip-file, subpath1, subpath2, ...]
        mode: 'r' for reading, 'w' for modifying
        filters: a list of file or folder to remove
    """
    last = len(paths) - 1
    if last < 1:
        raise ValueError('length of paths must > 1')

    filtered = False
    stack = []
    try:
        zip = zipfile.ZipFile(paths[0])
        stack.append(zip)
        for i in range(1, last):
            f = zip.open(paths[i])
            f = zip_stream(f)
            stack.append(f)
            zip = zipfile.ZipFile(f)
            stack.append(zip)

        if mode == 'r':
            yield zip

        elif mode == 'w':
            # create a buffer for writing
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as zip:
                yield zip

            # copy zip file
            for i in reversed(range(1, last + 1)):
                zip0 = stack.pop()
                with zipfile.ZipFile(buffer, 'a') as zip:
                    for info in zip0.infolist():
                        if filters and i == last:
                            if any(info.filename == filter or info.filename.startswith(filter + '/')
                                    for filter in filters):
                                filtered = True
                                continue

                        try:
                            zip.getinfo(info.filename)
                        except KeyError:
                            pass
                        else:
                            continue

                        try:
                            zip.writestr(info, zip0.read(info),
                                    compress_type=info.compress_type,
                                    compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9)
                        except TypeError:
                            # compresslevel is supported since Python 3.7
                            zip.writestr(info, zip0.read(info),
                                    compress_type=info.compress_type)

                if filters and not filtered:
                    raise KeyError('paths to filter do not exist')

                if i == 1:
                    break

                # writer to another buffer for the parent zip
                buffer2 = io.BytesIO()
                with zipfile.ZipFile(buffer2, 'w') as zip:
                    zip.writestr(paths[i - 1], buffer.getvalue(), compress_type=zipfile.ZIP_STORED)
                buffer.close()
                buffer = buffer2

                # pop a file handler
                stack.pop()

            # write to the outermost zip
            # use 'r+b' as 'wb' causes PermissionError for hidden file in Windows
            buffer.seek(0)
            with open(paths[0], 'r+b') as fw, buffer as fr:
                fw.truncate()
                while True:
                    bytes = fr.read(8192)
                    if not bytes: break
                    fw.write(bytes)
    finally:
        for f in reversed(stack):
            f.close()


def is_local_access():
    """Determine if the client is in same device.
    """
    server_host = request.host.partition(':')[0]
    client_host = request.remote_addr
    return util.is_localhost(server_host) or util.is_localhost(client_host) or server_host == client_host


def get_permission(auth_info, auth_config):
    """Calculate effective permission from provided auth info and config.
    """
    auth = auth_info or {}
    user = auth.get('username') or ''
    pw = auth.get('password') or ''

    for _, entry in auth_config.items():
        entry_user = entry.get('user', '')
        if user != entry_user:
            continue

        entry_pw = entry.get('pw', '')
        entry_pw_salt = entry.get('pw_salt', '')
        entry_pw_type = entry.get('pw_type', '')
        if util.encrypt(pw, entry_pw_salt, entry_pw_type) != entry_pw:
            continue

        entry_permission = entry.get('permission', 'all')
        return entry_permission

    return ''


def verify_authorization(perm, action):
    """Check if authorized or not.
    """
    if perm == 'all':
        return True

    if perm == 'read':
        return action not in {'token', 'lock', 'unlock', 'mkdir', 'mkzip', 'save', 'delete', 'move', 'copy'}

    if perm == 'view':
        return action in {'view', 'info', 'source', 'download', 'static'}

    return False


def handle_directory_listing(paths, zip=None, redirect_slash=True, recursive=False, format=None):
    """List contents in a directory.

    Args:
        paths: [path-to-zip-file, subpath1, subpath2, ...]
        zip: an opened zipfile.ZipFile object for faster reading
    """
    # ensure directory has trailing '/'
    if redirect_slash and not request.path.endswith('/'):
        parts = urlsplit(request.url)
        new_url = urlunsplit((
            parts.scheme,
            parts.netloc,
            quote_path(unquote(parts.path)) + '/',
            parts.query,
            parts.fragment,
            ))
        return redirect(new_url)

    # prepare index
    if len(paths) > 1:
        # support 304 if zip not modified
        stats = os.stat(paths[0])
        last_modified = http_date(stats.st_mtime)
        etag = "%s-%s-%s" % (
            stats.st_mtime,
            stats.st_size,
            adler32(paths[0].encode("utf-8")) & 0xFFFFFFFF,
            )

        if not is_resource_modified(request.environ, etag=etag, last_modified=last_modified):
            return http_response(status=304, format=format)

        headers = {
            'Cache-Control': 'no-cache',
            'Last-Modified': last_modified,
            'ETag': etag,
            }

        with nullcontext(zip) if zip else open_archive_path(paths) as zip:
            subentries = util.zip_listdir(zip, paths[-1], recursive)

    else:
        # disallow cache to reflect any content file change
        stats = os.stat(paths[0])
        headers = {
            'Cache-Control': 'no-store',
            'Last-Modified': http_date(stats.st_mtime),
            }

        subentries = util.listdir(paths[0], recursive)

    if format == 'sse':
        def gen():
            for entry in subentries:
                data = {
                    'name': entry.name,
                    'type': entry.type,
                    'size': entry.size,
                    'last_modified': entry.last_modified,
                    }

                yield json.dumps(data, ensure_ascii=False)

        return http_response(gen(), headers=headers, format=format)

    if format == 'json':
        data = []
        for entry in subentries:
            data.append({
                    'name': entry.name,
                    'type': entry.type,
                    'size': entry.size,
                    'last_modified': entry.last_modified,
                    })
        return http_response(data, headers=headers, format=format)

    body = render_template('index.html',
            sitename=runtime['name'],
            is_local=is_local_access(),
            base=request.script_root,
            path=request.path,
            pathparts=request.paths,
            subentries=subentries,
            )
    return http_response(body, headers=headers)


def handle_archive_viewing(paths, mimetype):
    """Handle direct visit of HTZ/MAFF file.

    Args:
        paths: [path-to-zip-file, subpath1, subpath2, ...]
    """
    def list_maff_pages(pages):
        """List available web pages in a MAFF file.
        """
        return render_template('maff_index.html',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=request.script_root,
                path=request.path,
                pages=pages,
                )

    if mimetype == "application/html+zip":
        subpath = "index.html"
    else:
        if len(paths) > 1:
            with open_archive_path(paths) as zip:
                with zip.open(paths[-1]) as zh:
                    pages = util.get_maff_pages(zh)
        else:
            pages = util.get_maff_pages(paths[-1])

        if len(pages) > 1:
            # multiple index files
            return list_maff_pages(pages)

        if len(pages) == 0:
            # no valid index file found
            return list_maff_pages([])

        subpath = pages[0].indexfilename

    parts = urlsplit(request.url)
    new_url = urlunsplit((
        parts.scheme,
        parts.netloc,
        quote_path(unquote(parts.path)) + '!/' + quote_path(subpath),
        parts.query,
        parts.fragment,
        ))
    return redirect(new_url)


def handle_markdown_output(paths, zip=None):
    """Output processed markdown.

    Args:
        paths: [path-to-zip-file, subpath1, subpath2, ...]
        zip: an opened zipfile.ZipFile object for faster reading
    """
    if len(paths) > 1:
        if zip:
            context = nullcontext(zip)
        else:
            context = open_archive_path(paths)
    else:
        context = nullcontext(None)

    with context as zip:
        # calculate last-modified time and etag
        if zip:
            info = zip.getinfo(paths[-1])

            lm = info.date_time
            lm = int(time.mktime((lm[0], lm[1], lm[2], lm[3], lm[4], lm[5], 0, 0, -1)))
            last_modified = http_date(lm)

            etag = "%s-%s-%s" % (
                lm,
                info.file_size,
                adler32(info.filename.encode("utf-8")) & 0xFFFFFFFF,
                )
        else:
            stats = os.stat(paths[0])
            last_modified = http_date(stats.st_mtime)
            etag = "%s-%s-%s" % (
                stats.st_mtime,
                stats.st_size,
                adler32(paths[0].encode("utf-8")) & 0xFFFFFFFF,
                )

        if not is_resource_modified(request.environ, etag=etag, last_modified=last_modified):
            return http_response(status=304)

        headers = {
            'Cache-Control': 'no-cache',
            'Last-Modified': last_modified,
            'ETag': etag,
            }
        if runtime['config']['app']['content_security_policy'] == 'strict':
            headers['Content-Security-Policy'] = "connect-src 'none'; form-action 'none';"

        # prepare content
        if zip:
            with zip.open(info) as f:
                body = f.read().decode('UTF-8')
        else:
            with open(paths[0], 'r', encoding='UTF-8') as f:
                body = f.read()

    body = render_template('markdown.html',
            sitename=runtime['name'],
            is_local=is_local_access(),
            base=request.script_root,
            path=request.path,
            pathparts=request.paths,
            content=commonmark.commonmark(body),
            )

    return http_response(body, headers=headers)


class Request(flask.Request):
    """Subclassed Request object for more useful properties.
    """
    @cached_property
    def paths(self):
        """Like request.path, but with ZIP subpaths resolved."""
        return get_archive_path(self.path)

    @cached_property
    def localpath(self):
        """Corresponding filesystem path of the requested path."""
        return os.path.normpath(os.path.join(runtime['root'], self.path.strip('/')))

    @cached_property
    def localpaths(self):
        """Like localpath, but with ZIP subpaths resolved."""
        paths = self.paths.copy()
        paths[0] = os.path.normpath(os.path.join(runtime['root'], paths[0].lstrip('/')))
        return paths

    @cached_property
    def localrealpath(self):
        """Like localpath, but with symlinks resolved."""
        return os.path.realpath(self.localpath)

    @cached_property
    def localmimetype(self):
        """Mimetype of the requested path."""
        mimetype, _ = mimetypes.guess_type(self.localrealpath)
        return mimetype

    @cached_property
    def action(self):
        """Shortcut of the requested action."""
        rv = request.values.get('a', default='view')
        rv = request.values.get('action', default=rv)
        return rv

    @cached_property
    def format(self):
        """Shortcut of the requested format."""
        rv = request.values.get('f')
        rv = request.values.get('format', default=rv)
        return rv


class ActionHandler():
    def _handle_action(self, action):
        try:
            handler = getattr(self, action, None) or self.unknown
            return handler()
        except PermissionError:
            abort(403)

    def _handle_advanced(func):
        """A decorator function that helps handling an advanced command.

        - Verify POST method.
        - Verify access token.
        - Provide a default return value.
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            format = request.format

            # require POST method
            if request.method != 'POST':
                abort(405, valid_methods=['POST'])

            # validate and revoke token
            token = request.values.get('token') or ''

            if not runtime['token_handler'].validate(token):
                abort(400, 'Invalid access token.')

            runtime['token_handler'].delete(token)

            rv = func(self, *args, **kwargs)

            if rv is not None:
                return rv

            if format:
                return http_response('Command run successfully.', format=format)

            return http_response(status=204)

        return wrapper

    def _handle_lock(func):
        """A decorator function that helps handling the lock.

        - Verify lock name.
        - Verify targetpath.
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # verify name
            name = request.values.get('name')
            if name is None:
                abort(400, "Lock name is not specified.")

            # validate targetpath
            targetname = util.encrypt(name, method='md5') + '.lock'
            targetpath = os.path.join(runtime['locks'], targetname)

            return func(self, name=name, targetpath=targetpath, *args, **kwargs)

        return wrapper

    def _handle_writing(func):
        """A decorator function that helps handling a writing action.
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if os.path.abspath(request.localpath) == runtime['root']:
                abort(403, "Unable to operate the root directory.")

            return func(self, *args, **kwargs)

        return wrapper

    def _handle_renaming(func):
        """A decorator function that helps handling a move/copy action.
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            localpaths = request.localpaths

            if len(localpaths) > 1:
                with open_archive_path(localpaths) as zip:
                    try:
                        zip.getinfo(localpaths[-1])
                    except KeyError:
                        if not util.zip_hasdir(zip, localpaths[-1] + '/'):
                            abort(404, "Source does not exist.")
            else:
                if not os.path.lexists(localpaths[0]):
                    abort(404, "Source does not exist.")

            target = request.values.get('target')

            if target is None:
                abort(400, 'Target is not specified.')

            targetpaths = get_archive_path(target)
            targetpaths[0] = os.path.normpath(os.path.join(runtime['root'], targetpaths[0].lstrip('/')))

            if not targetpaths[0].startswith(os.path.join(runtime['root'], '')):
                abort(403, "Unable to operate beyond the root directory.")

            if len(targetpaths) > 1:
                with open_archive_path(targetpaths) as zip:
                    try:
                        zip.getinfo(targetpaths[-1])
                    except KeyError:
                        if util.zip_hasdir(zip, targetpaths[-1] + '/'):
                            abort(400, 'Found something at target.')
                    else:
                        abort(400, 'Found something at target.')
            else:
                if os.path.lexists(targetpaths[0]):
                    abort(400, 'Found something at target.')

            return func(self, sourcepaths=localpaths, targetpaths=targetpaths, *args, **kwargs)

        return wrapper

    def unknown(self):
        """Default handler for an undefined action"""
        abort(400, "Action not supported.")

    def view(self):
        """Show the content of a file or list a directory.

        If formatted, show information of the file or directory.
        """
        # info for other output formats
        if request.format:
            return self.info()

        localpaths = request.localpaths
        mimetype = request.localmimetype

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zip:
                try:
                    info = zip.getinfo(localpaths[-1])
                except KeyError:
                    # File does not exist.  List directory only when URL
                    # suffixed with "/", as it's not a common operation,
                    # and it's costy to check for directory existence in
                    # a ZIP.
                    if request.path.endswith('/'):
                        try:
                            return handle_directory_listing(localpaths, zip, redirect_slash=False)
                        except util.ZipDirNotFoundError:
                            abort(404)
                    abort(404)
                else:
                    # view archive file
                    if mimetype in ("application/html+zip", "application/x-maff"):
                        return handle_archive_viewing(localpaths, mimetype)

                    # view markdown
                    if mimetype == "text/markdown":
                        return handle_markdown_output(localpaths, zip)

                    # convert meta refresh to 302 redirect
                    if localpaths[-1].lower().endswith('.htm'):
                        with zip.open(info) as fh:
                            target = util.parse_meta_refresh(fh).target

                        if target is not None:
                            # Keep several chars as javascript encodeURI do,
                            # plus "%" as target may have already been escaped.
                            parts = urlsplit(urljoin(request.url, quote(target, ";,/?:@&=+$-_.!~*'()#%")))
                            new_url = urlunsplit((
                                parts.scheme,
                                parts.netloc,
                                quote_path(unquote(parts.path)),
                                parts.query,
                                parts.fragment,
                                ))
                            return redirect(new_url)

                    # show static file for other cases
                    response = zip_static_file(zip, localpaths[-1], mimetype=mimetype)
        else:
            localpath = localpaths[0]

            # handle directory
            if os.path.isdir(localpath):
                return handle_directory_listing(localpaths)

            # handle file
            elif os.path.isfile(localpath):
                # view archive file
                if mimetype in ("application/html+zip", "application/x-maff"):
                    return handle_archive_viewing(localpaths, mimetype)

                # view markdown
                if mimetype == "text/markdown":
                    return handle_markdown_output(localpaths)

                # convert meta refresh to 302 redirect
                if request.localrealpath.lower().endswith('.htm'):
                    target = util.parse_meta_refresh(localpath).target

                    if target is not None:
                        # Keep several chars as javascript encodeURI do,
                        # plus "%" as target may have already been escaped.
                        parts = urlsplit(urljoin(request.url, quote(target, ";,/?:@&=+$-_.!~*'()#%")))
                        new_url = urlunsplit((
                            parts.scheme,
                            parts.netloc,
                            quote_path(unquote(parts.path)),
                            parts.query,
                            parts.fragment,
                            ))
                        return redirect(new_url)

                # show static file for other cases
                response = static_file(localpath, mimetype=mimetype)

            else:
                abort(404)

        # don't include charset
        m, p = parse_options_header(response.headers.get('Content-Type'))
        try:
            del p['charset']
        except KeyError:
            pass
        response.headers.set('Content-Type', dump_options_header(m, p))

        return response

    def source(self):
        """Show file content as plain text."""
        if request.format:
            abort(400, "Action not supported.")

        localpaths = request.localpaths

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zip:
                response = zip_static_file(zip, localpaths[-1])
        else:
            response = static_file(localpaths[0])

        # show as inline plain text
        # @TODO: Chromium (80) seems to ignore header mimetype for certain types
        #        like image and zip
        encoding = request.values.get('e', 'utf-8')
        encoding = request.values.get('encoding', default=encoding)
        response.headers.set('Content-Type', 'text/plain; charset=' + quote(encoding))
        response.headers.set('Content-Disposition', 'inline')

        return response

    def download(self):
        """Download the  file."""
        if request.format:
            abort(400, "Action not supported.")

        localpaths = request.localpaths

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zip:
                response = zip_static_file(zip, localpaths[-1], mimetype=request.localmimetype)
        else:
            response = static_file(localpaths[0])

        filename = quote_path(os.path.basename(request.localrealpath))
        response.headers.set('Content-Disposition',
                f'''attachment; filename*=UTF-8''{filename}; filename="{filename}"''')
        return response

    def info(self):
        """Show information of a path."""
        format = request.format

        if not format:
            abort(400, "Action not supported.")

        localpaths = request.localpaths
        mimetype = request.localmimetype

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zip:
                info = util.zip_file_info(zip, localpaths[-1])
        else:
            info = util.file_info(localpaths[0])

        data = {
            'name': info.name,
            'type': info.type,
            'size': info.size,
            'last_modified': info.last_modified,
            'mime': mimetype,
            }
        return http_response(data, format=format)

    def list(self):
        """List entries in a directory."""
        format = request.format

        if not format:
            abort(400, "Action not supported.")

        recursive = request.values.get('recursive', type=bool)
        localpaths = request.localpaths

        if len(localpaths) > 1:
            try:
                return handle_directory_listing(localpaths, redirect_slash=False, recursive=recursive, format=format)
            except util.ZipDirNotFoundError:
                abort(404, "Directory does not exist.")

        if os.path.isdir(localpaths[0]):
            return handle_directory_listing(localpaths, redirect_slash=False, recursive=recursive, format=format)

        abort(404, "Directory does not exist.")

    def static(self):
        """Show a static file of the current theme."""
        format = request.format

        if format:
            abort(400, "Action not supported.")

        filepath = request.path.strip('/')
        for i in runtime['statics']:
            f = os.path.join(i, filepath)
            if os.path.isfile(f):
                return static_file(f)

        abort(404)

    def edit(self):
        """Simple text editor for a file."""
        format = request.format

        if format:
            abort(400, "Action not supported.")

        localpaths = request.localpaths
        localpath = localpaths[0]

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            abort(400, "Found a non-file here.")

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zip:
                try:
                    info = zip.getinfo(localpaths[-1])
                except KeyError:
                    body = b''
                else:
                    body = zip.read(info)
        else:
            try:
                with open(localpath, 'rb') as f:
                    body = f.read()
            except FileNotFoundError:
                body = b''

        encoding = request.values.get('e')
        encoding = request.values.get('encoding', default=encoding)

        try:
            body = body.decode(encoding or 'UTF-8')
        except (LookupError, UnicodeDecodeError):
            encoding = 'ISO-8859-1'
            body = body.decode(encoding)

        body = render_template('edit.html',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=request.script_root,
                path=request.path,
                body=body,
                encoding=encoding,
                )

        return http_response(body, format=format)

    def editx(self):
        """HTML editor for a file."""
        format = request.format

        if format:
            abort(400, "Action not supported.")

        localpaths = request.localpaths
        localpath = localpaths[0]

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            abort(400, "Found a non-file here.")

        if not request.localmimetype in ("text/html", "application/xhtml+xml"):
            abort(400, "This is not an HTML file.")

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zip:
                try:
                    info = zip.getinfo(localpaths[-1])
                except KeyError:
                    abort(404)
        else:
            if not os.path.lexists(localpath):
                abort(404)

        body = render_template('editx.html',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=request.script_root,
                path=request.path,
                )

        return http_response(body, format=format)

    def exec(self):
        """Launch a file or directory."""
        format = request.format

        if not is_local_access():
            abort(400, "Command can only run on local device.")

        localpath = request.localpath

        if not os.path.lexists(localpath):
            abort(404, "File does not exist.")

        util.launch(localpath)

        if format:
            return http_response('Command run successfully.', format=format)

        return http_response(status=204)

    def browse(self):
        """Open a file or directory in the file browser."""
        format = request.format

        if not is_local_access():
            abort(400, "Command can only run on local device.")

        localpath = request.localpath

        if not os.path.lexists(localpath):
            abort(404, "File does not exist.")

        util.view_in_explorer(localpath)

        if format:
            return http_response('Command run successfully.', format=format)

        return http_response(status=204)

    def config(self):
        """Show server config."""
        format = request.format

        if not format:
            abort(400, "Action not supported.")

        data = runtime['config'].dump_object()

        # filter values for better security
        data = {k:v for k, v in data.items() if k in ('app', 'book')}
        data['app'] = {k:v for k, v in data['app'].items() if k in ('name', 'theme')}

        # add and rewrite values for client to better know the server
        data['app']['base'] = request.script_root
        data['app']['is_local'] = is_local_access()
        data['VERSION'] = __version__
        data['WSB_DIR'] = WSB_DIR
        data['WSB_LOCAL_CONFIG'] = WSB_LOCAL_CONFIG
        data['WSB_EXTENSION_MIN_VERSION'] = WSB_EXTENSION_MIN_VERSION

        return http_response(data, format=format)

    def token(self):
        """Acquire a token and return its name."""
        format = request.format

        # require POST method
        if request.method != 'POST':
            abort(405, valid_methods=['POST'])

        return http_response(runtime['token_handler'].acquire(), format=format)

    @_handle_advanced
    @_handle_lock
    def lock(self, name, targetpath):
        """Acquire a lock for the given name.

        URL params:
        - chkt: recheck until the lock file not exist or fail out when time out.
        - chks: how long to treat the lock file as stale.
        """
        format = request.format
        check_stale = request.values.get('chks', 300, type=int)
        check_timeout = request.values.get('chkt', 5, type=int)
        check_expire = time.time() + check_timeout
        check_delta = min(check_timeout, 0.1)

        try:
            while True:
                try:
                    os.makedirs(targetpath)
                except FileExistsError:
                    t = time.time()

                    if t >= check_expire or not os.path.isdir(targetpath):
                        abort(500, f'Unable to acquire lock "{name}".')

                    try:
                        lock_expire = os.stat(targetpath).st_mtime + check_stale
                    except FileNotFoundError:
                        # Lock removed by another process during the short interval.
                        # Try acquire again.
                        continue

                    if t >= lock_expire:
                        # Lock expired. Touch rather than remove and make for atomicity.
                        try:
                            os.utime(targetpath)
                        except OSError:
                            traceback.print_exc()
                            abort(500, f'Unable to regenerate stale lock "{name}".')
                        else:
                            break

                    time.sleep(check_delta)
                else:
                    break
        except HTTPException:
            raise
        except Exception:
            traceback.print_exc()
            abort(500, f'Unable to create lock "{name}".')

    @_handle_advanced
    @_handle_lock
    def unlock(self, name, targetpath):
        """Release a lock for the given name."""
        format = request.format

        try:
            os.rmdir(targetpath)
        except FileNotFoundError:
            pass
        except Exception:
            traceback.print_exc()
            abort(500, f'Unable to remove lock "{name}".')

    @_handle_advanced
    @_handle_writing
    def mkdir(self):
        """Create a directory."""
        format = request.format
        localpaths = request.localpaths

        if len(localpaths) > 1:
            try:
                folderpath = localpaths[-1] + '/'
                zip = None

                with open_archive_path(localpaths) as zip0:
                    try:
                        zip0.getinfo(folderpath)
                    except KeyError:
                        # append for a non-nested zip
                        if len(localpaths) == 2:
                            zip = zipfile.ZipFile(localpaths[0], 'a')
                    else:
                        # skip as the folder already exists
                        return

                if zip is None:
                    zip = open_archive_path(localpaths, 'w')

                with zip as zip:
                    info = zipfile.ZipInfo(folderpath, time.localtime())
                    zip.writestr(info, b'', compress_type=zipfile.ZIP_STORED)
            except Exception:
                traceback.print_exc()
                abort(500, "Unable to write to this ZIP file.")

        else:
            localpath = localpaths[0]

            if os.path.lexists(localpath) and not os.path.isdir(localpath):
                abort(400, "Found a non-directory here.")

            try:
                os.makedirs(localpath, exist_ok=True)
            except OSError:
                traceback.print_exc()
                abort(500, "Unable to create a directory here.")


    @_handle_advanced
    @_handle_writing
    def mkzip(self):
        """Create a zip file."""
        format = request.format
        localpaths = request.localpaths

        if len(localpaths) > 1:
            try:
                zip = None

                # append for a nonexistent path in a non-nested zip
                if len(localpaths) == 2:
                    zip0 = zipfile.ZipFile(localpaths[0], 'a')
                    try:
                        zip0.getinfo(localpaths[-1])
                    except KeyError:
                        zip = zip0
                    except:
                        zip0.close()
                        raise
                    else:
                        zip0.close()

                if zip is None:
                    zip = open_archive_path(localpaths, 'w')

                with zip as zip:
                    info = zipfile.ZipInfo(localpaths[-1], time.localtime())
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, 'w'):
                        pass
                    zip.writestr(info, buf.getvalue(), compress_type=zipfile.ZIP_STORED)
            except Exception:
                traceback.print_exc()
                abort(500, "Unable to write to this ZIP file.")

        else:
            localpath = localpaths[0]

            if os.path.lexists(localpath) and not os.path.isfile(localpath):
                abort(400, "Found a non-file here.")

            try:
                os.makedirs(os.path.dirname(localpath), exist_ok=True)
            except Exception:
                traceback.print_exc()
                abort(500, "Unable to write to this path.")

            try:
                with zipfile.ZipFile(localpath, 'w') as f:
                    pass
            except Exception:
                traceback.print_exc()
                abort(500, "Unable to write to this file.")


    @_handle_advanced
    @_handle_writing
    def save(self):
        """Write a file with provided text or uploaded stream."""
        format = request.format
        localpaths = request.localpaths

        if len(localpaths) > 1:
            try:
                zip = None

                # append for a nonexistent path in a non-nested zip
                if len(localpaths) == 2:
                    zip0 = zipfile.ZipFile(localpaths[0], 'a')
                    try:
                        zip0.getinfo(localpaths[-1])
                    except KeyError:
                        zip = zip0
                    except Exception:
                        zip0.close()
                        raise
                    else:
                        zip0.close()

                if zip is None:
                    zip = open_archive_path(localpaths, 'w')

                with zip as zip:
                    info = zipfile.ZipInfo(localpaths[-1], time.localtime())
                    file = request.files.get('upload')
                    if file is not None:
                        with zip.open(info, 'w', force_zip64=True) as fh:
                            stream = file.stream
                            while True:
                                s = stream.read(8192)
                                if not s: break
                                fh.write(s)
                    else:
                        bytes = request.values.get('text', '').encode('ISO-8859-1')
                        try:
                            zip.writestr(info, bytes, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
                        except TypeError:
                            # compresslevel is supported since Python 3.7
                            zip.writestr(info, bytes, compress_type=zipfile.ZIP_DEFLATED)
            except Exception:
                traceback.print_exc()
                abort(500, "Unable to write to this ZIP file.")

        else:
            localpath = localpaths[0]

            if os.path.lexists(localpath) and not os.path.isfile(localpath):
                abort(400, "Found a non-file here.")

            try:
                os.makedirs(os.path.dirname(localpath), exist_ok=True)
            except OSError:
                traceback.print_exc()
                abort(500, "Unable to write to this path.")

            try:
                file = request.files.get('upload')
                if file is not None:
                    file.save(localpath)
                else:
                    bytes = request.values.get('text', '').encode('ISO-8859-1')
                    with open(localpath, 'wb') as f:
                        f.write(bytes)
            except Exception:
                traceback.print_exc()
                abort(500, "Unable to write to this file.")


    @_handle_advanced
    @_handle_writing
    def delete(self):
        """Delete a file or directory."""
        format = request.format
        localpaths = request.localpaths

        if len(localpaths) > 1:
            try:
                with open_archive_path(localpaths, 'w', [localpaths[-1]]) as zip:
                    pass
            except KeyError:
                # fail since nothing is deleted
                abort(404, "Entry does not exist in this ZIP file.")
            except Exception:
                traceback.print_exc()
                abort(500, "Unable to write to this ZIP file.")

        else:
            localpath = localpaths[0]

            if not os.path.lexists(localpath):
                abort(404, "File does not exist.")

            if util.file_is_link(localpath):
                try:
                    os.remove(localpath)
                except OSError:
                    traceback.print_exc()
                    abort(500, "Unable to delete this link.")
            elif os.path.isfile(localpath):
                try:
                    os.remove(localpath)
                except OSError:
                    traceback.print_exc()
                    abort(500, "Unable to delete this file.")
            elif os.path.isdir(localpath):
                try:
                    shutil.rmtree(localpath)
                except OSError:
                    traceback.print_exc()
                    abort(500, "Unable to delete this directory.")
            else:
                # this should not happen
                abort(500, "Unable to handle this path.")

    @_handle_advanced
    @_handle_writing
    @_handle_renaming
    def move(self, sourcepaths, targetpaths):
        """Move a file or directory."""
        format = request.format

        try:
            if len(sourcepaths) == 1:
                if len(targetpaths) == 1:
                    try:
                        os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                    except OSError:
                        traceback.print_exc()
                        abort(500, "Unable to copy to this path.")

                    shutil.move(sourcepaths[0], targetpaths[0])

                else:
                    # Moving a file into a zip is like moving across disk,
                    # which makes little sense. Additionally, moving a
                    # symlink/junction should rename the entry and cannot be
                    # implemented as copying-deleting. Forbid such operation to
                    # prevent a confusion.
                    abort(400, "Unable to move across a zip.")

            elif len(sourcepaths) > 1:
                if len(targetpaths) == 1:
                    # Moving from zip to disk is like moving across disk, which
                    # makes little sense.
                    abort(400, "Unable to move across a zip.")

                else:
                    with open_archive_path(sourcepaths) as zip:
                        try:
                            zip.getinfo(sourcepaths[-1])
                        except KeyError:
                            entries = [e for e in zip.namelist() if e.startswith(sourcepaths[-1] + '/')]
                        else:
                            entries = [sourcepaths[-1]]

                        with open_archive_path(targetpaths, 'w') as zip2:
                            cut = len(sourcepaths[-1])
                            for entry in entries:
                                info = zip.getinfo(entry)
                                info.filename = targetpaths[-1] + entry[cut:]
                                try:
                                    zip2.writestr(info, zip.read(entry),
                                            compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9)
                                except TypeError:
                                    # compresslevel is supported since Python 3.7
                                    zip2.writestr(info, zip.read(entry))

                    with open_archive_path(sourcepaths, 'w', entries) as zip:
                        pass

        except HTTPException:
            raise
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to move to the target.')

    @_handle_advanced
    @_handle_writing
    @_handle_renaming
    def copy(self, sourcepaths, targetpaths):
        """Copy a file or directory."""
        format = request.format

        # Copying a symlink/junction means copying the real file/directory.
        # It makes no sense if the symlink/junction is broken.
        if not os.path.exists(sourcepaths[0]):
            abort(404, "Source does not exist.")

        try:
            if len(sourcepaths) == 1:
                if len(targetpaths) == 1:
                    try:
                        os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                    except OSError:
                        traceback.print_exc()
                        abort(500, "Unable to copy to this path.")

                    try:
                        shutil.copytree(sourcepaths[0], targetpaths[0])
                    except NotADirectoryError:
                        shutil.copy2(sourcepaths[0], targetpaths[0])
                    except shutil.Error:
                        traceback.print_exc()
                        abort(500, 'Fail to copy some files.')

                else:
                    if os.path.isdir(sourcepaths[0]):
                        errors = []

                        with open_archive_path(targetpaths, 'w') as zip:
                            src = sourcepaths[0]
                            dst = targetpaths[-1] + '/'
                            try:
                                t = time.localtime(os.stat(src).st_mtime)[:-3]
                                zip.writestr(zipfile.ZipInfo(dst, t), '')
                            except OSError as why:
                                errors.append((src, targetpaths[:-1] + [dst], str(why)))

                            base_cut = len(os.path.join(sourcepaths[0], ''))
                            for root, dirs, files in os.walk(sourcepaths[0], followlinks=True):
                                for dir in dirs:
                                    src = os.path.join(root, dir)
                                    dst = src[base_cut:]
                                    if os.sep != '/': dst = dst.replace(os.sep, '/')
                                    dst = targetpaths[-1] + '/' + dst + '/'
                                    try:
                                        t = time.localtime(os.stat(src).st_mtime)[:-3]
                                        zip.writestr(zipfile.ZipInfo(dst, t), '')
                                    except OSError as why:
                                        errors.append((src, targetpaths[:-1] + [dst], str(why)))
                                for file in files:
                                    src = os.path.join(root, file)
                                    dst = src[base_cut:]
                                    if os.sep != '/': dst = dst.replace(os.sep, '/')
                                    dst = targetpaths[-1] + '/' + dst
                                    compressible = util.is_compressible(mimetypes.guess_type(dst)[0])
                                    compress_type = zipfile.ZIP_DEFLATED if compressible else zipfile.ZIP_STORED
                                    compresslevel = 9 if compressible else None
                                    try:
                                        try:
                                            zip.write(src, dst, compress_type, compresslevel)
                                        except TypeError:
                                            # compresslevel is supported since Python 3.7
                                            zip.write(src, dst, compress_type)
                                    except OSError as why:
                                        errors.append((src, targetpaths[:-1] + [dst], str(why)))

                        if errors:
                            try:
                                raise shutil.Error(errors)
                            except shutil.Error:
                                traceback.print_exc()
                            abort(500, 'Fail to copy some files.')

                    elif os.path.isfile(sourcepaths[0]):
                        with open_archive_path(targetpaths, 'w') as zip:
                            zip.write(sourcepaths[0], targetpaths[-1])

            elif len(sourcepaths) > 1:
                if len(targetpaths) == 1:
                    try:
                        os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                    except OSError:
                        traceback.print_exc()
                        abort(500, "Unable to copy to this path.")

                    tempdir = tempfile.mkdtemp()
                    try:
                        with open_archive_path(sourcepaths) as zip:
                            try:
                                zip.getinfo(sourcepaths[-1])
                            except KeyError:
                                entries = [e for e in zip.namelist() if e.startswith(sourcepaths[-1] + '/')]
                            else:
                                entries = [sourcepaths[-1]]

                            # extract entries and keep datetime
                            zip.extractall(tempdir, entries)
                            for entry in entries:
                                file = os.path.join(tempdir, entry)
                                date = time.mktime(zip.getinfo(entry).date_time + (0, 0, -1))
                                os.utime(file, (date, date))

                        # move to target path
                        shutil.move(os.path.join(tempdir, sourcepaths[-1]), targetpaths[0])
                    finally:
                        try:
                            shutil.rmtree(tempdir)
                        except OSError:
                            traceback.print_exc()

                else:
                    with open_archive_path(sourcepaths) as zip:
                        try:
                            zip.getinfo(sourcepaths[-1])
                        except KeyError:
                            entries = [e for e in zip.namelist() if e.startswith(sourcepaths[-1] + '/')]
                        else:
                            entries = [sourcepaths[-1]]

                        with open_archive_path(targetpaths, 'w') as zip2:
                            cut = len(sourcepaths[-1])
                            for entry in entries:
                                info = zip.getinfo(entry)
                                info.filename = targetpaths[-1] + entry[cut:]
                                try:
                                    zip2.writestr(info, zip.read(entry),
                                            compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9)
                                except TypeError:
                                    # compresslevel is supported since Python 3.7
                                    zip2.writestr(info, zip.read(entry))

        except HTTPException:
            raise
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to copy to the target.')

    _handle_advanced = staticmethod(_handle_advanced)
    _handle_lock = staticmethod(_handle_lock)
    _handle_writing = staticmethod(_handle_writing)
    _handle_renaming = staticmethod(_handle_renaming)

action_handler = ActionHandler()


def static_url(path):
    return f'{quote_path(request.script_root)}/{quote_path(path)}?a=static'


@bp.before_request
def handle_before_request():
    # replace SCRIPT_NAME with the custom if set
    if runtime['config']['app']['base']:
        # Flask treats SCRIPT_NAME in the same way as PATH_INFO, which is an
        # IRI string decoded as ISO-8859-1 according to WSGI standard).
        request.environ['SCRIPT_NAME'] = unquote(runtime['config']['app']['base']).encode('UTF-8').decode('ISO-8859-1')

    # handle authorization
    try:
        auth_config = runtime['config']['auth']
    except KeyError:
        # auth not required
        return

    perm = get_permission(request.authorization, auth_config)
    if not verify_authorization(perm, request.action):
        auth = WWWAuthenticate()
        auth.set_basic(runtime['config']['app']['name'])
        abort(401, 'You are not authorized.', www_authenticate=auth)


@bp.route('/', methods=['GET', 'HEAD', 'POST'])
@bp.route('/<path:filepath>', methods=['GET', 'HEAD', 'POST'])
def handle_request(filepath=''):
    """Handle an HTTP request (HEAD, GET, POST).
    """
    return action_handler._handle_action(request.action)


@bp.after_request
def handle_after_request(response):
    # forbid a privileged page to be framed
    if runtime['config']['app']['content_security_policy'] == 'strict':
        if 'Content-Security-Policy' not in response.headers:
            response.headers.set('Content-Security-Policy', "frame-ancestors 'none';")
            response.headers.set('X-Frame-Options', 'deny')

    return response


@bp.errorhandler(HTTPException)
def handle_error(exc):
    """Handle formatted error if requested by client.
    """
    if request.format == 'json':
        response = exc.get_response()
        response.data = json.dumps({
            'error': {
                'status': exc.code,
                'message': exc.description,
                },
            })
        response.content_type = "application/json"
        return response

    return exc


def make_app(root=".", config=None):
    # use the same realpath during the APP lifetime
    root = os.path.realpath(root)

    if not config:
        config = Config()
        config.load(root)

    # runtime variables
    _runtime = {}
    _runtime['config'] = config
    _runtime['root'] = os.path.normpath(os.path.join(root, config['app']['root']))
    _runtime['name'] = config['app']['name']

    # add path for themes
    _runtime['themes'] = [
        os.path.join(root, WSB_DIR, 'themes', config['app']['theme']),
        os.path.join(os.path.dirname(__file__), 'themes', config['app']['theme']),
        ]
    _runtime['statics'] = [os.path.join(t, 'static') for t in _runtime['themes']]
    _runtime['templates'] = [os.path.join(t, 'templates') for t in _runtime['themes']]

    _runtime['tokens'] = os.path.join(root, WSB_DIR, 'server', 'tokens')
    _runtime['locks'] = os.path.join(root, WSB_DIR, 'server', 'locks')

    # init token_handler
    _runtime['token_handler'] = util.TokenHandler(_runtime['tokens'])

    # main app instance
    app = flask.Flask(__name__, instance_path=_runtime['root'])
    app.register_blueprint(bp)
    app.request_class = Request
    app.config['WEBSCRAPBOOK_RUNTIME'] = _runtime

    xheaders = {
            'x_for': config['app']['allowed_x_for'],
            'x_proto': config['app']['allowed_x_proto'],
            'x_host': config['app']['allowed_x_host'],
            'x_port': config['app']['allowed_x_port'],
            'x_prefix': config['app']['allowed_x_prefix'],
            }

    if any(v for v in xheaders.values()):
        app.wsgi_app = ProxyFix(app.wsgi_app, **xheaders)

    app.jinja_loader = jinja2.FileSystemLoader(_runtime['templates'])
    app.jinja_env.globals.update({
            'os': os,
            'time': time,
            'get_breadcrumbs': util.get_breadcrumbs,
            'format_filesize': util.format_filesize,
            'quote_path': quote_path,
            'static_url': static_url,
            })

    return app
