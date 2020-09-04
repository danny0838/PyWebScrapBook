#!/usr/bin/env python3
"""The WGSI application.
"""
import sys
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
from urllib.parse import urlsplit, urlunsplit, urljoin, quote, unquote, parse_qs
from pathlib import Path
from zlib import adler32
from contextlib import contextmanager
from secrets import token_bytes

# dependency
import flask
from flask import request, Response, redirect, abort, render_template
from flask import current_app, session
from werkzeug.local import LocalProxy
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.datastructures import WWWAuthenticate
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
from ._compat.time import time_ns
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
        return http_error(404)
    response = flask.send_file(filename, conditional=True, mimetype=mimetype)
    response.headers.set('Accept-Ranges', 'bytes')
    response.headers.set('Cache-Control', 'no-cache')
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
            return http_error(404)
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
            for data in gen:
                yield "data: " + data + "\n\n"

            yield "event: complete" + "\n"
            yield "data: " + "\n\n"

        body = wrapper(body)

    else:
        return http_error(400, f'Output format "{format}" is not supported.')

    return Response(body, status, headers, mimetype=mimetype)


def http_error(status=500, description=None, format=None, *args, **kwargs):
    """Handle formatted error response.
    """
    # expect body to be a JSON-serializable object
    if format == 'json':
        mimetype = 'application/json'

        try:
            abort(status, description=description, *args, **kwargs)
        except Exception as e:
            headers = e.get_headers()
            description = e.description

        body = {
            'error': {
                'status': status,
                'message': description,
                },
            }

        body = json.dumps(body, ensure_ascii=False)

        return Response(body, status, headers=headers, mimetype=mimetype)

    else:
        return abort(status, description=description, *args, **kwargs)


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

    Returns:
        a tuple (id, permission), where id is None if user is anonymous.
    """
    auth = auth_info or {}
    user = auth.get('username') or ''
    pw = auth.get('password') or ''

    for id, entry in auth_config.items():
        entry_user = entry.get('user', '')
        entry_pw = entry.get('pw', '')
        entry_pw_salt = entry.get('pw_salt', '')
        entry_pw_type = entry.get('pw_type', '')
        entry_permission = entry.get('permission', 'all')
        if (user == entry_user and
                util.encrypt(pw, entry_pw_salt, entry_pw_type) == entry_pw):
            return id if user or pw else None, entry_permission

    return None, ''


def verify_authorization(perm, action):
    """Check if authorized or not.
    """
    if perm == 'all':
        return True

    elif perm == 'read':
        if action in {'token', 'lock', 'unlock', 'mkdir', 'mkzip', 'save', 'delete', 'move', 'copy'}:
            return False
        else:
            return True

    elif perm == 'view':
        if action in {'view', 'info', 'source', 'static'}:
            return True
        else:
            return False

    else:
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

    elif format == 'json':
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
        elif len(pages) > 0:
            subpath = pages[0].indexfilename
        else:
            # no valid index file found
            return list_maff_pages([])

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
            return http_error(403, format=request.format)

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
                return http_error(405, format=format, valid_methods=['POST'])

            # validate and revoke token
            token = request.values.get('token') or ''

            if not runtime['token_handler'].validate(token):
                return http_error(400, 'Invalid access token.', format=format)

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
            format = request.format

            # verify name
            name = request.values.get('name')
            if name is None:
                return http_error(400, "Lock name is not specified.", format=format)

            # validate targetpath
            targetpath = os.path.join(runtime['locks'], name)
            if not targetpath.startswith(os.path.join(runtime['locks'], '')):
                return http_error(400, f'Invalid lock name "{name}".', format=format)

            return func(self, name=name, targetpath=targetpath, *args, **kwargs)

        return wrapper

    def _handle_writing(func):
        """A decorator function that helps handling a writing action.
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            format = request.format

            if os.path.abspath(request.localpath) == runtime['root']:
                return http_error(403, "Unable to operate the root directory.", format=format)

            return func(self, *args, **kwargs)

        return wrapper

    def _handle_renaming(func):
        """A decorator function that helps handling a move/copy action.
        """
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            format = request.format
            localpaths = request.localpaths

            if len(localpaths) > 1:
                with open_archive_path(localpaths) as zip:
                    try:
                        zip.getinfo(localpaths[-1])
                    except KeyError:
                        if not util.zip_hasdir(zip, localpaths[-1] + '/'):
                            return http_error(404, "Source does not exist.", format=format)
            else:
                if not os.path.lexists(localpaths[0]):
                    return http_error(404, "Source does not exist.", format=format)

            target = request.values.get('target')

            if target is None:
                return http_error(400, 'Target is not specified.', format=format)

            targetpaths = get_archive_path(target)
            targetpaths[0] = os.path.normpath(os.path.join(runtime['root'], targetpaths[0].lstrip('/')))

            if not targetpaths[0].startswith(os.path.join(runtime['root'], '')):
                return http_error(403, "Unable to operate beyond the root directory.", format=format)

            if len(targetpaths) > 1:
                with open_archive_path(targetpaths) as zip:
                    try:
                        zip.getinfo(targetpaths[-1])
                    except KeyError:
                        if util.zip_hasdir(zip, targetpaths[-1] + '/'):
                            return http_error(400, 'Found something at target.', format=format)
                    else:
                        return http_error(400, 'Found something at target.', format=format)
            else:
                if os.path.lexists(targetpaths[0]):
                    return http_error(400, 'Found something at target.', format=format)

            return func(self, sourcepaths=localpaths, targetpaths=targetpaths, *args, **kwargs)

        return wrapper

    def unknown(self, *args, **kwargs):
        """Default handler for an undefined action"""
        format = request.format
        return http_error(400, "Action not supported.", format=format)

    def view(self, *args, **kwargs):
        """Show the content of a file or list a directory.

        If formatted, show information of the file or directory.
        """
        format = request.format

        # info for other output formats
        if format:
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
                            return http_error(404)
                    return http_error(404)
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
                return http_error(404)

        # don't include charset
        m, p = parse_options_header(response.headers.get('Content-Type'))
        try:
            del p['charset']
        except KeyError:
            pass
        response.headers.set('Content-Type', dump_options_header(m, p))

        return response

    def source(self, *args, **kwargs):
        """Show file content as plain text."""
        format = request.format

        if format:
            return http_error(400, "Action not supported.", format=format)

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

    def info(self, *args, **kwargs):
        """Show information of a path."""
        format = request.format

        if not format:
            return http_error(400, "Action not supported.", format=format)

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

    def list(self, *args, **kwargs):
        """List entries in a directory."""
        format = request.format

        if not format:
            return http_error(400, "Action not supported.", format=format)

        recursive = request.values.get('recursive', type=bool)
        localpaths = request.localpaths

        if len(localpaths) > 1:
            try:
                return handle_directory_listing(localpaths, redirect_slash=False, recursive=recursive, format=format)
            except util.ZipDirNotFoundError:
                return http_error(404, "Directory does not exist.", format=format)

        if os.path.isdir(localpaths[0]):
            return handle_directory_listing(localpaths, redirect_slash=False, recursive=recursive, format=format)

        return http_error(404, "Directory does not exist.", format=format)

    def static(self, *args, **kwargs):
        """Show a static file of the current theme."""
        format = request.format

        if format:
            return http_error(400, "Action not supported.", format=format)

        filepath = request.path.strip('/')
        for i in runtime['statics']:
            f = os.path.join(i, filepath)
            if os.path.isfile(f):
                return static_file(f)
        else:
            return http_error(404)

    def edit(self, *args, **kwargs):
        """Simple text editor for a file."""
        format = request.format

        if format:
            return http_error(400, "Action not supported.", format=format)

        localpaths = request.localpaths
        localpath = localpaths[0]

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            return http_error(400, "Found a non-file here.", format=format)

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zip:
                try:
                    info = zip.getinfo(localpaths[-1])
                except:
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

    def editx(self, *args, **kwargs):
        """HTML editor for a file."""
        format = request.format

        if format:
            return http_error(400, "Action not supported.", format=format)

        localpaths = request.localpaths
        localpath = localpaths[0]

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            return http_error(400, "Found a non-file here.", format=format)

        if not request.localmimetype in ("text/html", "application/xhtml+xml"):
            return http_error(400, "This is not an HTML file.", format=format)

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zip:
                try:
                    info = zip.getinfo(localpaths[-1])
                except:
                    return http_error(404, format=format)
        else:
            if not os.path.lexists(localpath):
                return http_error(404, format=format)

        body = render_template('editx.html',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=request.script_root,
                path=request.path,
                )

        return http_response(body, format=format)

    def exec(self, *args, **kwargs):
        """Launch a file or directory."""
        format = request.format

        if not is_local_access():
            return http_error(400, "Command can only run on local device.", format=format)

        localpath = request.localpath

        if not os.path.lexists(localpath):
            return http_error(404, "File does not exist.", format=format)

        util.launch(localpath)

        if format:
            return http_response('Command run successfully.', format=format)

        return http_response(status=204)

    def browse(self, *args, **kwargs):
        """Open a file or directory in the file browser."""
        format = request.format

        if not is_local_access():
            return http_error(400, "Command can only run on local device.", format=format)

        localpath = request.localpath

        if not os.path.lexists(localpath):
            return http_error(404, "File does not exist.", format=format)

        util.view_in_explorer(localpath)

        if format:
            return http_response('Command run successfully.', format=format)

        return http_response(status=204)

    def config(self, *args, **kwargs):
        """Show server config."""
        format = request.format

        if not format:
            return http_error(400, "Action not supported.", format=format)

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

    def token(self, *args, **kwargs):
        """Acquire a token and return its name."""
        format = request.format
        return http_response(runtime['token_handler'].acquire(), format=format)

    @_handle_advanced
    @_handle_lock
    def lock(self, name, targetpath, *args, **kwargs):
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

        while True:
            try:
                os.makedirs(targetpath)
            except FileExistsError:
                t = time.time()

                if t >= check_expire or not os.path.isdir(targetpath):
                    return http_error(500, f'Unable to acquire lock "{name}".', format=format)

                try:
                    lock_expire = os.stat(targetpath).st_mtime + check_stale
                except FileNotFoundError:
                    # Lock removed by another process during the short interval.
                    # Try acquire again.
                    continue

                if t >= lock_expire:
                    # Lock expired. Touch rather than remove and make for atomicity.
                    try:
                        Path(targetpath).touch()
                    except:
                        traceback.print_exc()
                        return http_error(500, f'Unable to regenerate stale lock "{name}".', format=format)
                    else:
                        break

                time.sleep(check_delta)
            except:
                traceback.print_exc()
                return http_error(500, f'Unable to create lock "{name}".', format=format)
            else:
                break

    @_handle_advanced
    @_handle_lock
    def unlock(self, name, targetpath, *args, **kwargs):
        """Release a lock for the given name."""
        format = request.format

        try:
            os.rmdir(targetpath)
        except FileNotFoundError:
            pass
        except:
            traceback.print_exc()
            return http_error(500, f'Unable to remove lock "{name}".', format=format)

    @_handle_advanced
    @_handle_writing
    def mkdir(self, *args, **kwargs):
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
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this ZIP file.", format=format)

        else:
            localpath = localpaths[0]

            if os.path.lexists(localpath) and not os.path.isdir(localpath):
                return http_error(400, "Found a non-directory here.", format=format)

            try:
                os.makedirs(localpath, exist_ok=True)
            except OSError:
                traceback.print_exc()
                return http_error(500, "Unable to create a directory here.", format=format)


    @_handle_advanced
    @_handle_writing
    def mkzip(self, *args, **kwargs):
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
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this ZIP file.", format=format)

        else:
            localpath = localpaths[0]

            if os.path.lexists(localpath) and not os.path.isfile(localpath):
                return http_error(400, "Found a non-file here.", format=format)

            try:
                os.makedirs(os.path.dirname(localpath), exist_ok=True)
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this path.", format=format)

            try:
                with zipfile.ZipFile(localpath, 'w') as f:
                    pass
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this file.", format=format)


    @_handle_advanced
    @_handle_writing
    def save(self, *args, **kwargs):
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
                    except:
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
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this ZIP file.", format=format)

        else:
            localpath = localpaths[0]

            if os.path.lexists(localpath) and not os.path.isfile(localpath):
                return http_error(400, "Found a non-file here.", format=format)

            try:
                os.makedirs(os.path.dirname(localpath), exist_ok=True)
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this path.", format=format)

            try:
                file = request.files.get('upload')
                if file is not None:
                    file.save(localpath)
                else:
                    bytes = request.values.get('text', '').encode('ISO-8859-1')
                    with open(localpath, 'wb') as f:
                        f.write(bytes)
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this file.", format=format)


    @_handle_advanced
    @_handle_writing
    def delete(self, *args, **kwargs):
        """Delete a file or directory."""
        format = request.format
        localpaths = request.localpaths

        if len(localpaths) > 1:
            try:
                with open_archive_path(localpaths, 'w', [localpaths[-1]]) as zip:
                    pass
            except KeyError:
                # fail since nothing is deleted
                return http_error(404, "Entry does not exist in this ZIP file.", format=format)
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this ZIP file.", format=format)

        else:
            localpath = localpaths[0]

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
                    try:
                        # try rmdir for a possible windows directory junction,
                        # which is not detected by os.path.islink
                        os.rmdir(localpath)
                    except OSError:
                        # directory not empty
                        shutil.rmtree(localpath)
                except:
                    traceback.print_exc()
                    return http_error(500, "Unable to delete this directory.", format=format)

    @_handle_advanced
    @_handle_writing
    @_handle_renaming
    def move(self, sourcepaths, targetpaths, *args, **kwargs):
        """Move a file or directory."""
        format = request.format

        try:
            if len(sourcepaths) == 1:
                if len(targetpaths) == 1:
                    try:
                        os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                    except:
                        traceback.print_exc()
                        return http_error(500, "Unable to copy to this path.", format=format)

                    shutil.move(sourcepaths[0], targetpaths[0])

                else:
                    # Moving a file into a zip is like moving across disk,
                    # which makes little sense. Additionally, moving a
                    # symlink/junction should rename the entry and cannot be
                    # implemented as copying-deleting. Forbid such operation to
                    # prevent a confusion.
                    return http_error(400, "Unable to move across a zip.", format=format)

            elif len(sourcepaths) > 1:
                if len(targetpaths) == 1:
                    # Moving from zip to disk is like moving across disk, which
                    # makes little sense.
                    return http_error(400, "Unable to move across a zip.", format=format)

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

        except:
            traceback.print_exc()
            return http_error(500, 'Unable to move to the target.', format=format)

    @_handle_advanced
    @_handle_writing
    @_handle_renaming
    def copy(self, sourcepaths, targetpaths, *args, **kwargs):
        """Copy a file or directory."""
        format = request.format

        # Copying a symlink/junction means copying the real file/directory.
        # It makes no sense if the symlink/junction is broken.
        if not os.path.exists(sourcepaths[0]):
            return http_error(404, "Source does not exist.", format=format)

        try:
            if len(sourcepaths) == 1:
                if len(targetpaths) == 1:
                    try:
                        os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                    except:
                        traceback.print_exc()
                        return http_error(500, "Unable to copy to this path.", format=format)

                    try:
                        shutil.copytree(sourcepaths[0], targetpaths[0])
                    except NotADirectoryError:
                        shutil.copy2(sourcepaths[0], targetpaths[0])

                else:
                    if os.path.isdir(sourcepaths[0]):
                        with open_archive_path(targetpaths, 'w') as zip:
                            base = sourcepaths[0]
                            zip.writestr(zipfile.ZipInfo(
                                targetpaths[-1] + '/',
                                time.localtime(os.stat(sourcepaths[0]).st_mtime)[:-3]
                                ), '')
                            for root, dirs, files in os.walk(base):
                                for dir in dirs:
                                    dir = os.path.join(root, dir)
                                    subpath = os.path.relpath(dir, base).replace('\\', '/')
                                    zip.writestr(zipfile.ZipInfo(
                                        targetpaths[-1] + '/' + subpath + '/',
                                        time.localtime(os.stat(dir).st_mtime)[:-3]
                                        ), '')
                                for file in files:
                                    file = os.path.join(root, file)
                                    subpath = os.path.relpath(file, base).replace('\\', '/')
                                    zip.write(file, targetpaths[-1] + '/' + subpath)
                    elif os.path.isfile(sourcepaths[0]):
                        with open_archive_path(targetpaths, 'w') as zip:
                            zip.write(sourcepaths[0], targetpaths[-1])

            elif len(sourcepaths) > 1:
                if len(targetpaths) == 1:
                    try:
                        os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                    except:
                        traceback.print_exc()
                        return http_error(500, "Unable to copy to this path.", format=format)

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
                        except:
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

        except:
            traceback.print_exc()
            return http_error(500, 'Unable to copy to the target.', format=format)

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

    # if request authorization is provided, use it
    # otherwise try to read from session
    auth = request.authorization
    if auth:
        id, perm = get_permission(auth, auth_config)
    else:
        sid = session.get('auth_id')
        try:
            assert session.get('auth_pw') == runtime['config']['auth'][sid].get('pw', '')
            perm = runtime['config']['auth'][sid].get('permission', 'all')
        except (KeyError, AssertionError):
            id, perm = get_permission(auth, auth_config)

            # clear if session becomes invalid and no new log in
            if sid and not id:
                session.clear()
        else:
            id = sid

    # store auth id in session
    if id:
        session['auth_id'] = id
        session['auth_pw'] = runtime['config']['auth'][id].get('pw', '')
        session.permanent = True

    if not verify_authorization(perm, request.action):
        auth = WWWAuthenticate()
        auth.set_basic('Authentication required.')
        return http_error(401, 'You are not authorized.', format=request.format, www_authenticate=auth)


