#!/usr/bin/env python3
"""The WGSI application.
"""
import sys
import os
import traceback
import shutil
import mimetypes
import re
import zipfile
import time
import json
import functools
from urllib.parse import urlsplit, urlunsplit, urljoin, quote, unquote, parse_qs
from pathlib import Path
from zlib import adler32

# dependency
import flask
from flask import request, Response, redirect, abort, render_template
from flask import current_app
from werkzeug.local import LocalProxy
from werkzeug.middleware.proxy_fix import ProxyFix
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
        return http_error(400, 'Output format "{}" is not supported.'.format(format))

    return Response(body, status, headers, mimetype=mimetype)


def http_error(status=500, body=None, headers=None, format=None):
    """Handle formatted error response.
    """
    # expect body to be a JSON-serializable object
    if format == 'json':
        mimetype = 'application/json'

        body = {
            'error': {
                'status': status,
                'message': body,
                },
            }

        body = json.dumps(body, ensure_ascii=False)
    else:
        mimetype = None

    if body:
        return Response(body, status, headers, mimetype=mimetype)
    else:
        # @TODO: abort does not support headers and mimetype
        return abort(status)


def get_archive_path(filepath):
    """Parse archive file path and the sub-archive path.

    - Priority:
      entry.zip!/entry1.zip!/ = entry.zip!/entry1.zip! >
      entry.zip!/entry1.zip >
      entry.zip!/ = entry.zip! >
      entry.zip

    Returns:
        a tuple (archivefile, subarchivepath).
    """
    for m in reversed(list(re.finditer(r'!/', filepath, flags=re.I))):
        archivefile = os.path.normpath(os.path.join(runtime['root'], filepath[:m.start(0)].strip('/')))
        if os.path.lexists(archivefile + '!'):
            break

        if zipfile.is_zipfile(archivefile):
            subarchivepath = filepath[m.end(0):].rstrip('/')
            return (archivefile, subarchivepath)

    return (None, None)


def is_local_access():
    """Determine if the client is in same device.
    """
    server_host = request.host.partition(':')[0]
    client_host = request.remote_addr
    return util.is_localhost(server_host) or util.is_localhost(client_host) or server_host == client_host


def get_permission(auth):
    """Get effective permission of the current logged in user.
    """
    try:
        auth_sections = runtime['config']['auth']
    except KeyError:
        return 'all'

    auth = auth or {}
    user = auth.get('username') or ''
    pw = auth.get('password') or ''

    for _, entry in auth_sections.items():
        entry_user = entry.get('user', '')
        entry_pw = entry.get('pw', '')
        entry_pw_salt = entry.get('pw_salt', '')
        entry_pw_type = entry.get('pw_type', '')
        entry_permission = entry.get('permission', 'all')
        if (user == entry_user and
                util.encrypt(pw, entry_pw_salt, entry_pw_type) == entry_pw):
            return entry_permission

    return ''


def verify_authorization(perm, action):
    """Check if authorized or not.
    """
    if perm == 'all':
        return True

    elif perm == 'read':
        if action in {'token', 'lock', 'unlock', 'mkdir', 'save', 'delete', 'move', 'copy'}:
            return False
        else:
            return True

    elif perm == 'view':
        if action in {'view', 'source', 'static'}:
            return True
        else:
            return False

    else:
        return False


def handle_directory_listing(localpath, recursive=False, format=None):
    """List contents in a directory.
    """
    # ensure directory has trailing '/'
    if not request.path.endswith('/'):
        parts = urlsplit(request.url)
        new_url = urlunsplit((
            parts.scheme,
            parts.netloc,
            quote_path(unquote(parts.path)) + '/',
            parts.query,
            parts.fragment,
            ))
        return redirect(new_url)

    if not os.path.exists(localpath):
        return http_error(404, "Directory does not exist.", format=format)

    if not os.access(localpath, os.R_OK):
        return http_error(403, "You do not have permission to view this directory.", format=format)

    # output index
    subentries = util.listdir(localpath, recursive)

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

        return http_response(gen(), format=format)

    elif format == 'json':
        data = []
        for entry in subentries:
            data.append({
                    'name': entry.name,
                    'type': entry.type,
                    'size': entry.size,
                    'last_modified': entry.last_modified,
                    })
        return http_response(data, format=format)

    # headers
    headers = {}
    headers['Cache-Control'] = 'no-store'
    stats = os.stat(localpath)
    headers['Last-Modified'] = http_date(stats.st_mtime)

    body = render_template('index.html',
            sitename=runtime['name'],
            is_local=is_local_access(),
            base=request.script_root,
            path=request.path,
            subarchivepath=None,
            subentries=subentries,
            )

    return http_response(body, format=format, headers=headers)


