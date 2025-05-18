"""The WGSI application.
"""
import datetime
import functools
import hashlib
import json
import os
import time
import traceback
import types
from collections import defaultdict, namedtuple
from contextlib import nullcontext
from secrets import token_urlsafe
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from zlib import adler32

import commonmark
import flask
import jinja2
from flask import (
    Response,
    abort,
    current_app,
    redirect,
    render_template,
    request,
)
from werkzeug.datastructures import WWWAuthenticate
from werkzeug.exceptions import HTTPException
from werkzeug.http import (
    dump_options_header,
    http_date,
    is_resource_modified,
    parse_options_header,
)
from werkzeug.local import LocalProxy
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash
from werkzeug.utils import cached_property

from . import WSB_CONFIG, WSB_DIR, WSB_EXTENSION_MIN_VERSION, __version__, util
from ._polyfill import mimetypes, zipfile
from .scrapbook import cache as wsb_cache
from .scrapbook import check as wsb_check
from .scrapbook import exporter as wsb_exporter
from .scrapbook import host as wsb_host
from .scrapbook import importer as wsb_importer
from .scrapbook import search as wsb_search
from .scrapbook import util as wsb_util
from .util.fs import (
    ZIP_SUBPATH_DIR,
    ZIP_SUBPATH_DIR_IMPLICIT,
    ZIP_SUBPATH_DIR_ROOT,
    ZIP_SUBPATH_FILE,
)

# see: https://url.spec.whatwg.org/#percent-encoded-bytes
quote_path = functools.partial(quote, safe=":/[]@!$&'()*+,;=")
quote_path.__doc__ = 'Escape reserved chars for the path part of a URL.'

jsonify = functools.partial(
    json.dumps,
    ensure_ascii=False,
    check_circular=False,
    separators=(',', ':'),
)

bp = flask.Blueprint('default', __name__)
host = LocalProxy(lambda: current_app.config['WEBSCRAPBOOK_HOST'])


def static_url(path):
    return f'{quote_path(request.script_root)}/{quote_path(path)}?a=static'


def apply_csp(response):
    """Apply CSP, mostly for a static resource.
    """
    if host.config['app']['content_security_policy'] == 'strict':
        response.headers.set('Content-Security-Policy', "connect-src 'none'; form-action 'none';")


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
    apply_csp(response)
    return response


def zip_static_file(zh, subpath, mimetype=None):
    """Output the specified file in a ZIP to the client.

    Args:
        zh: an opened zipfile.ZipFile
        subpath: str or zipfile.ZipInfo
    """
    if not isinstance(subpath, zipfile.ZipInfo):
        try:
            info = zh.getinfo(subpath)
        except KeyError:
            abort(404)
    else:
        info = subpath

    fh = zh.open(info, 'r')

    lm = util.fs.zip_timestamp(info)
    last_modified = http_date(lm)

    etag = '%s-%s-%s' % (
        lm,
        info.file_size,
        adler32(info.filename.encode('utf-8')) & 0xFFFFFFFF,
    )

    headers = {
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'no-cache',
        'Last-Modified': last_modified,
        'ETag': etag,
    }

    response = Response(fh, headers=headers, mimetype=mimetype)
    response.make_conditional(request.environ, accept_ranges=True, complete_length=info.file_size)
    apply_csp(response)
    return response


def stream_template(template_name, **context):
    current_app.update_template_context(context)
    t = current_app.jinja_env.get_template(template_name)
    return t.stream(context)


def generate_server_sent_events(gen):
    try:
        for data in gen:
            yield 'data: ' + data + '\n\n'
    except Exception:
        traceback.print_exc()
        err = {'type': 'critical', 'msg': 'Internal Server Error'}
        yield 'data: ' + jsonify(err) + '\n\n'

    yield 'event: complete' + '\n'
    yield 'data: ' + '\n\n'


def http_response(body=None, status=None, headers=None, format=None):
    """Handle formatted response.

    ref: https://jsonapi.org
    """
    if not format:
        mimetype = None
        if body is None:
            body = ''

    # expect body to be a JSON-serializable object (including str)
    elif format == 'json':
        mimetype = 'application/json'

        if status == 204:
            status = None
            body = None

        body = jsonify({'data': body})

    # expect body to be a generator of text (mostly JSON) data
    elif format == 'sse':
        mimetype = 'text/event-stream'

        if status == 204:
            status = None
            body = None

        if body is None:
            body = generate_server_sent_events(iter(()))
        else:
            if not isinstance(body, types.GeneratorType):
                abort(500, 'Invalid generator for an event stream')

            body = generate_server_sent_events(body)

    else:
        abort(400, f'Output format {format!r} is not supported.')

    return Response(body, status, headers, mimetype=mimetype)


def get_localpath(path):
    """Convert a request path to local filesystem path.
    """
    # Don't use os.path.join as it doesn't concatenate if path looks like
    # absolute (e.g. "/path/to/foo" on POSIX or "X:/foo" on Windows), which
    # can cause a security issue.
    return os.path.normpath(host.chroot + os.sep + path)


def get_breadcrumbs(localpaths, base='', topname='.'):
    """Generate (label, subpath, sep, is_last) tuples.
    """
    base = base.rstrip('/') + '/'
    paths = list(localpaths)
    paths[0] = paths[0].strip('/')

    if not paths[0]:
        yield (topname, base, '/', True)
        return

    yield (topname, base, '/', False)

    # handle zip root, which is something like /archive.zip!/
    is_zip_root = False
    if paths[-1] == '':
        paths.pop()
        is_zip_root = True

    paths_max = len(paths) - 1
    pathlist = []
    for path_idx, path in enumerate(paths):
        pathlist.append([])
        parts = path.split('/')
        parts_max = len(parts) - 1
        for part_idx, part in enumerate(parts):
            pathlist[-1].append(part)
            subpath = '!/'.join('/'.join(p) for p in pathlist)
            sep = '!/' if part_idx == parts_max and (path_idx < paths_max or is_zip_root) else '/'
            is_last = path_idx == paths_max and part_idx == parts_max
            yield (part, base + subpath + sep, sep, is_last)