@bp.route('/', methods=['GET', 'HEAD', 'POST'])
@bp.route('/<path:filepath>', methods=['GET', 'HEAD', 'POST'])
def handle_request(filepath=''):
    """Handle an HTTP request (HEAD, GET, POST).
    """
    return action_handler._handle_action(request.action)


def make_app(root=".", config=None):
    if not config:
        config = Config()
        config.load(root)

    # runtime variables
    _runtime = {}
    _runtime['config'] = config
    _runtime['root'] = os.path.abspath(os.path.join(root, config['app']['root']))
    _runtime['name'] = config['app']['name']

    # add path for themes
    _runtime['themes'] = [
        os.path.join(_runtime['root'], WSB_DIR, 'themes', config['app']['theme']),
        os.path.join(os.path.dirname(__file__), 'themes', config['app']['theme']),
        ]
    _runtime['statics'] = [os.path.join(t, 'static') for t in _runtime['themes']]
    _runtime['templates'] = [os.path.join(t, 'templates') for t in _runtime['themes']]

    _runtime['tokens'] = os.path.join(_runtime['root'], WSB_DIR, 'server', 'tokens')
    _runtime['locks'] = os.path.join(_runtime['root'], WSB_DIR, 'server', 'locks')
    _runtime['sessions'] = os.path.join(_runtime['root'], WSB_DIR, 'server', 'sessions')

    # init token_handler
    _runtime['token_handler'] = util.TokenHandler(_runtime['tokens'])

    # load or generate a session key if auth is defined
    try:
        auth_sections = _runtime['config']['auth']
    except KeyError:
        session_key = None
        pass
    else:
        os.makedirs(os.path.dirname(_runtime['sessions']), exist_ok=True)
        try:
            with open(_runtime['sessions'], 'rb') as f:
                session_key = f.read()
            assert len(session_key) >= 32
        except (FileNotFoundError, AssertionError):
            session_key = token_bytes(128)
            with open(_runtime['sessions'], 'wb') as f:
                f.write(session_key)

    # main app instance
    app = flask.Flask(__name__, instance_path=_runtime['root'])
    app.register_blueprint(bp)
    app.request_class = Request
    app.config['WEBSCRAPBOOK_RUNTIME'] = _runtime
    app.config['SECRET_KEY'] = session_key
    app.config['SESSION_COOKIE_NAME'] = 'wsbsession'
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

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
