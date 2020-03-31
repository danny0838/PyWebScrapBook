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
import hashlib
import json
from urllib.parse import urlsplit, urlunsplit, urljoin, quote, unquote, parse_qs
from pathlib import Path
from zlib import adler32

# dependency
from flask import Flask
from flask import request, Response, redirect, abort, render_template, send_from_directory, send_file, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.http import is_resource_modified
from werkzeug.http import http_date
import jinja2
import commonmark

# this package
from . import *
from . import __version__
from . import Config
from . import util

try:
    from time import time_ns
except ImportError:
    from .lib.shim.time import time_ns


def make_app(root=".", config=None):
    if not config:
        config = Config()
        config.load(root)

    # runtime variables
    runtime = {}
    runtime['root'] = config['app']['root']
    if not os.path.isabs(runtime['root']):
        runtime['root'] = os.path.abspath(os.path.join(root, runtime['root']))
    runtime['name'] = config['app']['name']

    # add path for themes
    runtime['themes'] = [
        os.path.join(runtime['root'], WSB_DIR, 'themes', config['app']['theme']),
        os.path.join(os.path.dirname(__file__), 'themes', config['app']['theme']),
        ]
    runtime['statics'] = [os.path.join(t, 'static') for t in runtime['themes']]
    runtime['templates'] = [os.path.join(t, 'templates') for t in runtime['themes']]

    # init token_handler
    token_handler = util.TokenHandler(os.path.join(runtime['root'], WSB_DIR, 'server', 'token'))

    # init debugging logger
    runtime['log'] = os.path.join(runtime['root'], WSB_DIR, 'server', 'logs', 'debug.log')

    # main app instance
    app = Flask(__name__, root_path=runtime['root'])

    xheaders = {
            'x_for': config['app'].getint('allowed_x_for'),
            'x_proto': config['app'].getint('allowed_x_proto'),
            'x_host': config['app'].getint('allowed_x_host'),
            'x_port': config['app'].getint('allowed_x_port'),
            'x_prefix': config['app'].getint('allowed_x_prefix'),
            }

    if any(v for v in xheaders.values()):
        app.wsgi_app = ProxyFix(app.wsgi_app, **xheaders)

    app.jinja_loader = jinja2.FileSystemLoader(runtime['templates'])
    app.jinja_env.globals.update({
            'os': os,
            'time': time,
            'util': util,
            })


    def static_file(filepath, root=None, mimetype=None):
        """Wrap send_file for customized behaviors.
        """
        result = send_from_directory(root or runtime['root'], filepath, mimetype=mimetype)
        headers = {
            'Cache-Control': 'no-cache',
            'Accept-Ranges': 'bytes',
            }
        return result, headers


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
            return http_error(400, 'Output format "{}" is not supported.'.format(format), format=format)

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
        server_host = request.host
        client_host = request.remote_addr
        return util.is_localhost(server_host) or util.is_localhost(client_host) or server_host == client_host


    def handle_authorization(action, format=None):
        """Check if authorized or not.

        Return None if authorization passed, otherwise the header and body for authorization.
        """
        def get_permission():
            if not len(config.subsections.get('auth', {})):
                return 'all'

            auth = request.authorization or {}
            user = auth.get('username') or ''
            pw = auth.get('password') or ''

            for _, entry in config.subsections['auth'].items():
                entry_user = entry.get('user', '')
                entry_pw = entry.get('pw', '')
                entry_pw_salt = entry.get('pw_salt', '')
                entry_pw_type = entry.get('pw_type', '')
                entry_permission = entry.get('permission', 'all')
                if (user == entry_user and
                        util.encrypt(pw, entry_pw_salt, entry_pw_type) == entry_pw):
                    return entry_permission

            return ''

        def check_permission(permission):
            if permission == 'all':
                return True

            elif permission == 'read':
                if action in ('token', 'lock', 'unlock', 'mkdir', 'save', 'delete', 'move', 'copy'):
                    return False
                else:
                    return True

            elif permission == 'view':
                if action in ('view', 'source', 'static'):
                    return True
                else:
                    return False

            else:
                return False

        perm = get_permission()

        if not check_permission(perm):
            response = http_error(401, "You are not authorized.", format=format)
            response.www_authenticate.set_basic("Authentication required.")
            return response


    def handle_directory_listing(localpath, recursive=False, format=None):
        """List contents in a directory.
        """
        # ensure directory has trailing '/'
        pathname = request.path
        if not pathname.endswith('/'):
            parts = urlsplit(request.url)
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
        headers['Last-Modified'] = http_date(stats.st_mtime)

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

            return http_response(gen(), format=format, headers=headers)

        elif format == 'json':
            data = []
            for entry in subentries:
                data.append({
                        'name': entry.name,
                        'type': entry.type,
                        'size': entry.size,
                        'last_modified': entry.last_modified,
                        })
            return http_response(data, format=format, headers=headers)

        body = render_template('index.html',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=request.script_root,
                path=request.path,
                subarchivepath=None,
                subentries=subentries,
                )

        return http_response(body, format=format, headers=headers)


    def handle_zip_directory_listing(zip, archivefile, subarchivepath):
        """List contents in a directory.
        """
        # ensure directory has trailing '/'
        pathname = request.path
        if not pathname.endswith('/'):
            parts = urlsplit(request.url)
            new_parts = (parts[0], parts[1], quote(pathname) + '/', parts[3], parts[4])
            new_url = urlunsplit(new_parts)
            return redirect(new_url)

        stats = os.lstat(archivefile)
        last_modified = http_date(stats.st_mtime)
        etag = "%s-%s-%s" % (
            stats.st_mtime,
            stats.st_size,
            adler32(archivefile.encode("utf-8")) & 0xFFFFFFFF,
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

        subentries = util.zip_listdir(zip, subarchivepath)

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


    def handle_subarchive_path(archivefile, subarchivepath, mimetype, encoding):
        """Show content of a path in a zip file.
        """
        if not os.access(archivefile, os.R_OK):
            return http_error(403, "You do not have permission to access this file.")

        try:
            zip = zipfile.ZipFile(archivefile)
        except:
            return http_error(500, "Unable to open the ZIP file.")

        try:
            # KeyError is raised if subarchivepath does not exist
            info = zip.getinfo(subarchivepath)
        except KeyError:
            # subarchivepath does not exist
            # possibility a missing directory entry?
            return handle_zip_directory_listing(zip, archivefile, subarchivepath)

        fh = zip.open(subarchivepath, 'r')

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
        new_parts = (parts[0], parts[1], parts[2] + '!/' + quote(subpath), parts[3], parts[4])
        new_url = urlunsplit(new_parts)
        return redirect(new_url)


    def handle_markdown_output(filepath, filename):
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
            f.close()
        
        body = render_template('markdown.html',
                sitename=runtime['name'],
                is_local=is_local_access(),
                base=request.script_root,
                path=request.path,
                content=commonmark.commonmark(body),
                )

        return http_response(body, headers=headers)


    @app.route('/', methods=['GET', 'HEAD', 'POST'])
    @app.route('/<path:filepath>', methods=['GET', 'HEAD', 'POST'])
    def handle_request(filepath=''):
        """Handle an HTTP request (HEAD, GET, POST).
        """
        # replace SCRIPT_NAME with the custom if set
        if config['app']['base']:
            request.environ['SCRIPT_NAME'] = config['app']['base']

        query = request.values

        action = query.get('a', default='view')
        action = query.get('action', default=action)

        format = query.get('f')
        format = query.get('format', default=format)

        # handle authorization
        auth_result = handle_authorization(action=action, format=format)
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
                f = os.path.join(i, filepath)
                if os.path.lexists(f):
                    return static_file(filepath, root=i)
            else:
                return http_error(404)

        elif action == 'source':
            if format:
                return http_error(400, "Action not supported.", format=format)

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
                        mimetype, encoding)

            return static_file(filepath, root=runtime['root'], mimetype=mimetype)

        elif action in ('exec', 'browse'):
            if not is_local_access():
                return http_error(400, "Command can only run on local device.", format=format)

            if not os.path.lexists(localpath):
                return http_error(404, "File does not exist.", format=format)

            if action == 'browse':
                util.view_in_explorer(localpath)

            elif action == 'exec':
                util.launch(localpath)

            if format:
                return http_response('Command run successfully.', format=format)

            return http_response(status=204)

        elif action == 'token':
            return http_response(token_handler.acquire(), format=format)

        elif action == 'list':
            if not format:
                return http_error(400, "Action not supported.", format=format)

            if os.path.isdir(localpath):
                recursive = query.get('recursive', type=bool)
                return handle_directory_listing(localtargetpath, recursive=recursive, format=format)

            return http_error(400, "This is not a directory.", format=format)

        elif action == 'config':
            if not format:
                return http_error(400, "Action not supported.", format=format)

            data = config.dump_object()

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

            body = render_template('edit.html',
                    sitename=runtime['name'],
                    is_local=is_local_access(),
                    base=request.script_root,
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

            body = render_template('editx.html',
                    sitename=runtime['name'],
                    is_local=is_local_access(),
                    base=request.script_root,
                    path=request.path,
                    )

            return http_response(body, format=format)

        elif action in ('lock', 'unlock', 'mkdir', 'save', 'delete', 'move', 'copy'):
            if request.method != 'POST':
                headers = {
                    'Allow': 'POST',
                    }
                return http_error(405, 'Method "{}" not allowed.'.format(request.method), format=format, headers=headers)

            # validate and revoke token
            token = query.get('token') or ''

            if not token_handler.validate(token):
                return http_error(400, 'Invalid access token.', format=format)

            token_handler.delete(token)

            # validate localpath
            if action not in ('lock', 'unlock'):
                if os.path.abspath(localpath) == runtime['root']:
                    return http_error(403, "Unable to operate the root directory.", format=format)

            # validate targetpath
            if action in ('lock', 'unlock'):
                name = query.get('name')
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
                check_stale = query.get('chks', 300, type=int)
                check_timeout = query.get('chkt', 5, type=int)
                check_expire = time.time() + check_timeout
                check_delta = min(check_timeout, 0.1)

                while True:
                    try:
                        os.makedirs(targetpath)
                    except FileExistsError:
                        t = time.time()

                        if t >= check_expire:
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
                            bytes = query.get('text', '').encode('ISO-8859-1')
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
                            bytes = query.get('text', '').encode('ISO-8859-1')
                            with open(localpath, 'wb') as f:
                                f.write(bytes)
                                f.close()
                    except:
                        traceback.print_exc()
                        return http_error(500, "Unable to write to this file.", format=format)

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

            elif action == 'move':
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

                ta, tsa = get_archive_path(target, targetpath)
                if ta:
                    return http_error(400, "Move target is inside an archive file.", format=format)

                os.makedirs(os.path.dirname(targetpath), exist_ok=True)

                try:
                    os.rename(localpath, targetpath)
                except:
                    traceback.print_exc()
                    return http_error(500, 'Unable to move to target "{}".'.format(target), format=format)

            elif action == 'copy':
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

            return http_response(status=204)

        # "view" or undefined actions
        elif action == 'view':
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
                return handle_directory_listing(localtargetpath)

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
                return static_file(filepath, root=runtime['root'], mimetype=mimetype)

            # handle sub-archive path
            elif archivefile:
                return handle_subarchive_path(os.path.realpath(archivefile), subarchivepath,
                        mimetype, encoding)

            # probably 404 not found here
            return static_file(filepath, mimetype=mimetype)

        # unknown action
        else:
            return http_error(400, "Action not supported.", format=format)


    def debug(*msg):
        """Quick dirty logging for testing purpose.
        """
        os.makedirs(os.path.dirname(runtime['log']), exist_ok=True)
        with open(runtime['log'], 'a', encoding='UTF-8') as f:
            f.write(' '.join(str(s) for s in msg))
            f.write('\n')
            f.close()

    return app