def is_local_access():
    """Determine if the client is in same device.
    """
    server_host = request.host.partition(':')[0]
    client_host = request.remote_addr
    return util.is_localhost(server_host) or util.is_localhost(client_host) or server_host == client_host


def handle_directory_listing(localpaths, zh=None, redirect_slash=True, format=None):
    """List contents in a directory.

    Args:
        localpaths: a CPath
        zh: an opened zipfile.ZipFile object for faster reading
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
    if len(localpaths) > 1:
        # support 304 if zip not modified
        stats = os.stat(localpaths[0])
        last_modified = http_date(stats.st_mtime)
        etag = '%s-%s-%s' % (
            stats.st_mtime,
            stats.st_size,
            adler32(localpaths[0].encode('utf-8')) & 0xFFFFFFFF,
        )

        if not is_resource_modified(request.environ, etag=etag, last_modified=last_modified):
            return http_response(status=304, format=format)

        headers = {
            'Cache-Control': 'no-cache',
            'Last-Modified': last_modified,
            'ETag': etag,
        }

        with nullcontext(zh) if zh else util.fs.open_archive_path(localpaths) as zh:
            subentries = zip_listdir(zh, localpaths[-1])

    else:
        # disallow cache to reflect any content file change
        stats = os.stat(localpaths[0])
        headers = {
            'Cache-Control': 'no-store',
            'Last-Modified': http_date(stats.st_mtime),
        }

        subentries = listdir(localpaths[0])

    if format == 'sse':
        def gen():
            for entry in subentries:
                data = entry._asdict()
                yield jsonify(data)

        return http_response(gen(), headers=headers, format=format)

    if format == 'json':
        data = [e._asdict() for e in subentries]
        return http_response(data, headers=headers, format=format)

    body = render_template('index.html',
                           sitename=host.name,
                           is_local=is_local_access(),
                           base=request.script_root,
                           path=request.path,
                           pathparts=request.paths,
                           subentries=subentries,
                           )
    return http_response(body, headers=headers)


def handle_archive_viewing(localpaths, mimetype):
    """Handle direct visit of HTZ/MAFF file.

    Args:
        localpaths: a CPath
    """
    def list_maff_pages(pages):
        """List available web pages in a MAFF file.
        """
        return render_template('maff_index.html',
                               sitename=host.name,
                               is_local=is_local_access(),
                               base=request.script_root,
                               path=request.path,
                               pages=pages,
                               )

    if mimetype == 'application/html+zip':
        subpath = 'index.html'
    else:
        if len(localpaths) > 1:
            with util.fs.open_archive_path(localpaths) as zh:
                with zh.open(localpaths[-1]) as zh1:
                    pages = util.get_maff_pages(zh1)
        else:
            pages = util.get_maff_pages(localpaths[-1])

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


def handle_markdown_output(localpaths, zh=None):
    """Output processed markdown.

    Args:
        localpaths: a CPath
        zh: an opened zipfile.ZipFile object for faster reading
    """
    if len(localpaths) > 1:
        if zh:
            context = nullcontext(zh)
        else:
            context = util.fs.open_archive_path(localpaths)
    else:
        context = nullcontext(None)

    with context as zh:
        # calculate last-modified time and etag
        if zh:
            info = zh.getinfo(localpaths[-1])
            lm = util.fs.zip_timestamp(info)
            last_modified = http_date(lm)

            etag = '%s-%s-%s' % (
                lm,
                info.file_size,
                adler32(info.filename.encode('utf-8')) & 0xFFFFFFFF,
            )
        else:
            stats = os.stat(localpaths[0])
            last_modified = http_date(stats.st_mtime)
            etag = '%s-%s-%s' % (
                stats.st_mtime,
                stats.st_size,
                adler32(localpaths[0].encode('utf-8')) & 0xFFFFFFFF,
            )

        if not is_resource_modified(request.environ, etag=etag, last_modified=last_modified):
            return http_response(status=304)

        headers = {
            'Cache-Control': 'no-cache',
            'Last-Modified': last_modified,
            'ETag': etag,
        }

        # prepare content
        if zh:
            with zh.open(info) as fh:
                body = fh.read().decode('UTF-8')
        else:
            with open(localpaths[0], 'r', encoding='UTF-8') as fh:
                body = fh.read()

    body = render_template('markdown.html',
                           sitename=host.name,
                           is_local=is_local_access(),
                           base=request.script_root,
                           path=request.path,
                           pathparts=request.paths,
                           content=commonmark.commonmark(body),
                           )

    response = http_response(body, headers=headers)
    apply_csp(response)
    return response


class Request(flask.Request):
    """Subclassed Request object for more useful properties.
    """
    @cached_property
    def paths(self):
        """Like request.path, but with ZIP subpaths resolved."""
        return util.fs.CPath.resolve(self.path, get_localpath)

    @cached_property
    def localpath(self):
        """Corresponding filesystem path of the requested path."""
        return get_localpath(self.path)

    @cached_property
    def localpaths(self):
        """Like localpath, but with ZIP subpaths resolved."""
        return util.fs.CPath(
            get_localpath(self.paths[0]),
            *self.paths[1:],
        )

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
        if not globals().get(f'action_{rv}'):
            rv = 'unknown'
        return rv

    @cached_property
    def format(self):
        """Shortcut of the requested format."""
        rv = request.values.get('f')
        rv = request.values.get('format', default=rv)
        return rv


def handle_action_token(func):
    """A decorator function that validates token.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        token = request.values.get('token') or ''

        if not host.token_validate(token):
            abort(400, 'Invalid access token.')

        host.token_delete(token)

        return func(*args, **kwargs)

    return wrapper


def handle_action_advanced(func):
    """A decorator function that helps handling an advanced command.

    - Verify POST method (except for SSE format).
    - Add 'Cache-Control: no-store' header.
    - Provide a default 204 response.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        format = request.format

        if request.method != 'POST' and format != 'sse':
            abort(405, valid_methods=['POST'])

        response = func(*args, **kwargs)

        if response is None:
            response = http_response(status=204, format=format)

        response.headers.set('Cache-Control', 'no-store')

        return response

    return wrapper


def handle_action_writing(func):
    """A decorator function that helps handling a writing action.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if os.path.abspath(request.localpath) == host.chroot:
            abort(403, 'Unable to operate the root directory.')

        return func(*args, **kwargs)

    return wrapper


