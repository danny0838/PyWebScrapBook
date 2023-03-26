"""The WGSI application.
"""
import functools
import io
import json
import mimetypes
import os
import re
import shutil
import time
import traceback
import zipfile
from contextlib import contextmanager, nullcontext
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
from werkzeug.utils import cached_property

from . import WSB_CONFIG, WSB_DIR, WSB_EXTENSION_MIN_VERSION, __version__, util
from .scrapbook import cache as wsb_cache
from .scrapbook import check as wsb_check
from .scrapbook import host as wsb_host

# see: https://url.spec.whatwg.org/#percent-encoded-bytes
quote_path = functools.partial(quote, safe=":/[]@!$&'()*+,;=")
quote_path.__doc__ = 'Escape reserved chars for the path part of a URL.'

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
                    yield 'data: ' + data + '\n\n'
            except Exception:
                traceback.print_exc()
                err = {'error': {'message': 'Internal Server Error'}}
                yield 'data: ' + json.dumps(err, ensure_ascii=False) + '\n\n'

            yield 'event: complete' + '\n'
            yield 'data: ' + '\n\n'

        body = wrapper(body)

    else:
        abort(400, f'Output format "{format}" is not supported.')

    return Response(body, status, headers, mimetype=mimetype)


def get_localpath(path):
    """Convert a request path to local filesystem path.
    """
    # Don't use os.path.join as it doesn't concatenate if path looks like
    # absolute (e.g. "/path/to/foo" on POSIX or "X:/foo" on Windows), which
    # can cause a security issue.
    return os.path.normpath(host.chroot + os.sep + path)


def _get_archive_path_tidy(path, striproot=False):
    has_initial_slash = path.startswith('/')
    comps = path.split('/')
    new_comps = []
    for comp in comps:
        if comp in ('', '.'):
            continue
        if comp == '..':
            if new_comps:
                new_comps.pop()
            continue
        new_comps.append(comp)
    return ('/' if has_initial_slash and not striproot else '') + '/'.join(new_comps)


def _get_archive_path_add_subpath(paths, zh, subpath):
    for m in reversed(list(re.finditer(r'!/', subpath, flags=re.I))):
        archivepath = _get_archive_path_tidy(subpath[:m.start(0)], True)
        conflicting = archivepath + '!/'

        if any(i.startswith(conflicting) for i in zh.namelist()):
            break

        try:
            fh = zh.open(archivepath, 'r')
        except KeyError:
            continue

        with fh as fh:
            try:
                zh1 = zipfile.ZipFile(fh, 'r')
            except zipfile.BadZipFile:
                continue

            with zh1 as zh1:
                paths.append(archivepath)
                _get_archive_path_add_subpath(paths, zh1, subpath[m.end(0):])
                return

    paths.append(_get_archive_path_tidy(subpath, True))


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
    paths = []
    for m in reversed(list(re.finditer(r'!/', filepath, flags=re.I))):
        archivepath = _get_archive_path_tidy(filepath[:m.start(0)])
        archivefile = get_localpath(archivepath)
        conflicting = archivefile + '!'
        if os.path.lexists(conflicting):
            break

        # if parent directory does not exist, FileNotFoundError is raised on
        # Windows, while NotADirectoryError is raised on Linux
        try:
            zh = zipfile.ZipFile(archivefile, 'r')
        except (zipfile.BadZipFile, FileNotFoundError, NotADirectoryError):
            continue

        with zh as zh:
            paths.append(archivepath)
            _get_archive_path_add_subpath(paths, zh, filepath[m.end(0):])
            return paths

    paths.append(_get_archive_path_tidy(filepath))
    return paths


def _open_archive_path_filter(path, filters):
    for filter in filters:
        filter = filter.rstrip('/')
        if path == filter:
            return True
        if path.startswith(filter + ('/' if filter else '')):
            return True
    return False