def handle_zip_directory_listing(zip, archivefile, subarchivepath, recursive=False, format=None):
    """List contents in a directory.
    """
    # ensure directory has trailing '/'
    if not request.path.endswith('/'):
        parts = urlsplit(request.url)
        new_url = urlunsplit((
            parts.scheme,
            parts.netloc,
            quote_path(unquote(parts.path)) + '/',
            parts.query,
            parts.fragment,
            ))
        return redirect(new_url)

    stats = os.lstat(archivefile)
    last_modified = http_date(stats.st_mtime)
    etag = "%s-%s-%s" % (
        stats.st_mtime,
        stats.st_size,
        adler32(archivefile.encode("utf-8")) & 0xFFFFFFFF,
        )

    if not is_resource_modified(request.environ, etag=etag, last_modified=last_modified):
        return http_response(status=304, format=format)

    headers = {
        'Cache-Control': 'no-cache',
        'Last-Modified': last_modified,
        'ETag': etag,
        }

    subentries = util.zip_listdir(zip, subarchivepath, recursive)

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

    try:
        body = render_template('index.html',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=request.script_root,
                path=request.path,
                subarchivepath=subarchivepath,
                subentries=subentries,
                )
        return http_response(body, headers=headers)
    except util.ZipDirNotFoundError:
        return http_error(404, "File does not exist.")