def action_unknown():
    """Default handler for an undefined action"""
    abort(400, 'Action not supported.')


def action_view():
    """Show the content of a file or list a directory.

    If formatted, show information of the file or directory.
    """
    # info for other output formats
    if request.format:
        return action_info()

    localpaths = request.localpaths
    mimetype = request.localmimetype

    if len(localpaths) > 1:
        with util.fs.open_archive_path(localpaths) as zh:
            # List directory only when URL suffixed with "/", as it's not a
            # common operation, and it's costy to check for directory existence
            # in a ZIP.
            if request.path.endswith('/'):
                try:
                    return handle_directory_listing(localpaths, zh, redirect_slash=False)
                except ZipDirNotFoundError:
                    abort(404)

            try:
                info = zh.getinfo(localpaths[-1])
            except KeyError:
                # File does not exist.
                abort(404)
            else:
                # view archive file
                if mimetype in ('application/html+zip', 'application/x-maff'):
                    return handle_archive_viewing(localpaths, mimetype)

                # view markdown
                if mimetype == 'text/markdown':
                    return handle_markdown_output(localpaths, zh)

                # convert meta refresh to 302 redirect
                if localpaths[-1].lower().endswith('.htm'):
                    with zh.open(info) as fh:
                        target = util.get_meta_refresh(fh).target

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
                response = zip_static_file(zh, localpaths[-1], mimetype=mimetype)
    else:
        localpath = localpaths[0]

        # handle directory
        if os.path.isdir(localpath):
            return handle_directory_listing(localpaths)

        # handle file
        elif os.path.isfile(localpath):
            # view archive file
            if mimetype in ('application/html+zip', 'application/x-maff'):
                return handle_archive_viewing(localpaths, mimetype)

            # view markdown
            if mimetype == 'text/markdown':
                return handle_markdown_output(localpaths)

            # convert meta refresh to 302 redirect
            if request.localrealpath.lower().endswith('.htm'):
                target = util.get_meta_refresh(localpath).target

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


def action_source():
    """Show file content as plain text."""
    if request.format:
        abort(400, 'Action not supported.')

    localpaths = request.localpaths

    if len(localpaths) > 1:
        with util.fs.open_archive_path(localpaths) as zh:
            response = zip_static_file(zh, localpaths[-1])
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


def action_download():
    """Download a file or directory."""
    if request.format:
        abort(400, 'Action not supported.')

    localpaths = request.localpaths
    filter = request.values.getlist('i')

    if len(localpaths) > 1:
        with util.fs.open_archive_path(localpaths) as zh:
            cur = util.fs.zip_check_subpath(zh, localpaths[-1], allow_invalid=True)
            if cur in (ZIP_SUBPATH_DIR, ZIP_SUBPATH_DIR_IMPLICIT, ZIP_SUBPATH_DIR_ROOT):
                filename = (os.path.basename(localpaths[-1]) or os.path.basename(localpaths[-2])) + '.zip'
                mimetype, _ = mimetypes.guess_type(filename)
                response = None
            elif cur == ZIP_SUBPATH_FILE:
                filename = os.path.basename(request.localrealpath)
                response = zip_static_file(zh, localpaths[-1], mimetype=request.localmimetype)
            else:
                abort(404)

        if not response:
            def gen():
                zs = util.fs.ZipStream()
                with util.fs.open_archive_path(localpaths) as zh:
                    yield from util.fs.zip_copy(zh, localpaths[-1], zs, '', filter, stream=zs)

            response = Response(gen(), mimetype=mimetype)
            response.headers.set('Cache-Control', 'no-store')
    else:
        if os.path.isdir(localpaths[0]):
            filename = os.path.basename(request.localrealpath) + '.zip'
            mimetype, _ = mimetypes.guess_type(filename)
            zs = util.fs.ZipStream()
            gen = util.fs.zip_compress(zs, localpaths[0], '', filter, stream=zs)
            response = Response(gen, mimetype=mimetype)
            response.headers.set('Cache-Control', 'no-store')
        else:
            filename = os.path.basename(request.localrealpath)
            response = static_file(localpaths[0])

    filename = quote_path(filename)
    response.headers.set('Content-Disposition',
                         f'''attachment; filename*=UTF-8''{filename}; filename="{filename}"''')
    return response


def action_info():
    """Show information of a path."""
    format = request.format

    if format != 'json':
        abort(400, 'Action not supported.')

    localpaths = request.localpaths
    mimetype = request.localmimetype

    if len(localpaths) > 1:
        with util.fs.open_archive_path(localpaths) as zh:
            info = zip_file_info(zh, localpaths[-1], check_implicit_dir=True)
    else:
        info = file_info(localpaths[0])

    data = info._asdict()
    data['mime'] = mimetype
    return http_response(data, format=format)


def action_list():
    """List entries in a directory."""
    format = request.format

    if not format:
        abort(400, 'Action not supported.')

    localpaths = request.localpaths

    if len(localpaths) > 1:
        try:
            return handle_directory_listing(localpaths, redirect_slash=False, format=format)
        except ZipDirNotFoundError:
            abort(404, 'Directory does not exist.')

    if os.path.isdir(localpaths[0]):
        return handle_directory_listing(localpaths, redirect_slash=False, format=format)

    abort(404, 'Directory does not exist.')


def action_static():
    """Show a static file of the current theme."""
    format = request.format

    if format:
        abort(400, 'Action not supported.')

    filepath = request.path.strip('/')
    file = host.get_static_file(filepath)
    if file:
        return static_file(file)

    abort(404)