@contextmanager
def open_archive_path(localpaths, mode='r', filters=None):
    """Open the innermost zip handler for reading or writing.

    e.g. reading from localpaths=['/path/to/foo.zip', 'subdir/file.txt']:

        with open_archive_path(localpaths) as zh:
            with zh.open(localpaths[-1]) as fh:
                print(fh.read())

    e.g. writing to localpaths=['/path/to/foo.zip', 'subdir/file.txt']:

        with open_archive_path(localpaths, 'w') as zh:
            zh.writestr(localpaths[-1], 'foo')

    e.g. deleting localpaths=['/path/to/foo.zip', 'subdir/']:

        with open_archive_path(localpaths, 'w', [localpaths[-1]]) as zh:
            pass

    Args:
        localpaths: [path-to-zip-file, subpath1, subpath2, ...]
        mode: 'r' for reading, 'w' for modifying
        filters: a list of file or folder to remove
    """
    last = len(localpaths) - 1
    if last < 1:
        raise ValueError('length of paths must > 1')

    filtered = False
    stack = []
    try:
        zh = zipfile.ZipFile(localpaths[0])
        stack.append(zh)
        for i in range(1, last):
            fh = zh.open(localpaths[i])
            stack.append(fh)
            zh = zipfile.ZipFile(fh)
            stack.append(zh)

        if mode == 'r':
            yield zh

        elif mode == 'w':
            # create a buffer for writing
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as zh:
                yield zh

            # copy zip file
            for i in reversed(range(1, last + 1)):
                zh0 = stack.pop()
                with zipfile.ZipFile(buffer, 'a') as zh:
                    zh.comment = zh0.comment
                    for info in zh0.infolist():
                        if filters and i == last:
                            if _open_archive_path_filter(info.filename, filters):
                                filtered = True
                                continue

                        try:
                            zh.getinfo(info.filename)
                        except KeyError:
                            pass
                        else:
                            continue

                        zh.writestr(info, zh0.read(info),
                                    compress_type=info.compress_type,
                                    compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9,
                                    )

                if filters and not any(f == '' for f in filters) and not filtered:
                    raise KeyError('paths to filter do not exist')

                if i == 1:
                    break

                # writer to another buffer for the parent zip
                buffer2 = io.BytesIO()
                with zipfile.ZipFile(buffer2, 'w') as zh:
                    zh.writestr(localpaths[i - 1], buffer.getvalue(), compress_type=zipfile.ZIP_STORED)
                buffer.close()
                buffer = buffer2

                # pop a file handler
                stack.pop()

            # write to the outermost zip
            # use 'r+b' as 'wb' causes PermissionError for hidden file in Windows
            buffer.seek(0)
            with open(localpaths[0], 'r+b') as fw, buffer as fr:
                fw.truncate()
                for chunk in iter(functools.partial(fr.read, 8192), b''):
                    fw.write(chunk)
    finally:
        for fh in reversed(stack):
            fh.close()


def get_breadcrumbs(paths, base='', topname='.'):
    """Generate (label, subpath, sep, is_last) tuples.
    """
    base = base.rstrip('/') + '/'
    paths = paths.copy()
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
        return action not in {
            'token', 'lock', 'unlock',
            'mkdir', 'mkzip', 'save', 'delete', 'move', 'copy',
            'backup', 'unbackup', 'cache', 'check',
        }

    if perm == 'view':
        return action in {'view', 'info', 'source', 'download', 'static'}

    return False