def handle_subarchive_path(archivefile, subarchivepath, mimetype=None, list_directory=True, format=None):
    """Show content of a path in a zip file.
    """
    if not os.access(archivefile, os.R_OK):
        return http_error(403, "You do not have permission to access this file.", format=format)

    try:
        zip = zipfile.ZipFile(archivefile)
    except:
        return http_error(500, "Unable to open the ZIP file.", format=format)

    if format:
        info = util.zip_file_info(zip, subarchivepath)
        data = {
            'name': info.name,
            'type': info.type,
            'size': info.size,
            'last_modified': info.last_modified,
            'mime': mimetype,
            }
        return http_response(data, format=format)

    try:
        # KeyError is raised if subarchivepath does not exist
        info = zip.getinfo(subarchivepath)
    except KeyError:
        # subarchivepath does not exist
        # possibility a missing directory entry?
        if not list_directory:
            return http_error(404)

        return handle_zip_directory_listing(zip, archivefile, subarchivepath)
    else:
        fh = zip.open(info, 'r')

        lm = info.date_time
        lm = int(time.mktime((lm[0], lm[1], lm[2], lm[3], lm[4], lm[5], 0, 0, -1)))
        last_modified = http_date(lm)

        etag = "%s-%s-%s" % (
            lm,
            info.file_size,
            adler32(archivefile.encode("utf-8")) & 0xFFFFFFFF,
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
    finally:
        zip.close()


def handle_archive_viewing(localpath, mimetype):
    """Handle direct visit of HTZ/MAFF file.
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

    parts = urlsplit(request.url)
    new_url = urlunsplit((
        parts.scheme,
        parts.netloc,
        quote_path(unquote(parts.path)) + '!/' + quote_path(subpath),
        parts.query,
        parts.fragment,
        ))
    return redirect(new_url)


def handle_markdown_output(filename):
    """Output processed markdown.
    """
    stats = os.stat(filename)
    last_modified = http_date(stats.st_mtime)
    etag = "%s-%s-%s" % (
        stats.st_mtime,
        stats.st_size,
        adler32(filename.encode("utf-8")) & 0xFFFFFFFF,
        )

    headers = {
        'Cache-Control': 'no-cache',
        }

    if not is_resource_modified(request.environ, etag=etag, last_modified=last_modified):
        return http_response(status=304, headers=headers)

    headers.update({
        'Last-Modified': last_modified,
        'ETag': etag,
        })

    # output processed content
    with open(filename, 'r', encoding='UTF-8') as f:
        body = f.read()
    
    body = render_template('markdown.html',
            sitename=runtime['name'],
            is_local=is_local_access(),
            base=request.script_root,
            path=request.path,
            content=commonmark.commonmark(body),
            )

    return http_response(body, headers=headers)


class Request(flask.Request):
    """Subclassed Request object for more useful properties.
    """
    @cached_property
    def localpath(self):
        """Corresponding filesystem path of the requested path."""
        return os.path.normpath(os.path.join(runtime['root'], self.path.strip('/')))

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
    def _handle_action(self):
        handler = getattr(self, request.action, None) or self.unknown
        return handler(
            filepath=request.path.lstrip('/'),
            localpath=request.localpath,
            mimetype=request.localmimetype,
            query=request.values,
            format=request.format,
            )

    def _handle_advanced(func):
        """A decorator function that helps handling an advanced command.

        - Verify POST method.
        - Verify access token.
        - Provide a default return value.
        """
        @functools.wraps(func)
        def wrapper(self,
                localpath,
                query=None,
                format=None,
                *args, **kwargs):
            # require POST method
            if request.method != 'POST':
                headers = {
                    'Allow': 'POST',
                    }
                return http_error(405, 'Method "{}" not allowed.'.format(request.method), format=format, headers=headers)

            # validate and revoke token
            token = query.get('token') or ''

            if not runtime['token_handler'].validate(token):
                return http_error(400, 'Invalid access token.', format=format)

            runtime['token_handler'].delete(token)

            rv = func(
                self=self,
                localpath=localpath,
                query=query,
                format=format,
                *args, **kwargs)

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
        def wrapper(self, query=None, format=None, *args, **kwargs):
            # verify name
            name = query.get('name')
            if name is None:
                return http_error(400, "Lock name is not specified.", format=format)

            # validate targetpath
            targetpath = os.path.join(runtime['locks'], name)
            if not targetpath.startswith(os.path.join(runtime['locks'], '')):
                return http_error(400, 'Invalid lock name "{}".'.format(name), format=format)

            return func(
                self=self,
                name=name,
                targetpath=targetpath,
                query=query,
                format=format,
                *args, **kwargs)

        return wrapper

    def _handle_writing(func):
        """A decorator function that helps handling a writing action.
        """
        @functools.wraps(func)
        def wrapper(self, localpath, format=None, *args, **kwargs):
            if os.path.abspath(localpath) == runtime['root']:
                return http_error(403, "Unable to operate the root directory.", format=format)

            return func(
                self=self,
                localpath=localpath,
                format=format,
                *args, **kwargs)

        return wrapper

    def _handle_renaming(func):
        """A decorator function that helps handling a move/copy action.
        """
        @functools.wraps(func)
        def wrapper(self,
                localpath,
                query=None,
                format=None,
                *args, **kwargs):
            archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

            if archivefile:
                return http_error(400, "File is inside an archive file.", format=format)

            if not os.path.lexists(localpath):
                return http_error(404, "File does not exist.", format=format)

            target = query.get('target')

            if target is None:
                return http_error(400, 'Target is not specified.', format=format)

            targetpath = os.path.normpath(os.path.join(runtime['root'], target.strip('/')))

            if not targetpath.startswith(os.path.join(runtime['root'], '')):
                return http_error(403, "Unable to operate beyond the root directory.", format=format)

            if os.path.lexists(targetpath):
                return http_error(400, 'Found something at target "{}".'.format(target), format=format)

            ta, tsa = get_archive_path(target)
            if ta:
                return http_error(400, "Target is inside an archive file.", format=format)

            return func(
                self=self,
                localpath=localpath,
                targetpath=targetpath,
                format=format,
                *args, **kwargs)

        return wrapper

    def unknown(self, format=None, *args, **kwargs):
        """Default handler for an undefined action"""
        return http_error(400, "Action not supported.", format=format)

    def view(self,
            localpath,
            mimetype=None,
            format=None,
            *args, **kwargs):
        """Show the content of a file or list a directory.

        If formatted, show information of the file or directory.
        """
        archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

        # show file information for other output formats
        if format:
            if archivefile:
                return handle_subarchive_path(os.path.realpath(archivefile), subarchivepath, mimetype, format=format)

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
            return handle_directory_listing(localpath)

        # handle file
        elif os.path.isfile(localpath):
            # view archive file
            if mimetype in ("application/html+zip", "application/x-maff"):
                return handle_archive_viewing(localpath, mimetype)

            # view markdown
            if mimetype == "text/markdown":
                return handle_markdown_output(localpath)

            # convert meta refresh to 302 redirect
            if request.localrealpath.lower().endswith('.htm'):
                target = util.parse_meta_refresh(localpath).target

                if target is not None:
                    # Keep several chars as javascript encodeURI do,
                    # plus "%" as target may have already been escaped.
                    new_url = urljoin(request.url, quote(target, ";,/?:@&=+$-_.!~*'()#%"))
                    return redirect(new_url)

            # show static file for other cases
            response = static_file(localpath, mimetype=mimetype)

        # handle sub-archive path
        elif archivefile:
            response = handle_subarchive_path(os.path.realpath(archivefile), subarchivepath, mimetype)

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

    def source(self,
            localpath,
            mimetype=None,
            query=None,
            format=None,
            *args, **kwargs):
        """Show file content as plain text."""
        if format:
            return http_error(400, "Action not supported.", format=format)

        archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

        if archivefile:
            response = handle_subarchive_path(os.path.realpath(archivefile), subarchivepath, mimetype, list_directory=False)
        else:
            response = static_file(localpath, mimetype=mimetype)

        # show as inline plain text
        # @TODO: Chromium (80) seems to ignore header mimetype for certain types
        #        like image and zip
        encoding = query.get('e', 'utf-8')
        encoding = query.get('encoding', default=encoding)
        response.headers.set('Content-Type', 'text/plain; charset=' + quote(encoding))
        response.headers.set('Content-Disposition', 'inline')

        return response

    def list(self,
            localpath,
            query=None,
            format=None,
            *args, **kwargs):
        """List entries in a directory."""
        if not format:
            return http_error(400, "Action not supported.", format=format)

        recursive = query.get('recursive', type=bool)
        archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

        if archivefile:
            return handle_zip_directory_listing(os.path.realpath(archivefile), os.path.realpath(archivefile), subarchivepath, recursive=recursive, format=format)

        if os.path.isdir(localpath):
            return handle_directory_listing(localpath, recursive=recursive, format=format)

        return http_error(404, "Directory does not exist.", format=format)

    def static(self,
            filepath,
            format=None,
            *args, **kwargs):
        """Show a static file of the current theme."""
        if format:
            return http_error(400, "Action not supported.", format=format)

        for i in runtime['statics']:
            f = os.path.join(i, filepath)
            if os.path.isfile(f):
                return static_file(f)
        else:
            return http_error(404)

    def edit(self,
            localpath,
            query=None,
            format=None,
            *args, **kwargs):
        """Simple text editor for a file."""
        if format:
            return http_error(400, "Action not supported.", format=format)

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            return http_error(400, "Found a non-file here.", format=format)

        archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

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
            except FileNotFoundError:
                body = b''

        encoding = query.get('e')
        encoding = query.get('encoding', default=encoding)

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

    def editx(self,
            localpath,
            mimetype=None,
            format=None,
            *args, **kwargs):
        """HTML editor for a file."""
        if format:
            return http_error(400, "Action not supported.", format=format)

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            return http_error(400, "Found a non-file here.", format=format)

        if not mimetype in ("text/html", "application/xhtml+xml"):
            return http_error(400, "This is not an HTML file.", format=format)

        archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

        if archivefile:
            with zipfile.ZipFile(archivefile, 'r') as zip:
                try:
                    info = zip.getinfo(subarchivepath)
                except:
                    return http_error(404, "File does not exist.", format=format)
        else:
            if not os.path.lexists(localpath):
                return http_error(404, "File does not exist.", format=format)

        body = render_template('editx.html',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=request.script_root,
                path=request.path,
                )

        return http_response(body, format=format)

    def exec(self, localpath, format=None, *args, **kwargs):
        """Launch a file or directory."""
        if not is_local_access():
            return http_error(400, "Command can only run on local device.", format=format)

        if not os.path.lexists(localpath):
            return http_error(404, "File does not exist.", format=format)

        util.launch(localpath)

        if format:
            return http_response('Command run successfully.', format=format)

        return http_response(status=204)

    def browse(self, localpath, format=None, *args, **kwargs):
        """Open a file or directory in the file browser."""
        if not is_local_access():
            return http_error(400, "Command can only run on local device.", format=format)

        if not os.path.lexists(localpath):
            return http_error(404, "File does not exist.", format=format)

        util.view_in_explorer(localpath)

        if format:
            return http_response('Command run successfully.', format=format)

        return http_response(status=204)

    def config(self, format=None, *args, **kwargs):
        """Show server config."""
        if not format:
            return http_error(400, "Action not supported.", format=format)

        data = runtime['config'].dump_object()

        # filter values for better security
        data = {k:v for k, v in data.items() if k in ('app', 'book')}
        data['app'] = {k:v for k, v in data['app'].items() if k in ('name', 'theme')}

        # add and rewrite values for client to better know the server
        data['app']['base'] = request.script_root
        data['app']['is_local'] = is_local_access()
        data['VERSION'] = __version__;
        data['WSB_DIR'] = WSB_DIR;
        data['WSB_LOCAL_CONFIG'] = WSB_LOCAL_CONFIG;

        return http_response(data, format=format)

    def token(self, format=None, *args, **kwargs):
        """Acquire a token and return its name."""
        return http_response(runtime['token_handler'].acquire(), format=format)

    @_handle_advanced
    @_handle_lock
    def lock(self, name, targetpath, query=None, format=None, *args, **kwargs):
        """Acquire a lock for the given name.

        URL params:
        - chkt: recheck until the lock file not exist or fail out when time out.
        - chks: how long to treat the lock file as stale.
        """
        check_stale = query.get('chks', 300, type=int)
        check_timeout = query.get('chkt', 5, type=int)
        check_expire = time.time() + check_timeout
        check_delta = min(check_timeout, 0.1)

        while True:
            try:
                os.makedirs(targetpath)
            except FileExistsError:
                t = time.time()

                if t >= check_expire or not os.path.isdir(targetpath):
                    return http_error(500, 'Unable to acquire lock "{}".'.format(name), format=format)

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
                        return http_error(500, 'Unable to regenerate stale lock "{}".'.format(name), format=format)
                    else:
                        break

                time.sleep(check_delta)
            except:
                traceback.print_exc()
                return http_error(500, 'Unable to create lock "{}".'.format(name), format=format)
            else:
                break

    @_handle_advanced
    @_handle_lock
    def unlock(self, name, targetpath, format=None, *args, **kwargs):
        """Release a lock for the given name."""
        try:
            os.rmdir(targetpath)
        except FileNotFoundError:
            pass
        except:
            traceback.print_exc()
            return http_error(500, 'Unable to remove lock "{}".'.format(name), format=format)

    @_handle_advanced
    @_handle_writing
    def mkdir(self,
            localpath,
            format=None,
            *args, **kwargs):
        """Create a directory."""
        if os.path.lexists(localpath) and not os.path.isdir(localpath):
            return http_error(400, "Found a non-directory here.", format=format)

        archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

        if archivefile:
            try:
                with zipfile.ZipFile(archivefile, 'a') as zip:
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

    @_handle_advanced
    @_handle_writing
    def save(self,
            localpath,
            query=None,
            format=None,
            *args, **kwargs):
        """Write a file with provided text or uploaded stream."""
        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            return http_error(400, "Found a non-file here.", format=format)

        archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

        if archivefile:
            try:
                temp_writing_file = None

                with zipfile.ZipFile(archivefile, 'a') as zip0:
                    # if subarchivepath exists, open a new zip file for writing.
                    try:
                        info = zip0.getinfo(subarchivepath)
                    except KeyError:
                        info = zipfile.ZipInfo(subarchivepath, time.localtime())
                    else:
                        info.date_time = time.localtime()
                        temp_writing_file = archivefile + '.' + str(time_ns())

                    try:
                        with zipfile.ZipFile(temp_writing_file, 'w') if temp_writing_file else zip0 as zip:
                            # write to the zip file
                            file = request.files.get('upload')
                            if file is not None:
                                with zip.open(info, 'w', force_zip64=True) as fh:
                                    stream = file.stream
                                    while True:
                                        s = stream.read(8192)
                                        if not s: break
                                        fh.write(s)
                            else:
                                bytes = query.get('text', '').encode('ISO-8859-1')
                                try:
                                    zip.writestr(info, bytes, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
                                except TypeError:
                                    # compresslevel is supported since Python 3.7
                                    zip.writestr(info, bytes, compress_type=zipfile.ZIP_DEFLATED)

                            # copy zip content
                            if temp_writing_file:
                                for info in zip0.infolist():
                                    if info.filename == subarchivepath:
                                        continue

                                    try:
                                        zip.writestr(info, zip0.read(info),
                                                compress_type=info.compress_type,
                                                compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9)
                                    except TypeError:
                                        # compresslevel is supported since Python 3.7
                                        zip.writestr(info, zip0.read(info),
                                                compress_type=info.compress_type)
                    except:
                        # remove the generated zip file if writing fails
                        if temp_writing_file:
                            try:
                                os.remove(temp_writing_file)
                            except FileNotFoundError:
                                pass

                        raise

                # replace zip0 with the generated zip file
                if temp_writing_file:
                    temp_renaming_file = archivefile + '.' + str(time_ns() + 1)
                    os.rename(archivefile, temp_renaming_file)
                    os.rename(temp_writing_file, archivefile)
                    os.remove(temp_renaming_file)
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
                    file.save(localpath)
                else:
                    bytes = query.get('text', '').encode('ISO-8859-1')
                    with open(localpath, 'wb') as f:
                        f.write(bytes)
            except:
                traceback.print_exc()
                return http_error(500, "Unable to write to this file.", format=format)

    @_handle_advanced
    @_handle_writing
    def delete(self,
            localpath,
            format=None,
            *args, **kwargs):
        """Delete a file or directory."""
        archivefile, subarchivepath = get_archive_path(request.path.lstrip('/'))

        if archivefile:
            try:
                temp_writing_file = archivefile + '.' + str(time_ns())
                deleted = False

                with zipfile.ZipFile(archivefile, 'r') as zip0:
                    try:
                        # copy zip content
                        with zipfile.ZipFile(temp_writing_file, 'w') as zip:
                            for info in zip0.infolist():
                                if (info.filename == subarchivepath or
                                        info.filename.startswith(subarchivepath + '/')):
                                    deleted = True
                                    continue

                                try:
                                    zip.writestr(info, zip0.read(info),
                                            compress_type=info.compress_type,
                                            compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9)
                                except TypeError:
                                    # compresslevel is supported since Python 3.7
                                    zip.writestr(info, zip0.read(info),
                                            compress_type=info.compress_type)
                    except:
                        # remove the generated zip file if writing fails
                        try:
                            os.remove(temp_writing_file)
                        except FileNotFoundError:
                            pass

                        raise

                # fail since nothing is deleted
                if not deleted:
                    os.remove(temp_writing_file)
                    return http_error(404, "Entry does not exist in this ZIP file.", format=format)

                # replace zip0 with the generated zip file
                temp_renaming_file = archivefile + '.' + str(time_ns() + 1)
                os.rename(archivefile, temp_renaming_file)
                os.rename(temp_writing_file, archivefile)
                os.remove(temp_renaming_file)
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
    def move(self,
            localpath,
            targetpath,
            format=None,
            *args, **kwargs):
        """Move a file or directory."""
        os.makedirs(os.path.dirname(targetpath), exist_ok=True)

        try:
            os.rename(localpath, targetpath)
        except:
            traceback.print_exc()
            return http_error(500, 'Unable to move to the target.', format=format)

    @_handle_advanced
    @_handle_writing
    @_handle_renaming
    def copy(self,
            localpath,
            targetpath,
            format=None,
            *args, **kwargs):
        """Copy a file or directory."""
        os.makedirs(os.path.dirname(targetpath), exist_ok=True)

        try:
            try:
                shutil.copytree(localpath, targetpath)
            except NotADirectoryError:
                shutil.copy2(localpath, targetpath)
        except:
            traceback.print_exc()
            return http_error(500, 'Unable to copy to the target.', format=format)

    _handle_advanced = staticmethod(_handle_advanced)
    _handle_lock = staticmethod(_handle_lock)
    _handle_writing = staticmethod(_handle_writing)
    _handle_renaming = staticmethod(_handle_renaming)

action_handler = ActionHandler()


@bp.route('/', methods=['GET', 'HEAD', 'POST'])
@bp.route('/<path:filepath>', methods=['GET', 'HEAD', 'POST'])
def handle_request(filepath=''):
    """Handle an HTTP request (HEAD, GET, POST).
    """
    # replace SCRIPT_NAME with the custom if set
    if runtime['config']['app']['base']:
        request.environ['SCRIPT_NAME'] = runtime['config']['app']['base']

    # handle authorization
    perm = get_permission(request.authorization)
    if not verify_authorization(perm, request.action):
        response = http_error(401, "You are not authorized.", format=request.format)
        response.www_authenticate.set_basic("Authentication required.")
        return response

    return action_handler._handle_action()


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
            })

    return app