def action_edit():
    """Simple text editor for a file."""
    format = request.format

    if format:
        abort(400, 'Action not supported.')

    localpaths = request.localpaths
    localpath = localpaths[0]

    if os.path.lexists(localpath) and not os.path.isfile(localpath):
        abort(400, 'Found a non-file here.')

    if len(localpaths) > 1:
        with util.fs.open_archive_path(localpaths) as zh:
            try:
                info = zh.getinfo(localpaths[-1])
            except KeyError:
                body = b''
            else:
                body = zh.read(info)
    else:
        try:
            with open(localpath, 'rb') as fh:
                body = fh.read()
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
                           sitename=host.name,
                           is_local=is_local_access(),
                           base=request.script_root,
                           path=request.path,
                           body=body,
                           encoding=encoding,
                           )

    return http_response(body, format=format)


def action_editx():
    """HTML editor for a file."""
    format = request.format

    if format:
        abort(400, 'Action not supported.')

    localpaths = request.localpaths
    localpath = localpaths[0]

    if os.path.lexists(localpath) and not os.path.isfile(localpath):
        abort(400, 'Found a non-file here.')

    if request.localmimetype not in ('text/html', 'application/xhtml+xml'):
        abort(400, 'This is not an HTML file.')

    if len(localpaths) > 1:
        with util.fs.open_archive_path(localpaths) as zh:
            try:
                zh.getinfo(localpaths[-1])
            except KeyError:
                abort(404)
    else:
        if not os.path.lexists(localpath):
            abort(404)

    body = render_template('editx.html',
                           sitename=host.name,
                           is_local=is_local_access(),
                           base=request.script_root,
                           path=request.path,
                           )

    return http_response(body, format=format)


def action_exec():
    """Launch a file or directory."""
    format = request.format

    if not is_local_access():
        abort(400, 'Command can only run on local device.')

    localpath = request.localpath

    if not os.path.lexists(localpath):
        abort(404, 'File does not exist.')

    util.fs.launch(localpath)

    return http_response(status=204, format=format)


def action_browse():
    """Open a file or directory in the file browser."""
    format = request.format

    if not is_local_access():
        abort(400, 'Command can only run on local device.')

    localpath = request.localpath

    if not os.path.lexists(localpath):
        abort(404, 'File does not exist.')

    util.fs.view_in_explorer(localpath)

    return http_response(status=204, format=format)


def action_config():
    """Show server config."""
    format = request.format

    if format != 'json':
        abort(400, 'Action not supported.')

    key = request.values.get('k', default='')
    if key == 'search_help':
        data = {
            'help': {
                'label': host.i18n('cache_search_help_label'),
                'desc': host.i18n('cache_search_help_desc'),
            },
            'helpers': [
                {'text': 'id:', 'value': 'id:'},
                {'text': 'title:', 'value': 'title:'},
                {'text': 'comment:', 'value': 'comment:'},
                {'text': 'content:', 'value': 'content:'},
                {'text': 'source:', 'value': 'source:'},
                {'text': 'icon:', 'value': 'icon:'},
                {'text': 'type:', 'value': 'type:'},
                {'text': 'create:', 'value': 'create:'},
                {'text': 'modify:', 'value': 'modify:'},
                {'text': 'charset:', 'value': 'charset:'},
                {'text': 'marked:', 'value': 'marked:'},
                {'text': 'locked:', 'value': 'locked:'},
                {'text': 'location:', 'value': 'location:'},
                {'text': 're:', 'value': 're:'},
                {'text': 'mc:', 'value': 'mc:'},
                {'text': 'file:', 'value': 'file:'},
                {'text': 'root:', 'value': 'root:'},
                {'text': 'limit:', 'value': 'limit:'},
                {'text': 'sort:', 'value': 'sort:'},
                {'text': host.i18n('cache_search_sort_last_modified'), 'value': '-sort:modify'},
                {'text': host.i18n('cache_search_sort_last_created'), 'value': '-sort:create'},
                {'text': host.i18n('cache_search_sort_title'), 'value': 'sort:title'},
                {'text': host.i18n('cache_search_sort_id'), 'value': 'sort:id'},
            ],
        }
        return http_response(data, format=format)

    data = host.config.dump_object()

    # filter values for better security
    data = {k: v for k, v in data.items() if k in ('app', 'book')}
    data['app'] = {k: v for k, v in data['app'].items() if k in ('name', 'theme', 'locale')}

    # expose backup_dir if it's web accessible
    if os.path.normcase(os.path.join(host.backup_dir, '')).startswith(os.path.normcase(os.path.join(host.chroot, ''))):
        data['app']['backup_dir'] = host.backup_dir[len(os.path.join(host.chroot, '')):].replace('\\', '/')

    # add and rewrite values for client to better know the server
    data['app']['base'] = request.script_root
    data['app']['is_local'] = is_local_access()
    data['VERSION'] = __version__
    data['WSB_DIR'] = WSB_DIR
    data['WSB_CONFIG'] = WSB_CONFIG
    data['WSB_EXTENSION_MIN_VERSION'] = WSB_EXTENSION_MIN_VERSION

    return http_response(data, format=format)


def action_token():
    """Acquire a token and return its name."""
    format = request.format

    # require POST method
    if request.method != 'POST':
        abort(405, valid_methods=['POST'])

    if format not in (None, 'json'):
        abort(400, 'Action not supported.')

    return http_response(host.token_acquire(), format=format)


@handle_action_advanced
@handle_action_token
def action_lock():
    """Acquire a lock for the given name.

    URL params:
    - id: for persisting and extending previous lock.
    - chkt: timeout to wait for the lock.
    """
    # verify name
    name = request.values.get('name')
    if name is None:
        abort(400, 'Lock name is not specified.')

    id = request.values.get('id')

    timeout = request.values.get('chkt', 5, type=float)

    try:
        lock = host.get_lock(name, persist=id)
    except wsb_host.LockPersistError:
        abort(400, f'Unable to persist lock {name!r}.')

    if id:
        try:
            lock.extend()
        except wsb_host.LockExtendNotFoundError:
            # Lock file gone in this short interval. Try acquire.
            pass
        except wsb_host.LockExtendError:
            abort(500, f'Unable to extend lock {name!r}.')
        else:
            return http_response(lock.id, format=request.format)

    try:
        lock.acquire(timeout=timeout)
    except wsb_host.LockTimeoutError:
        abort(503, f'Unable to acquire lock {name!r}.', retry_after=60)
    except wsb_host.LockRegenerateError:
        abort(500, f'Unable to regenerate stale lock {name!r}.')
    except wsb_host.LockGenerateError:
        abort(500, f'Unable to create lock {name!r}.')

    return http_response(lock.id, format=request.format)