def handle_directory_listing(localpaths, zh=None, redirect_slash=True, format=None):
    """List contents in a directory.

    Args:
        localpaths: [path-to-zip-file, subpath1, subpath2, ...]
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

        with nullcontext(zh) if zh else open_archive_path(localpaths) as zh:
            subentries = util.fs.zip_listdir(zh, localpaths[-1])

    else:
        # disallow cache to reflect any content file change
        stats = os.stat(localpaths[0])
        headers = {
            'Cache-Control': 'no-store',
            'Last-Modified': http_date(stats.st_mtime),
        }

        subentries = util.fs.listdir(localpaths[0])

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
        localpaths: [path-to-zip-file, subpath1, subpath2, ...]
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
            with open_archive_path(localpaths) as zh:
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
        localpaths: [path-to-zip-file, subpath1, subpath2, ...]
        zh: an opened zipfile.ZipFile object for faster reading
    """
    if len(localpaths) > 1:
        if zh:
            context = nullcontext(zh)
        else:
            context = open_archive_path(localpaths)
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
        return get_archive_path(self.path)

    @cached_property
    def localpath(self):
        """Corresponding filesystem path of the requested path."""
        return get_localpath(self.path)

    @cached_property
    def localpaths(self):
        """Like localpath, but with ZIP subpaths resolved."""
        paths = self.paths.copy()
        paths[0] = get_localpath(paths[0])
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

    - Verify POST method.
    - Provide a default return value.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        format = request.format

        if request.method != 'POST':
            abort(405, valid_methods=['POST'])

        rv = func(*args, **kwargs)

        if rv is not None:
            return rv

        if format:
            return http_response('Command run successfully.', format=format)

        return http_response(status=204)

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


def handle_action_renaming(func):
    """A decorator function that helps handling a move/copy action.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        localpaths = request.localpaths

        if len(localpaths) > 1:
            with open_archive_path(localpaths) as zh:
                if not util.fs.zip_has(zh, localpaths[-1]):
                    abort(404, 'Source does not exist.')
        else:
            if not os.path.lexists(localpaths[0]):
                abort(404, 'Source does not exist.')

        target = request.values.get('target')

        if target is None:
            abort(400, 'Target is not specified.')

        targetpaths = get_archive_path(target)
        targetpaths[0] = get_localpath(targetpaths[0])

        if len(targetpaths) > 1:
            with open_archive_path(targetpaths) as zh:
                # target is a file
                if util.fs.zip_has(zh, targetpaths[-1], type='file'):
                    abort(400, 'Found something at target.')

                # target is a directory, treat as to target/<basename>
                if util.fs.zip_has(zh, targetpaths[-1], type='dir'):
                    targetpaths[-1] = targetpaths[-1] + ('/' if targetpaths[-1] else '') + os.path.basename(localpaths[-1])

                    # recheck if target exists
                    if util.fs.zip_has(zh, targetpaths[-1], type='any'):
                        abort(400, 'Found identical entry under the target directory.')
        else:
            if os.path.lexists(targetpaths[0]):
                if os.path.isdir(targetpaths[0]):
                    # target is an existing directory, treat as to target/<basename>
                    targetpaths[0] = os.path.join(targetpaths[0], os.path.basename(localpaths[-1]))

                    # recheck if target exists
                    if os.path.lexists(targetpaths[0]):
                        abort(400, 'Found identical entry under the target directory.')
                else:
                    abort(400, 'Found something at target.')

        return func(*args, sourcepaths=localpaths, targetpaths=targetpaths, **kwargs)

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
        with open_archive_path(localpaths) as zh:
            # List directory only when URL suffixed with "/", as it's not a
            # common operation, and it's costy to check for directory existence
            # in a ZIP.
            if request.path.endswith('/'):
                try:
                    return handle_directory_listing(localpaths, zh, redirect_slash=False)
                except util.fs.ZipDirNotFoundError:
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
        with open_archive_path(localpaths) as zh:
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
        streaming = False
        with open_archive_path(localpaths) as zh:
            try:
                zh.getinfo(localpaths[-1])
            except KeyError:
                base = localpaths[-1] + '/' if localpaths[-1] else ''
                infos = [i for i in zh.infolist() if i.filename.startswith(base)]

                # not exist
                if base and not len(infos):
                    abort(404)

                # directory (explicit or implicit): stream as ZIP
                streaming = True
                filename = (localpaths[-1] or os.path.basename(localpaths[-2])) + '.zip'
                mimetype, _ = mimetypes.guess_type(filename)
                cut = len(base)

                # prepare paths to output
                filter = set(filter)
                filter_d = {f + '/' for f in filter}
                paths = []
                for info in infos:
                    arcname = info.filename
                    subpath = info.filename[cut:]

                    # exclude the directory itself
                    if not arcname:
                        continue

                    # apply the filter
                    if filter:
                        if subpath not in filter:
                            if not any(subpath.startswith(f) for f in filter_d):
                                continue

                    paths.append((arcname, subpath))
            else:
                filename = os.path.basename(request.localrealpath)
                response = zip_static_file(zh, localpaths[-1], mimetype=request.localmimetype)

        if streaming:
            def gen():
                zs = util.fs.ZipStream()
                with open_archive_path(localpaths) as zh,\
                     zipfile.ZipFile(zs, 'w') as zf:
                    for arcname, subpath in paths:
                        info = zh.getinfo(arcname)
                        with zh.open(info) as ih:
                            info.filename = subpath
                            with zf.open(info, 'w') as oh:
                                for chunk in iter(lambda: ih.read(8192), b''):
                                    oh.write(chunk)
                                    yield zs.get()
                yield zs.get()

            response = Response(gen(), mimetype=mimetype)
            response.headers.set('Cache-Control', 'no-store')
    else:
        if os.path.isdir(localpaths[0]):
            filename = os.path.basename(request.localrealpath) + '.zip'
            mimetype, _ = mimetypes.guess_type(filename)

            # prepare paths to output
            filter = {os.path.normcase(os.path.join(localpaths[0], f)) for f in filter}
            filter_d = {os.path.join(f, '') for f in filter}
            cut = len(os.path.join(localpaths[0], ''))
            paths = []
            for root, dirs, files in os.walk(localpaths[0]):
                for file in dirs + files:
                    file = os.path.join(root, file)

                    # apply the filter
                    if filter:
                        file_nc = os.path.normcase(file)
                        if file_nc not in filter:
                            if not any(file_nc.startswith(f) for f in filter_d):
                                continue

                    subpath = file[cut:]
                    if os.path.isdir(file):
                        subpath += '/'
                    paths.append((file, subpath))

            def gen():
                zs = util.fs.ZipStream()
                with zipfile.ZipFile(zs, 'w') as zf:
                    for file, subpath in paths:
                        zinfo = zipfile.ZipInfo.from_file(file, subpath)
                        if zinfo.is_dir():
                            zf.writestr(zinfo, b'')
                            yield zs.get()
                        else:
                            with open(file, 'rb') as ih, zf.open(zinfo, 'w') as oh:
                                for chunk in iter(lambda: ih.read(8192), b''):
                                    oh.write(chunk)
                                    yield zs.get()
                yield zs.get()

            response = Response(gen(), mimetype=mimetype)
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

    if not format:
        abort(400, 'Action not supported.')

    localpaths = request.localpaths
    mimetype = request.localmimetype

    if len(localpaths) > 1:
        with open_archive_path(localpaths) as zh:
            info = util.fs.zip_file_info(zh, localpaths[-1], check_implicit_dir=True)
    else:
        info = util.fs.file_info(localpaths[0])

    data = {
        'name': info.name,
        'type': info.type,
        'size': info.size,
        'last_modified': info.last_modified,
        'mime': mimetype,
    }
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
        except util.fs.ZipDirNotFoundError:
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
        with open_archive_path(localpaths) as zh:
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
        with open_archive_path(localpaths) as zh:
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

    if format:
        return http_response('Command run successfully.', format=format)

    return http_response(status=204)


def action_browse():
    """Open a file or directory in the file browser."""
    format = request.format

    if not is_local_access():
        abort(400, 'Command can only run on local device.')

    localpath = request.localpath

    if not os.path.lexists(localpath):
        abort(404, 'File does not exist.')

    util.fs.view_in_explorer(localpath)

    if format:
        return http_response('Command run successfully.', format=format)

    return http_response(status=204)


def action_config():
    """Show server config."""
    format = request.format

    if not format:
        abort(400, 'Action not supported.')

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
        abort(400, f'Unable to persist lock "{name}".')

    if id:
        try:
            lock.extend()
        except wsb_host.LockExtendNotFoundError:
            # Lock file gone in this short interval. Try acquire.
            pass
        except wsb_host.LockExtendError:
            abort(500, f'Unable to extend lock "{name}".')
        else:
            return http_response(lock.id, format=request.format)

    try:
        lock.acquire(timeout=timeout)
    except wsb_host.LockTimeoutError:
        abort(503, f'Unable to acquire lock "{name}".', retry_after=60)
    except wsb_host.LockRegenerateError:
        abort(500, f'Unable to regenerate stale lock "{name}".')
    except wsb_host.LockGenerateError:
        abort(500, f'Unable to create lock "{name}".')

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
        abort(400, f'Unable to persist lock "{name}".')

    try:
        lock.release()
    except wsb_host.LockReleaseNotFoundError:
        pass
    except wsb_host.LockReleaseError:
        abort(500, f'Unable to remove lock "{name}".')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_mkdir():
    """Create a directory."""
    localpaths = request.localpaths

    if len(localpaths) > 1:
        try:
            zh = None
            with open_archive_path(localpaths) as zh0:
                if util.fs.zip_has(zh0, localpaths[-1], type='file'):
                    abort(400, 'Found a non-directory here.')

                # skip if the folder already exists
                if util.fs.zip_has(zh0, localpaths[-1], type='dir'):
                    return

                # append for a non-nested zip
                if len(localpaths) == 2:
                    zh = zipfile.ZipFile(localpaths[0], 'a')

            if zh is None:
                zh = open_archive_path(localpaths, 'w')

            with zh as zh:
                info = zipfile.ZipInfo(localpaths[-1] + '/', time.localtime())
                zh.writestr(info, b'', compress_type=zipfile.ZIP_STORED)
        except HTTPException:
            raise
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to create a directory here.')

    else:
        localpath = localpaths[0]

        if os.path.lexists(localpath) and not os.path.isdir(localpath):
            abort(400, 'Found a non-directory here.')

        try:
            os.makedirs(localpath, exist_ok=True)
        except OSError:
            traceback.print_exc()
            abort(500, 'Unable to create a directory here.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_mkzip():
    """Create a zip file."""
    localpaths = request.localpaths

    if len(localpaths) > 1:
        try:
            zh = None
            with open_archive_path(localpaths) as zh0:
                if util.fs.zip_has(zh0, localpaths[-1], type='dir'):
                    abort(400, 'Found a non-file here.')

                # append for a nonexistent path in a non-nested zip
                if len(localpaths) == 2:
                    if not util.fs.zip_has(zh0, localpaths[-1], type='file'):
                        zh = zipfile.ZipFile(localpaths[0], 'a')

            if zh is None:
                zh = open_archive_path(localpaths, 'w')

            with zh as zh:
                info = zipfile.ZipInfo(localpaths[-1], time.localtime())
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w'):
                    pass
                zh.writestr(info, buf.getvalue(), compress_type=zipfile.ZIP_STORED)
        except HTTPException:
            raise
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to write to this ZIP file.')

    else:
        localpath = localpaths[0]

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            abort(400, 'Found a non-file here.')

        try:
            os.makedirs(os.path.dirname(localpath), exist_ok=True)
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to write to this path.')

        try:
            with zipfile.ZipFile(localpath, 'w'):
                pass
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to write to this file.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_save():
    """Write a file with provided text or uploaded stream."""
    localpaths = request.localpaths

    if len(localpaths) > 1:
        try:
            zh = None
            with open_archive_path(localpaths) as zh0:
                if util.fs.zip_has(zh0, localpaths[-1], type='dir'):
                    abort(400, 'Found a non-file here.')

                # append for a nonexistent path in a non-nested zip
                if len(localpaths) == 2:
                    if not util.fs.zip_has(zh0, localpaths[-1], type='file'):
                        zh = zipfile.ZipFile(localpaths[0], 'a')

            if zh is None:
                zh = open_archive_path(localpaths, 'w')

            with zh as zh:
                info = zipfile.ZipInfo(localpaths[-1], time.localtime())
                file = request.files.get('upload')
                if file is not None:
                    with zh.open(info, 'w', force_zip64=True) as fh:
                        stream = file.stream
                        for chunk in iter(functools.partial(stream.read, 8192), b''):
                            fh.write(chunk)
                else:
                    bytes_ = request.values.get('text', '').encode('ISO-8859-1')
                    zh.writestr(info, bytes_, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        except HTTPException:
            raise
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to write to this ZIP file.')

    else:
        localpath = localpaths[0]

        if os.path.lexists(localpath) and not os.path.isfile(localpath):
            abort(400, 'Found a non-file here.')

        try:
            os.makedirs(os.path.dirname(localpath), exist_ok=True)
        except OSError:
            traceback.print_exc()
            abort(500, 'Unable to write to this path.')

        try:
            file = request.files.get('upload')
            if file is not None:
                file.save(localpath)
            else:
                bytes_ = request.values.get('text', '').encode('ISO-8859-1')
                with open(localpath, 'wb') as fh:
                    fh.write(bytes_)
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to write to this file.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
def action_delete():
    """Delete a file or directory."""
    localpaths = request.localpaths

    if len(localpaths) > 1:
        try:
            with open_archive_path(localpaths, 'w', [localpaths[-1]]):
                pass
        except KeyError:
            # fail since nothing is deleted
            abort(404, 'Entry does not exist in this ZIP file.')
        except Exception:
            traceback.print_exc()
            abort(500, 'Unable to write to this ZIP file.')

    else:
        localpath = localpaths[0]

        if not os.path.lexists(localpath):
            abort(404, 'File does not exist.')

        if util.fs.file_is_link(localpath):
            try:
                os.remove(localpath)
            except OSError:
                traceback.print_exc()
                abort(500, 'Unable to delete this link.')
        elif os.path.isfile(localpath):
            try:
                os.remove(localpath)
            except OSError:
                traceback.print_exc()
                abort(500, 'Unable to delete this file.')
        elif os.path.isdir(localpath):
            try:
                shutil.rmtree(localpath)
            except OSError:
                traceback.print_exc()
                abort(500, 'Unable to delete this directory.')
        else:
            # this should not happen
            abort(500, 'Unable to handle this path.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
@handle_action_renaming
def action_move(sourcepaths, targetpaths):
    """Move a file or directory."""
    try:
        if len(sourcepaths) == 1:
            if len(targetpaths) == 1:
                try:
                    os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                except OSError:
                    traceback.print_exc()
                    abort(500, 'Unable to move to this path.')

                shutil.move(sourcepaths[0], targetpaths[0])

            else:
                # Moving a file into a zip is like moving across disk,
                # which makes little sense. Additionally, moving a
                # symlink/junction should rename the entry and cannot be
                # implemented as copying-deleting. Forbid such operation to
                # prevent a confusion.
                abort(400, 'Unable to move across a zip.')

        elif len(sourcepaths) > 1:
            if len(targetpaths) == 1:
                # Moving from zip to disk is like moving across disk, which
                # makes little sense.
                abort(400, 'Unable to move across a zip.')

            else:
                with open_archive_path(sourcepaths) as zh:
                    try:
                        zh.getinfo(sourcepaths[-1])
                    except KeyError:
                        base = sourcepaths[-1] + '/'
                        entries = [e for e in zh.namelist() if e.startswith(base)]
                    else:
                        entries = [sourcepaths[-1]]

                    with open_archive_path(targetpaths, 'w') as zh2:
                        cut = len(sourcepaths[-1])
                        for entry in entries:
                            info = zh.getinfo(entry)
                            info.filename = targetpaths[-1] + entry[cut:]
                            zh2.writestr(info, zh.read(entry),
                                         compress_type=info.compress_type,
                                         compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9,
                                         )

                with open_archive_path(sourcepaths, 'w', entries):
                    pass

    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        abort(500, 'Unable to move to the target.')


@handle_action_advanced
@handle_action_token
@handle_action_writing
@handle_action_renaming
def action_copy(sourcepaths, targetpaths):
    """Copy a file or directory."""
    # Copying a symlink/junction means copying the real file/directory.
    # It makes no sense if the symlink/junction is broken.
    if not os.path.exists(sourcepaths[0]):
        abort(404, 'Source does not exist.')

    try:
        if len(sourcepaths) == 1:
            if len(targetpaths) == 1:
                try:
                    os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                except OSError:
                    traceback.print_exc()
                    abort(500, 'Unable to copy to this path.')

                try:
                    shutil.copytree(sourcepaths[0], targetpaths[0])
                except NotADirectoryError:
                    shutil.copy2(sourcepaths[0], targetpaths[0])
                except shutil.Error:
                    traceback.print_exc()
                    abort(500, 'Fail to copy some files.')

            else:
                error = False
                with open_archive_path(targetpaths, 'w') as zh:
                    try:
                        util.fs.zip_compress(zh, sourcepaths[0], targetpaths[-1])
                    except shutil.Error:
                        traceback.print_exc()
                        error = True
                if error:
                    abort(500, 'Fail to copy some files.')

        elif len(sourcepaths) > 1:
            if len(targetpaths) == 1:
                try:
                    os.makedirs(os.path.dirname(targetpaths[0]), exist_ok=True)
                except OSError:
                    traceback.print_exc()
                    abort(500, 'Unable to copy to this path.')

                with open_archive_path(sourcepaths) as zh:
                    util.fs.zip_extract(zh, targetpaths[0], sourcepaths[-1])

            else:
                with open_archive_path(sourcepaths) as zh:
                    try:
                        zh.getinfo(sourcepaths[-1])
                    except KeyError:
                        entries = [e for e in zh.namelist() if e.startswith(sourcepaths[-1] + '/')]
                    else:
                        entries = [sourcepaths[-1]]

                    with open_archive_path(targetpaths, 'w') as zh2:
                        cut = len(sourcepaths[-1])
                        for entry in entries:
                            info = zh.getinfo(entry)
                            info.filename = targetpaths[-1] + entry[cut:]
                            zh2.writestr(info, zh.read(entry),
                                         compress_type=info.compress_type,
                                         compresslevel=None if info.compress_type == zipfile.ZIP_STORED else 9,
                                         )

    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        abort(500, 'Unable to copy to the target.')


@handle_action_advanced
@handle_action_token
def action_backup():
    """Bakup file or directory."""
    format = request.format

    if not format:
        abort(400, 'Action not supported.')

    localpaths = request.localpaths

    if len(localpaths) > 1:
        abort(400, 'Unable to backup inside a zip file.')

    ts = request.values.get('ts') or util.datetime_to_id()
    note = request.values.get('note')
    move = request.values.get('move', default=False, type=bool)

    host.init_backup(ts, note=note)
    try:
        host.auto_backup(localpaths[0], move=move)
        return http_response(os.path.basename(host._backup_dir), format=request.format)
    finally:
        host.init_backup(False)


@handle_action_advanced
@handle_action_token
def action_unbackup():
    """Remove a backup."""
    format = request.format

    if not format:
        abort(400, 'Action not supported.')

    ts = request.values.get('ts') or util.datetime_to_id()
    note = request.values.get('note')

    host.init_backup(ts, note=note)
    try:
        host.unbackup(host._backup_dir)
        return http_response(os.path.basename(host._backup_dir), format=request.format)
    finally:
        host.init_backup(False)


@handle_action_token
def action_cache():
    """Invoke the cacher."""
    format = request.format

    kwargs = {
        'book_ids': request.values.getlist('book'),
        'item_ids': request.values.getlist('item'),
        'no_lock': request.values.get('no_lock', default=False, type=bool),
        'no_backup': request.values.get('no_backup', default=False, type=bool),
        'fulltext': request.values.get('fulltext', default=False, type=bool),
        'inclusive_frames': request.values.get('inclusive_frames', default=False, type=bool),
        'recreate': request.values.get('recreate', default=False, type=bool),
        'static_site': request.values.get('static_site', default=False, type=bool),
        'static_index': request.values.get('static_index', default=False, type=bool),
        'rss_root': request.values.get('rss_root'),
        'rss_item_count': request.values.get('rss_item_count', default=50, type=int),
        'locale': request.values.get('locale'),
    }

    headers = {
        'Cache-Control': 'no-store',
    }
    root = host.root
    config = host.config

    if format == 'sse':
        def gen():
            for info in wsb_cache.generate(root, config=config, **kwargs):
                data = {
                    'type': info.type,
                    'msg': info.msg,
                }

                yield json.dumps(data, ensure_ascii=False)

        return http_response(gen(), headers=headers, format=format)

    elif format:
        abort(400, 'Action not supported.')

    def gen():
        yield from wsb_cache.generate(root, config=config, **kwargs)

    stream = stream_template('cli.html',
                             title='Indexing...',
                             messages=gen(),
                             debug=False,
                             )

    return Response(stream, headers=headers)


@handle_action_token
def action_check():
    """Invoke the checker."""
    format = request.format

    kwargs = {
        'book_ids': request.values.getlist('book'),
        'no_lock': request.values.get('no_lock', default=False, type=bool),
        'no_backup': request.values.get('no_backup', default=False, type=bool),
        'resolve_invalid_id': request.values.get('resolve_invalid_id', default=False, type=bool),
        'resolve_missing_index': request.values.get('resolve_missing_index', default=False, type=bool),
        'resolve_missing_index_file': request.values.get('resolve_missing_index_file', default=False, type=bool),
        'resolve_missing_date': request.values.get('resolve_missing_date', default=False, type=bool),
        'resolve_older_mtime': request.values.get('resolve_older_mtime', default=False, type=bool),
        'resolve_toc_unreachable': request.values.get('resolve_toc_unreachable', default=False, type=bool),
        'resolve_toc_invalid': request.values.get('resolve_toc_invalid', default=False, type=bool),
        'resolve_toc_empty_subtree': request.values.get('resolve_toc_empty_subtree', default=False, type=bool),
        'resolve_unindexed_files': request.values.get('resolve_unindexed_files', default=False, type=bool),
        'resolve_absolute_icon': request.values.get('resolve_absolute_icon', default=False, type=bool),
        'resolve_unused_icon': request.values.get('resolve_unused_icon', default=False, type=bool),
    }

    headers = {
        'Cache-Control': 'no-store',
    }
    root = host.root
    config = host.config

    if format == 'sse':
        def gen():
            for info in wsb_check.run(root, config=config, **kwargs):
                data = {
                    'type': info.type,
                    'msg': info.msg,
                }

                yield json.dumps(data, ensure_ascii=False)

        return http_response(gen(), headers=headers, format=format)

    elif format:
        abort(400, 'Action not supported.')

    def gen():
        yield from wsb_check.run(root, config=config, **kwargs)

    stream = stream_template('cli.html',
                             title='Indexing...',
                             messages=gen(),
                             debug=False,
                             )

    return Response(stream, headers=headers)


@bp.before_request
def handle_before_request():
    # handle authorization
    try:
        auth_config = host.config['auth']
    except KeyError:
        # auth not required
        return

    perm = get_permission(request.authorization, auth_config)
    if not verify_authorization(perm, request.action):
        auth = WWWAuthenticate()
        auth.set_basic(host.config['app']['name'])
        abort(401, 'You are not authorized.', www_authenticate=auth)


@bp.route('/', methods=['GET', 'HEAD', 'POST'])
@bp.route('/<path:filepath>', methods=['GET', 'HEAD', 'POST'])
def handle_request(filepath=''):
    """Handle an HTTP request (HEAD, GET, POST).
    """
    try:
        handler = globals().get(f'action_{request.action}') or action_unknown
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
        response.data = json.dumps({
            'error': {
                'status': exc.code,
                'message': exc.description,
            },
        })
        response.content_type = 'application/json'
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
        'get_breadcrumbs': get_breadcrumbs,
        'format_filesize': util.format_filesize,
        'quote_path': quote_path,
        'static_url': static_url,
        'i18n': _host.get_i18n(_host.config['app']['locale']),
    })

    return app