@handle_action_advanced
@handle_action_token
def action_unlock():
    """Release a lock for the given name."""
    # verify name
    name = request.values.get('name')
    if name is None:
        abort(400, 'Lock name is not specified.')

    # verify ID
    id = request.values.get('id')
    if id is None:
        abort(400, 'Lock ID is not specified.')

    try:
        lock = host.get_lock(name, persist=id)
    except wsb_host.LockPersistError:
        abort(400, f'Unable to persist lock {name!r}.')

    try:
        lock.release()
    except wsb_host.LockReleaseNotFoundError:
        pass
    except wsb_host.LockReleaseError:
        abort(500, f'Unable to remove lock {name!r}.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_mkdir():
    """Create a directory."""
    localpaths = request.localpaths

    try:
        util.fs.mkdir(localpaths)
    except util.fs.FSEntryExistsError:
        abort(400, 'Found something here.')
    except util.fs.FSBadParentError:
        abort(400, 'Parent directory is not available.')
    except Exception:
        traceback.print_exc()
        abort(500, 'Unable to create a directory here.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_mkzip():
    """Create a zip file."""
    localpaths = request.localpaths

    try:
        util.fs.mkzip(localpaths)
    except util.fs.FSIsADirectoryError:
        abort(400, 'Found a non-file here.')
    except util.fs.FSEntryExistsError:
        abort(400, 'Found something here.')
    except util.fs.FSBadParentError:
        abort(400, 'Parent directory is not available.')
    except Exception:
        traceback.print_exc()
        abort(500, 'Unable to write to this ZIP file.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_save():
    """Write a file with provided text or uploaded stream."""
    localpaths = request.localpaths

    file = request.files.get('upload')
    if file is not None:
        src = file.stream
    else:
        src = request.values.get('text', '').encode('ISO-8859-1')

    try:
        util.fs.save(localpaths, src)
    except util.fs.FSIsADirectoryError:
        abort(400, 'Found a non-file here.')
    except util.fs.FSEntryExistsError:
        abort(400, 'Found something here.')
    except util.fs.FSBadParentError:
        abort(400, 'Parent directory is not available.')
    except Exception:
        traceback.print_exc()
        abort(500, 'Unable to write to this ZIP file.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_delete():
    """Delete a file or directory."""
    localpaths = request.localpaths

    try:
        util.fs.delete(localpaths)
    except util.fs.FSEntryNotFoundError:
        abort(404, 'Entry does not exist.')
    except Exception:
        traceback.print_exc()
        abort(500, 'Unable to delete this entry.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_move():
    """Move a file or directory."""
    localpaths = request.localpaths

    target = request.values.get('target')
    if target is None:
        abort(400, 'Target is not specified.')
    targetpaths = util.fs.CPath.resolve(target, get_localpath).path
    targetpaths[0] = get_localpath(targetpaths[0])

    try:
        util.fs.move(localpaths, targetpaths)
    except util.fs.FSEntryExistsError:
        abort(400, 'Target already exists.')
    except util.fs.FSMoveInsideError:
        abort(400, 'Unable to move into self.')
    except util.fs.FSMoveAcrossZipError:
        abort(400, 'Unable to move across a zip.')
    except util.fs.FSEntryNotFoundError:
        abort(404, 'Source does not exist.')
    except Exception:
        traceback.print_exc()
        abort(500, 'Unable to move to the target.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_copy():
    """Copy a file or directory."""
    localpaths = request.localpaths

    target = request.values.get('target')
    if target is None:
        abort(400, 'Target is not specified.')
    targetpaths = util.fs.CPath.resolve(target, get_localpath).path
    targetpaths[0] = get_localpath(targetpaths[0])

    try:
        util.fs.copy(localpaths, targetpaths)
    except util.fs.FSEntryExistsError:
        abort(400, 'Target already exists.')
    except util.fs.FSEntryNotFoundError:
        abort(404, 'Source does not exist.')
    except util.fs.FSPartialError:
        abort(500, 'Fail to copy some files.')
    except Exception:
        traceback.print_exc()
        abort(500, 'Unable to copy to the target.')


@handle_action_advanced
@handle_action_token
def action_backup():
    """Bakup file or directory."""
    format = request.format

    if format != 'json':
        abort(400, 'Action not supported.')

    localpaths = request.localpaths

    if len(localpaths) > 1:
        abort(400, 'Unable to backup inside a zip file.')

    ts = request.values.get('ts') or util.datetime_to_id()
    note = request.values.get('note')
    move = request.values.get('move', default=False, type=bool)

    backup_dir = host.get_auto_backup_dir(ts, note=note)
    host.backup(localpaths[0], backup_dir=backup_dir, move=move)
    return http_response(os.path.basename(backup_dir), format=request.format)


@handle_action_advanced
@handle_action_token
def action_unbackup():
    """Remove a backup."""
    format = request.format

    if format != 'json':
        abort(400, 'Action not supported.')

    ts = request.values.get('ts') or util.datetime_to_id()
    note = request.values.get('note')

    backup_dir = host.get_auto_backup_dir(ts, note=note)
    host.unbackup(backup_dir)
    return http_response(os.path.basename(backup_dir), format=request.format)


@handle_action_advanced
@handle_action_token
def action_cache():
    """Invoke the cacher."""
    format = request.format

    book_ids = request.values.getlist('book')
    item_ids = request.values.getlist('item')
    book_items = {}
    for i, book_id in enumerate(book_ids):
        book_items[book_id] = request.values.getlist(f'item[{i}]') + item_ids

    gen = wsb_cache.generate(
        (host.root, host.config),
        book_items=book_items,
        lock=request.values.get('lock', default=True),
        backup=request.values.get('backup', default=True, type=bool),
        fulltext=request.values.get('fulltext', default=False, type=bool),
        recreate=request.values.get('recreate', default=False, type=bool),
        static_site=request.values.get('static_site', default=False, type=bool),
        static_index=request.values.get('static_index', default=None, type=bool),
        rss=request.values.get('rss', default=None, type=bool),
    )

    if format == 'sse':
        def wrapper():
            for info in gen:
                yield jsonify({
                    'type': info.type,
                    'msg': info.msg,
                })

        return http_response(wrapper(), format=format)

    elif format:
        for info in gen:
            if info.type == 'critical':
                abort(500, info.msg)
        return None

    stream = stream_template('cli.html',
                             title='Indexing...',
                             messages=gen,
                             debug=False,
                             )

    return Response(stream)


@handle_action_advanced
@handle_action_token
def action_check():
    """Invoke the checker."""
    format = request.format

    gen = wsb_check.run(
        (host.root, host.config),
        book_ids=request.values.getlist('book'),
        lock=request.values.get('lock', default=True),
        backup=request.values.get('backup', default=True, type=bool),
        resolve_invalid_id=request.values.get('resolve_invalid_id', default=False, type=bool),
        resolve_missing_index=request.values.get('resolve_missing_index', default=False, type=bool),
        resolve_missing_index_file=request.values.get('resolve_missing_index_file', default=False, type=bool),
        resolve_missing_date=request.values.get('resolve_missing_date', default=False, type=bool),
        resolve_older_mtime=request.values.get('resolve_older_mtime', default=False, type=bool),
        resolve_toc_unreachable=request.values.get('resolve_toc_unreachable', default=False, type=bool),
        resolve_toc_invalid=request.values.get('resolve_toc_invalid', default=False, type=bool),
        resolve_toc_empty_subtree=request.values.get('resolve_toc_empty_subtree', default=False, type=bool),
        resolve_unindexed_files=request.values.get('resolve_unindexed_files', default=False, type=bool),
        resolve_absolute_icon=request.values.get('resolve_absolute_icon', default=False, type=bool),
        resolve_unused_icon=request.values.get('resolve_unused_icon', default=False, type=bool),
    )

    if format == 'sse':
        def wrapper():
            for info in gen:
                yield jsonify({
                    'type': info.type,
                    'msg': info.msg,
                })

        return http_response(wrapper(), format=format)

    elif format:
        for info in gen:
            if info.type == 'critical':
                abort(500, info.msg)
        return None

    stream = stream_template('cli.html',
                             title='Checking...',
                             messages=gen,
                             debug=False,
                             )

    return Response(stream)


@handle_action_advanced
@handle_action_token
def action_export():
    """Export items as an archive file."""
    format = request.format

    if format:
        abort(400, 'Action not supported.')

    book_id = request.values.get('book', default='')

    zs = util.fs.ZipStream()
    gen = wsb_exporter.run(
        (host.root, host.config), zs,
        book_id=book_id,
        items=request.values.get('items', default=(), type=json.loads),
        scheme=wsb_exporter.SCHEME_ROOT_INDEXES,
        recursive=request.values.get('recursive', default=False, type=bool),
        singleton=request.values.get('singleton', default=False, type=bool),
        lock=request.values.get('lock', default=True),
        stream=zs,
    )

    def wrapper():
        for info in gen:
            if info.type == 'critical':
                abort(500, info.msg)
            if isinstance(info.data, bytes):
                yield info.data

    filename = 'exports.wsba'
    mimetype, _ = mimetypes.guess_type(filename)
    filename = quote_path(filename)
    response = Response(wrapper(), mimetype=mimetype)
    response.headers.set('Content-Disposition',
                         f'''attachment; filename*=UTF-8''{filename}; filename="{filename}"''')
    return response


@handle_action_advanced
@handle_action_token
def action_import():
    """Import items from the archive files in the "exports" directory."""
    format = request.format

    book_id = request.values.get('book', default='')
    target_id = request.values.get('target')
    target_index = request.values.get('index', type=int)
    rebuild_folders = request.values.get('rebuild', default=False, type=bool)
    resolve_id_used = request.values.get('resolve', default='new')
    lock = request.values.get('lock', default=True)

    export_dir = os.path.join(host.books[book_id].tree_dir, 'exports')
    os.makedirs(export_dir, exist_ok=True)
    with os.scandir(export_dir) as it:
        files = sorted(f.path for f in it)

    _gen = wsb_importer.run(
        (host.root, host.config), files,
        book_id=book_id,
        target_id=target_id,
        target_index=target_index,
        rebuild_folders=rebuild_folders,
        resolve_id_used=resolve_id_used,
        lock=lock,
    )

    def gen():
        try:
            yield from _gen
        finally:
            util.fs.delete(export_dir)

    if format == 'sse':
        def wrapper():
            for info in gen():
                yield jsonify({
                    'type': info.type,
                    'msg': info.msg,
                })

        return http_response(wrapper(), format=format)

    elif format:
        for info in gen():
            if info.type == 'critical':
                abort(500, info.msg)
        return None

    stream = stream_template('cli.html',
                             title='Importing...',
                             messages=gen(),
                             debug=False,
                             )

    return Response(stream)


@handle_action_advanced
@handle_action_token
def action_query():
    """Perform queries on the scrapbook(s)."""
    query = request.values.getlist('q', type=json.loads)
    auto_cache = request.values.get('auto_cache', type=json.loads)
    details = request.values.get('details', default=False, type=bool)
    lock = request.values.get('lock', default=True)

    try:
        rv = wsb_util.HostQuery((host.root, host.config),
                                query, auto_cache, lock=lock).run()
    except Exception as exc:
        traceback.print_exc()
        abort(500, str(exc))

    if details:
        return http_response(rv, format=request.format)


@handle_action_advanced
def action_search():
    """Search in scrapbooks."""
    format = request.format

    gen = wsb_search.search(
        (host.root, host.config),
        query=request.values.get('q', default=''),
        context={
            'title': -1,
            'file': -1,
            'comment': request.values.get('comment', default=None, type=int),
            'source': request.values.get('source', default=None, type=int),
            'fulltext': request.values.get('fulltext', default=None, type=int),
        },
        lock=request.values.get('lock', default=True),
    )

    if format == 'json':
        data = defaultdict(list)
        try:
            for item in gen:
                data[item.book_id].append({
                    'id': item.id,
                    'file': item.file,
                    'context': item.context,
                })
        except wsb_search.QueryError as exc:
            abort(400, str(exc))

        return http_response(data, format=format)

    elif format == 'sse':
        def wrapper():
            try:
                for item in gen:
                    yield jsonify({
                        'type': 'info',
                        'msg': '',
                        'data': {
                            'book_id': item.book_id,
                            'id': item.id,
                            'file': item.file,
                            'context': item.context,
                        },
                    })
            except wsb_search.QueryError as exc:
                yield jsonify({
                    'type': 'critical',
                    'msg': str(exc),
                })

        return http_response(wrapper(), format=format)

    else:
        abort(400, 'Action not supported.')


@bp.before_request
def handle_before_request():
    host.verify_authorization()


@bp.route('/', methods=['GET', 'HEAD', 'POST'])
@bp.route('/<path:filepath>', methods=['GET', 'HEAD', 'POST'])
def handle_request(filepath=''):
    """Handle an HTTP request (HEAD, GET, POST).
    """
    try:
        handler = globals()[f'action_{request.action}']
        return handler()
    except PermissionError:
        abort(403)


@bp.after_request
def handle_after_request(response):
    # forbid a privileged page to be framed
    if host.config['app']['content_security_policy'] == 'strict':
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
        response.data = jsonify({
            'error': {
                'status': exc.code,
                'message': exc.description,
            },
        })
        response.content_type = 'application/json'
        return response

    if request.format == 'sse':
        _code = exc.code

        # use 200 for common errors for the client API to parse the content
        if exc.code in (400, 403, 404, 500):
            exc.code = 200

        response = exc.get_response()
        response.data = ''.join(generate_server_sent_events((
            jsonify({
                'type': 'critical',
                'msg': exc.description,
                'data': {'status': _code},
            }),
        )))
        response.content_type = 'text/event-stream'
        return response

    return exc


class WebHost(wsb_host.Host):
    """Extended Host class that also handles HTTP server related things.

    - Token handling: security token validation to avoid CSRF attack.
    """
    TOKEN_PURGE_INTERVAL = 3600  # in seconds
    TOKEN_DEFAULT_EXPIRY = 1800  # in seconds

    def __init__(self, root, config=None):
        super().__init__(root, config=config)

        # token handling
        self.tokens = os.path.join(self.root, WSB_DIR, 'server', 'tokens')
        self.token_last_purge = 0

        # cache
        self._get_permission_cache = {}
        self._get_permission_cache_salt = token_urlsafe()

    @cached_property
    def i18n(self):
        return self.get_i18n(self.config['app']['locale'])

    def token_acquire(self, now=None):
        if now is None:
            now = int(time.time())

        self.token_check_delete_expire(now)

        token = token_urlsafe()
        token_file = os.path.join(self.tokens, token)
        while os.path.lexists(token_file):
            token = token_urlsafe()
            token_file = os.path.join(self.tokens, token)

        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        with open(token_file, 'w', encoding='UTF-8') as fh:
            fh.write(str(now + self.TOKEN_DEFAULT_EXPIRY))

        return token

    def token_validate(self, token, now=None):
        if now is None:
            now = int(time.time())

        token_file = os.path.join(self.tokens, token)

        try:
            with open(token_file, 'r', encoding='UTF-8') as fh:
                expire = int(fh.read())
        except (FileNotFoundError, IsADirectoryError):
            return False

        if now >= expire:
            os.remove(token_file)
            return False

        return True

    def token_delete(self, token):
        token_file = os.path.join(self.tokens, token)

        try:
            os.remove(token_file)
        except OSError:
            pass

    def token_delete_expire(self, now=None):
        if now is None:
            now = int(time.time())

        try:
            token_files = os.scandir(self.tokens)
        except FileNotFoundError:
            pass
        else:
            for token_file in token_files:
                try:
                    with open(token_file, 'r', encoding='UTF-8') as fh:
                        expire = int(fh.read())
                except (OSError, ValueError):
                    continue
                if now >= expire:
                    os.remove(token_file)

    def token_check_delete_expire(self, now=None):
        if now is None:
            now = int(time.time())

        if now >= self.token_last_purge + self.TOKEN_PURGE_INTERVAL:
            self.token_last_purge = now
            self.token_delete_expire(now)

    def verify_authorization(self):
        """Verify that the current request is adequately authorized.

        - Must run in a request context.
        - Abort the request if not authorized.
        """
        if 'auth' not in self.config:
            return

        auth = request.authorization or {}
        username = auth.get('username') or ''
        password = auth.get('password') or ''
        perm = self.get_permission(username, password)
        if not self.check_permission(perm, request.action):
            auth = WWWAuthenticate('basic', {'realm': self.config['app']['name']})
            abort(401, 'You are not authorized.', www_authenticate=auth)

    def get_permission(self, username, password):
        """Calculate effective permission from provided auth info.

        - A valid username-password combinations will be cached (in hashed
          form) in the memory to prevent a slow down due to repeated slow
          hash checking.
        """
        # return cached value if exists
        try:
            return self._get_permission_cache[
                self._get_permission_hash(username, password)
            ]
        except KeyError:
            pass

        for _, entry in self.config['auth'].items():
            entry_user = entry.get('user', '')
            if username != entry_user:
                continue

            entry_pw = entry.get('pw', '')
            if entry_pw:
                if not check_password_hash(entry_pw, password):
                    continue
            else:
                if password != entry_pw:
                    continue

            entry_permission = entry.get('permission', 'all')

            # cache a successful match
            self._get_permission_cache[
                self._get_permission_hash(username, password)
            ] = entry_permission

            return entry_permission

        return ''

    def _get_permission_hash(self, username, password):
        key = '\0'.join((username, password, self._get_permission_cache_salt))
        return hashlib.sha512(key.encode('UTF-8')).digest()

    @staticmethod
    def check_permission(perm, action):
        """Check authorization for the provided perm and action."""
        if perm == 'all':
            return True

        if perm == 'read':
            return action not in {
                'token', 'lock', 'unlock',
                'mkdir', 'mkzip', 'save', 'delete', 'move', 'copy',
                'backup', 'unbackup', 'cache', 'check', 'export', 'import', 'query',
            }

        if perm == 'view':
            return action in {'view', 'info', 'source', 'download', 'static', 'unknown'}

        return False


def make_app(root='.', config=None):
    _host = WebHost(root, config=config)

    # main app instance
    app = flask.Flask(__name__, instance_path=_host.chroot)
    app.register_blueprint(bp)
    app.request_class = Request
    app.config['WEBSCRAPBOOK_HOST'] = _host

    xheaders = {
        'x_for': _host.config['app']['allowed_x_for'],
        'x_proto': _host.config['app']['allowed_x_proto'],
        'x_host': _host.config['app']['allowed_x_host'],
        'x_port': _host.config['app']['allowed_x_port'],
        'x_prefix': _host.config['app']['allowed_x_prefix'],
    }

    if any(v for v in xheaders.values()):
        app.wsgi_app = ProxyFix(app.wsgi_app, **xheaders)

    app.jinja_loader = jinja2.FileSystemLoader(_host.templates)
    app.jinja_env.globals.update({
        'os': os,
        'time': time,
        'datetime': datetime,
        'get_breadcrumbs': get_breadcrumbs,
        'format_filesize': functools.partial(util.format_filesize, space='\xA0'),
        'quote_path': quote_path,
        'static_url': static_url,
        'i18n': _host.i18n,
    })

    return app


#########################################################################
# Filesystem helpers
#########################################################################

FileInfo = namedtuple('FileInfo', ('name', 'type', 'size', 'last_modified'))


def file_info(file, base=None):
    """Read basic file information.

    Args:
        file: path of the file
        base: path that the result filename is based under
    """
    if base is None:
        name = os.path.basename(file)
    else:
        base = os.path.join(base, '')
        if not file.startswith(base):
            raise ValueError('file not under base')

        name = util.unify_pathsep(file[len(base):])

    try:
        statinfo = os.lstat(file)
    except OSError:
        # unexpected error when getting stat info
        statinfo = None
        size = None
        last_modified = None
    else:
        size = statinfo.st_size
        last_modified = statinfo.st_mtime

    if not os.path.lexists(file):
        type = None
    elif os.path.islink(file) or util.fs.isjunction(file):
        type = 'link'
    elif os.path.isdir(file):
        type = 'dir'
    elif os.path.isfile(file):
        type = 'file'
    else:
        type = 'unknown'

    if type != 'file':
        size = None

    return FileInfo(name=name, type=type, size=size, last_modified=last_modified)


def listdir(base, recursive=False):
    """Generates FileInfo(s) and omit invalid entries.
    """
    if not recursive:
        with os.scandir(base) as entries:
            for entry in entries:
                info = file_info(entry.path)
                if info.type is None:
                    continue
                yield info

    else:
        for root, dirs, files in os.walk(base):
            for dir in dirs:
                file = os.path.join(root, dir)
                info = file_info(file, base)
                if info.type is None:
                    continue
                yield info
            for file in files:
                file = os.path.join(root, file)
                info = file_info(file, base)
                if info.type is None:
                    continue
                yield info


#########################################################################
# ZIP helpers
#########################################################################

class ZipDirNotFoundError(Exception):
    pass


def zip_file_info(zip, subpath, base=None, check_implicit_dir=False):
    """Read basic file information from ZIP.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        subpath: 'dir' and 'dir/' are both supported
        base: path that the result filename is based under,
            'dir' and 'dir/' are both supported
    """
    subpath = subpath.rstrip('/')
    if base is None:
        name = os.path.basename(subpath)
    else:
        base = base.rstrip('/')
        base = base + ('/' if base else '')
        if not subpath.startswith(base):
            raise ValueError('subpath not under base')

        name = subpath[len(base):]

    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
        try:
            info = zh.getinfo(subpath)
        except KeyError:
            pass
        else:
            return FileInfo(
                name=name, type='file',
                size=info.file_size,
                last_modified=util.fs.zip_timestamp(info),
            )

        try:
            info = zh.getinfo(subpath + '/')
        except KeyError:
            pass
        else:
            return FileInfo(
                name=name, type='dir', size=None,
                last_modified=util.fs.zip_timestamp(info),
            )

        if check_implicit_dir:
            base = subpath + ('/' if subpath else '')
            for entry in zh.namelist():
                if entry.startswith(base):
                    return FileInfo(name=name, type='dir', size=None, last_modified=None)

    return FileInfo(name=name, type=None, size=None, last_modified=None)


def zip_listdir(zip, subpath, recursive=False):
    """Generates FileInfo(s) and omit invalid entries.

    Raise ZipDirNotFoundError if subpath does not exist.

    NOTE: It is possible that entry mydir/ does not exist while mydir/foo.bar
    exists. Check for matching subentries to make sure whether the implicit
    directory exists.

    Args:
        zip: path, file-like object, or zipfile.ZipFile
        subpath: the subpath in the ZIP, with or without trailing slash
    """
    base = subpath.rstrip('/')
    if base:
        base += '/'
    base_len = len(base)
    dir_exist = not base
    entries = {}

    with nullcontext(zip) if isinstance(zip, zipfile.ZipFile) else zipfile.ZipFile(zip) as zh:
        for filename in zh.namelist():
            if not filename.startswith(base):
                continue

            if filename == base:
                dir_exist = True
                continue

            entry = filename[base_len:]
            if not recursive:
                entry, _, _ = entry.partition('/')
                entries.setdefault(entry, True)
            else:
                parts = entry.rstrip('/').split('/')
                for i in range(0, len(parts)):
                    entry = '/'.join(parts[0:i + 1])
                    entries.setdefault(entry, True)

        if not entries and not dir_exist:
            raise ZipDirNotFoundError(f'Directory {base!r} does not exist in the zip.')

        for entry in entries:
            info = zip_file_info(zh, base + entry, base)

            if info.type is None:
                yield FileInfo(name=entry, type='dir', size=None, last_modified=None)
            else:
                yield info
