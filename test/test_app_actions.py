# @FIXME: Some cases have an unclosed file issue. Although adding
#     buffered=True temporarily suppresses it, a further investigation
#     for a possible leak of the source code is pending.
from unittest import mock
import unittest
import sys
import os
import io
import shutil
import zipfile
import json
from functools import partial
from flask import request, Response
import webscrapbook
from webscrapbook import WSB_DIR, WSB_LOCAL_CONFIG
from webscrapbook.app import make_app
from webscrapbook.util import make_hashable, frozendict

root_dir = os.path.abspath(os.path.dirname(__file__))
server_root = os.path.join(root_dir, 'test_app_actions')

mocking = None
app = None

def setUpModule():
    # mock out WSB_USER_CONFIG
    global mocking
    mocking = mock.patch('webscrapbook.WSB_USER_CONFIG', server_root)
    mocking.start()

    # init app
    global app
    app = make_app(server_root)
    app.testing = True

def tearDownModule():
    # purge WSB_DIR
    try:
        shutil.rmtree(os.path.join(server_root, WSB_DIR, 'server'))
    except FileNotFoundError:
        pass

    # stop mock
    mocking.stop()

def token(c):
    return c.get('/', query_string={'a': 'token'}).data.decode('UTF-8')

class TestView(unittest.TestCase):
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check1(self, mock_error):
        with app.test_client() as c, mock.patch('builtins.open', side_effect=PermissionError('Forbidden')):
            r = c.get('/index.html')
            mock_error.assert_called_once_with(403, format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check2(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass
            with app.test_client() as c, mock.patch('zipfile.ZipFile', side_effect=PermissionError('Forbidden')):
                r = c.get('/archive.zip!/')
                mock_error.assert_called_once_with(403, format=None)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_directory(self, mock_template):
        with app.test_client() as c:
            r = c.get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/')

            r = c.get('/subdir/')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            self.assertEqual(r.headers['Cache-Control'], 'no-store')
            mock_template.call_args[1]['subentries'] = set(mock_template.call_args[1]['subentries'])
            mock_template.assert_called_once_with('index.html',
                sitename='WebScrapBook',
                is_local=True,
                base='',
                path='/subdir/',
                pathparts=['/subdir'],
                subentries={
                    ('file.txt', 'file', 3, os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime),
                    ('sub', 'dir', None, os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime),
                    },
                )

    def test_file(self):
        with app.test_client() as c:
            r = c.get('/index.html', buffered=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html')
            self.assertEqual(r.headers['Content-Length'], str(os.stat(os.path.join(server_root, 'index.html')).st_size))
            self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
            self.assertEqual(r.headers['Cache-Control'], 'no-cache')
            self.assertIsNotNone(r.headers['Last-Modified'])
            self.assertIsNotNone(r.headers['ETag'])
            self.assertEqual(r.data.decode('UTF-8').replace('\r\n', '\n'), """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body>Hello World! 你好</body>
</html>""")

            etag = r.headers['ETag']
            lm =  r.headers['Last-Modified']

            # 304 for etag
            r = c.get('/index.html', headers={
                'If-None-Match': etag,
                }, buffered=True)
            self.assertEqual(r.status_code, 304)

            # 304 for last-modified
            r = c.get('/index.html', headers={
                'If-Modified-Since': lm,
                }, buffered=True)
            self.assertEqual(r.status_code, 304)

            # 206 for a ranged request
            r = c.get('/index.html', headers={
                'Range': 'bytes=0-14',
                }, buffered=True)
            self.assertEqual(r.status_code, 206)
            self.assertEqual(r.data.decode('UTF-8').replace('\r\n', '\n'), '<!DOCTYPE html>')

    def test_htz(self):
        zip_filename = os.path.join(server_root, 'archive.htz')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.htz', buffered=True)
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], 'http://localhost/archive.htz!/index.html')
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_maff(self):
        zip_filename = os.path.join(server_root, 'archive.maff')
        try:
            # 1 page
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('19870101/index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.maff', buffered=True)
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], 'http://localhost/archive.maff!/19870101/index.html')

            # 0 page
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass

            with app.test_client() as c, mock.patch('webscrapbook.app.render_template', return_value='') as mock_template:
                r = c.get('/archive.maff', buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
                mock_template.assert_called_once_with('maff_index.html',
                    sitename='WebScrapBook',
                    is_local=True,
                    base='',
                    path='/archive.maff',
                    pages=[],
                    )

            # 2+ pages
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('19870101/index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')
                zh.writestr(zipfile.ZipInfo('19870201/index.html', (1987, 1, 2, 0, 0, 0)), 'Hello World! 你好嗎')

            with app.test_client() as c, mock.patch('webscrapbook.app.render_template', return_value='') as mock_template:
                r = c.get('/archive.maff', buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
                mock_template.assert_called_once_with('maff_index.html',
                    sitename='WebScrapBook',
                    is_local=True,
                    base='',
                    path='/archive.maff',
                    pages=[
                        (None, None, None, '19870101/index.html', None),
                        (None, None, None, '19870201/index.html', None),
                        ],
                    )
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_zip(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.zip', buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/x-zip-compressed')
                self.assertNotEqual(r.headers['Content-Length'], '19')
                self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_markdown(self):
        with app.test_client() as c:
            with mock.patch('webscrapbook.app.render_template', return_value='') as mock_template:
                r = c.get('/index.md')
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
                self.assertNotEqual(r.headers['Content-Length'], str(os.stat(os.path.join(server_root, 'index.md')).st_size))
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                self.assertIsNone(r.headers.get('Accept-Ranges'))
                mock_template.assert_called_once_with('markdown.html',
                    sitename='WebScrapBook',
                    is_local=True,
                    base='',
                    path='/index.md',
                    pathparts=['/index.md'],
                    content='<h2>Header</h2>\n<p>Hello 你好</p>\n',
                    )

            etag = r.headers['ETag']
            lm =  r.headers['Last-Modified']

            # 304 for etag
            r = c.get('/index.md', headers={
                'If-None-Match': etag,
                }, buffered=True)
            self.assertEqual(r.status_code, 304)

            # 304 for last-modified
            r = c.get('/index.md', headers={
                'If-Modified-Since': lm,
                }, buffered=True)
            self.assertEqual(r.status_code, 304)

    def test_meta_refresh(self):
        with app.test_client() as c:
            r = c.get('/refresh.htm')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/index.html')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.get('/nonexist')
            mock_error.assert_called_once_with(404)

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_zip_subdir(self, mock_template):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.zip!/', buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                with self.assertRaises(KeyError):
                    r.headers['Accept-Ranges']
                mock_template.call_args[1]['subentries'] = set(mock_template.call_args[1]['subentries'])
                mock_template.assert_called_once_with('index.html',
                    sitename='WebScrapBook',
                    is_local=True,
                    base='',
                    path='/archive.zip!/',
                    pathparts=['/archive.zip', ''],
                    subentries={
                        ('index.html', 'file', 19, 536428800),
                        },
                    )

                etag = r.headers['ETag']
                lm =  r.headers['Last-Modified']

                # 304 for etag
                r = c.get('/archive.zip!/', headers={
                    'If-None-Match': etag,
                    }, buffered=True)
                self.assertEqual(r.status_code, 304)

                # 304 for last-modified
                r = c.get('/archive.zip!/', headers={
                    'If-Modified-Since': lm,
                    }, buffered=True)
                self.assertEqual(r.status_code, 304)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_zip_subdir_noslash(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('subdir/', (1987, 1, 1, 0, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('subdir/index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.zip!/subdir', buffered=True)
                mock_error.assert_called_once_with(404)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_zip_subfile(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.zip!/index.html', buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/html')
                self.assertEqual(r.headers['Content-Length'], '19')
                self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                self.assertEqual(r.data.decode('UTF-8'), 'Hello World! 你好')

                etag = r.headers['ETag']
                lm =  r.headers['Last-Modified']

                # 304 for etag
                r = c.get('/archive.zip!/index.html', headers={
                    'If-None-Match': etag,
                    }, buffered=True)
                self.assertEqual(r.status_code, 304)

                # 304 for last-modified
                r = c.get('/archive.zip!/index.html', headers={
                    'If-Modified-Since': lm,
                    }, buffered=True)
                self.assertEqual(r.status_code, 304)

                # 206 for a ranged request
                r = c.get('/archive.zip!/index.html', headers={
                    'Range': 'bytes=0-11',
                    }, buffered=True)
                self.assertEqual(r.status_code, 206)
                self.assertEqual(r.data.decode('UTF-8').replace('\r\n', '\n'), 'Hello World!')
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_zip_subfile_nested(self):
        zip_filename = os.path.join(server_root, 'archive.htz')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                buf1 = io.BytesIO()
                with zipfile.ZipFile(buf1, 'w') as zh1:
                    zh1.writestr(zipfile.ZipInfo('index.html', (1987, 1, 5, 0, 0, 0)), 'Hello World')
                zh.writestr(zipfile.ZipInfo('entry1.htz', (1987, 1, 4, 0, 0, 0)), buf1.getvalue())

            with app.test_client() as c:
                r = c.get('/archive.htz!/entry1.htz')
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], 'http://localhost/archive.htz!/entry1.htz!/index.html')

                r = c.get('/archive.htz!/entry1.htz!/index.html')
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/html')
                self.assertEqual(r.headers['Content-Length'], '11')
                self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                self.assertEqual(r.data.decode('UTF-8'), 'Hello World')
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_zip_markdown(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.md', (1987, 1, 1, 0, 0, 0)), '## Header\n\nHello 你好')

            with app.test_client() as c:
                with mock.patch('webscrapbook.app.render_template', return_value='') as mock_template:
                    r = c.get('/archive.zip!/index.md', buffered=True)
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
                    self.assertNotEqual(r.headers['Content-Length'], '23')
                    self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                    self.assertIsNotNone(r.headers['Last-Modified'])
                    self.assertIsNotNone(r.headers['ETag'])
                    self.assertIsNone(r.headers.get('Accept-Ranges'))
                    mock_template.assert_called_once_with('markdown.html',
                        sitename='WebScrapBook',
                        is_local=True,
                        base='',
                        path='/archive.zip!/index.md',
                        pathparts=['/archive.zip', 'index.md'],
                        content='<h2>Header</h2>\n<p>Hello 你好</p>\n',
                        )

                etag = r.headers['ETag']
                lm =  r.headers['Last-Modified']

                # 304 for etag
                r = c.get('/archive.zip!/index.md', headers={
                    'If-None-Match': etag,
                    }, buffered=True)
                self.assertEqual(r.status_code, 304)

                # 304 for last-modified
                r = c.get('/archive.zip!/index.md', headers={
                    'If-Modified-Since': lm,
                    }, buffered=True)
                self.assertEqual(r.status_code, 304)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    # @FIXME: fix "%21" back to "!"
    def test_zip_meta_refresh(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('refresh.htm', (1987, 1, 1, 0, 0, 0)), '<meta http-equiv="refresh" content="0;url=index.html">')

            with app.test_client() as c:
                r = c.get('/archive.zip!/refresh.htm', buffered=True)
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], 'http://localhost/archive.zip%21/index.html')
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file_zip_nonexist(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist')
                mock_error.assert_called_once_with(404)

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist/')
                mock_error.assert_called_once_with(404)

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist.txt')
                mock_error.assert_called_once_with(404)

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist.txt/')
                mock_error.assert_called_once_with(404)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.ActionHandler.info', return_value='')
    def test_json(self, mock_info):
        with app.test_client() as c:
            r = c.get('/', query_string={'f': 'json'})
            mock_info.assert_called_once_with()

class TestInfo(unittest.TestCase):
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_format_check(self, mock_error):
        """Require format."""
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'info'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check(self, mock_error):
        with app.test_client() as c, mock.patch('webscrapbook.util.file_info', side_effect=PermissionError('Forbidden')):
            r = c.get('/index.html', query_string={'a': 'info', 'f': 'json'})
            mock_error.assert_called_once_with(403, format='json')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check2(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass
            with app.test_client() as c, mock.patch('webscrapbook.app.open_archive_path', side_effect=PermissionError('Forbidden')):
                r = c.get('/archive.zip!/', query_string={'a': 'info', 'f': 'json'})
                mock_error.assert_called_once_with(403, format='json')
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_directory(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'info', 'f': 'json'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {
                'success': True,
                'data': {
                    'name': 'subdir',
                    'type': 'dir',
                    'size': None,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir')).st_mtime,
                    'mime': None,
                    },
                })

            r = c.get('/subdir/', query_string={'a': 'info', 'f': 'json'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {
                'success': True,
                'data': {
                    'name': 'subdir',
                    'type': 'dir',
                    'size': None,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir')).st_mtime,
                    'mime': None,
                    },
                })

    def test_file(self):
        files = [
            {'filename': 'index.html', 'mime': 'text/html'},
            {'filename': 'index.md', 'mime': 'text/markdown'},
            {'filename': 'archive.htz', 'mime': 'application/html+zip'},
            {'filename': 'archive.maff', 'mime': 'application/x-maff'},
            {'filename': 'archive.zip', 'mime': 'application/x-zip-compressed'},
            ]

        for file in files:
            filename = file['filename']
            mime = file['mime']
            with self.subTest(filename=filename, mime=mime):
                file_path = os.path.join(server_root, filename)
                url_path = '/' + filename
                iszip = os.path.splitext(file_path)[1] in ('.zip', '.htz', '.maff')
                if iszip:
                    with zipfile.ZipFile(file_path, 'w') as zh:
                        pass
                stat = os.stat(file_path)

                try:
                    with app.test_client() as c:
                        r = c.get(url_path, query_string={'a': 'info', 'f': 'json'})
                        self.assertEqual(r.status_code, 200)
                        self.assertEqual(r.headers['Content-Type'], 'application/json')
                        self.assertEqual(r.json, {
                            'success': True,
                            'data': {
                                'name': filename,
                                'type': 'file',
                                'size': stat.st_size,
                                'last_modified': stat.st_mtime,
                                'mime': mime,
                                },
                            })
                finally:
                    if iszip:
                        try:
                            os.remove(file_path)
                        except FileNotFoundError:
                            pass

    def test_file_zip(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('explicit_dir/', (1987, 1, 1, 0, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('explicit_dir/index.html', (1987, 1, 2, 0, 0, 0)), 'Hello World! 你好')
                zh.writestr(zipfile.ZipInfo('implicit_dir/index.html', (1987, 1, 3, 0, 0, 0)), 'Hello World! 你好嗎')

                buf1 = io.BytesIO()
                with zipfile.ZipFile(buf1, 'w') as zh1:
                    zh1.writestr(zipfile.ZipInfo('index.html', (1987, 1, 5, 0, 0, 0)), 'ABC')
                zh.writestr(zipfile.ZipInfo('entry1.zip', (1987, 1, 4, 0, 0, 0)), buf1.getvalue())

            with app.test_client() as c:
                # directory
                r = c.get('/archive.zip!/explicit_dir', query_string={'a': 'info', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'explicit_dir',
                        'type': 'dir',
                        'size': None,
                        'last_modified': 536428800,
                        'mime': None,
                        },
                    })

                # directory (slash)
                r = c.get('/archive.zip!/explicit_dir/', query_string={'a': 'info', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'explicit_dir',
                        'type': 'dir',
                        'size': None,
                        'last_modified': 536428800,
                        'mime': None,
                        },
                    })

                # directory (implicit)
                r = c.get('/archive.zip!/implicit_dir', query_string={'a': 'info', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'implicit_dir',
                        'type': None,
                        'size': None,
                        'last_modified': None,
                        'mime': None,
                        },
                    })

                # directory (implicit, slash)
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'info', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'implicit_dir',
                        'type': None,
                        'size': None,
                        'last_modified': None,
                        'mime': None,
                        },
                    })

                # file
                r = c.get('/archive.zip!/explicit_dir/index.html', query_string={'a': 'info', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'index.html',
                        'type': 'file',
                        'size': 19,
                        'last_modified': 536515200,
                        'mime': 'text/html',
                        },
                    })

                # nested directory
                r = c.get('/archive.zip!/entry1.zip!/', query_string={'a': 'info', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': '',
                        'type': None,
                        'size': None,
                        'last_modified': None,
                        'mime': None,
                        },
                    })

                # nested file
                r = c.get('/archive.zip!/entry1.zip!/index.html', query_string={'a': 'info', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'index.html',
                        'type': 'file',
                        'size': 3,
                        'last_modified': 536774400,
                        'mime': 'text/html',
                        },
                    })
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'info', 'f': 'json'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {
                'success': True,
                'data': {
                    'name': 'nonexist',
                    'type': None,
                    'size': None,
                    'last_modified': None,
                    'mime': None,
                    },
                })

class TestList(unittest.TestCase):
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check1(self, mock_error):
        with app.test_client() as c, mock.patch('os.scandir', side_effect=PermissionError('Forbidden')):
            r = c.get('/subdir/', query_string={'a': 'list', 'f': 'json'})
            mock_error.assert_called_once_with(403, format='json')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check2(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass
            with app.test_client() as c, mock.patch('zipfile.ZipFile', side_effect=PermissionError('Forbidden')):
                r = c.get('/archive.zip!/', query_string={'a': 'list', 'f': 'json'})
                mock_error.assert_called_once_with(403, format='json')
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_format_check(self, mock_error):
        """Require format."""
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'list'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format=None)

    def test_directory(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'list', 'f': 'json'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            data = r.json
            self.assertTrue(data['success'])
            self.assertEqual(set(make_hashable(data['data'])), {
                frozendict({
                    'name': 'file.txt',
                    'type': 'file',
                    'size': 3,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime,
                    }),
                frozendict({
                    'name': 'sub',
                    'type': 'dir',
                    'size': None,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime,
                    }),
                })

            r = c.get('/subdir/', query_string={'a': 'list', 'f': 'json'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            data = r.json
            self.assertTrue(data['success'])
            self.assertEqual(set(make_hashable(data['data'])), {
                frozendict({
                    'name': 'file.txt',
                    'type': 'file',
                    'size': 3,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime,
                    }),
                frozendict({
                    'name': 'sub',
                    'type': 'dir',
                    'size': None,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime,
                    }),
                })

    def test_directory_recursive(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'list', 'f': 'json', 'recursive': 1})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            data = r.json
            self.assertTrue(data['success'])
            self.assertEqual(set(make_hashable(data['data'])), {
                frozendict({
                    'name': 'file.txt',
                    'type': 'file',
                    'size': 3,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime,
                    }),
                frozendict({
                    'name': 'sub',
                    'type': 'dir',
                    'size': None,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime,
                    }),
                frozendict({
                    'name': 'sub/subfile.txt',
                    'type': 'file',
                    'size': 6,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'sub', 'subfile.txt')).st_mtime,
                    }),
                })

            r = c.get('/subdir/', query_string={'a': 'list', 'f': 'json', 'recursive': 1})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            data = r.json
            self.assertTrue(data['success'])
            self.assertEqual(set(make_hashable(data['data'])), {
                frozendict({
                    'name': 'file.txt',
                    'type': 'file',
                    'size': 3,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime,
                    }),
                frozendict({
                    'name': 'sub',
                    'type': 'dir',
                    'size': None,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime,
                    }),
                frozendict({
                    'name': 'sub/subfile.txt',
                    'type': 'file',
                    'size': 6,
                    'last_modified': os.stat(os.path.join(server_root, 'subdir', 'sub', 'subfile.txt')).st_mtime,
                    }),
                })

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file(self, mock_error):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'list', 'f': 'json'})
            mock_error.assert_called_once_with(404, 'Directory does not exist.', format='json')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'list', 'f': 'json'})
            mock_error.assert_called_once_with(404, 'Directory does not exist.', format='json')

    def test_zip(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('explicit_dir/', (1987, 1, 1, 0, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('explicit_dir/index.html', (1987, 1, 2, 0, 0, 0)), 'Hello World! 你好')
                zh.writestr(zipfile.ZipInfo('explicit_dir/subdir/', (1987, 1, 2, 1, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('implicit_dir/index.html', (1987, 1, 3, 0, 0, 0)), 'Hello World! 你好嗎')
                zh.writestr(zipfile.ZipInfo('implicit_dir/subdir/index.html', (1987, 1, 3, 1, 0, 0)), 'Hello World!')

                buf1 = io.BytesIO()
                with zipfile.ZipFile(buf1, 'w') as zh1:
                    zh1.writestr(zipfile.ZipInfo('index.html', (1987, 1, 5, 0, 0, 0)), 'ABC')
                zh.writestr(zipfile.ZipInfo('entry1.zip', (1987, 1, 4, 0, 0, 0)), buf1.getvalue())

            with app.test_client() as c:
                # explicit dir (no slash)
                r = c.get('/archive.zip!/explicit_dir', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.json
                self.assertTrue(data['success'])
                self.assertEqual(set(make_hashable(data['data'])), {
                    frozendict({
                        'name': 'index.html',
                        'type': 'file',
                        'size': 19,
                        'last_modified': 536515200,
                        }),
                    frozendict({
                        'name': 'subdir',
                        'type': 'dir',
                        'size': None,
                        'last_modified': 536518800,
                        }),
                    })

                # explicit dir
                r = c.get('/archive.zip!/explicit_dir/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.json
                self.assertTrue(data['success'])
                self.assertEqual(set(make_hashable(data['data'])), {
                    frozendict({
                        'name': 'index.html',
                        'type': 'file',
                        'size': 19,
                        'last_modified': 536515200,
                        }),
                    frozendict({
                        'name': 'subdir',
                        'type': 'dir',
                        'size': None,
                        'last_modified': 536518800,
                        }),
                    })

                # implicit dir (no slash)
                r = c.get('/archive.zip!/implicit_dir', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.json
                self.assertTrue(data['success'])
                self.assertEqual(set(make_hashable(data['data'])), {
                    frozendict({
                        'name': 'index.html',
                        'type': 'file',
                        'size': 22,
                        'last_modified': 536601600,
                        }),
                    frozendict({
                        'name': 'subdir',
                        'type': 'dir',
                        'size': None,
                        'last_modified': None,
                        }),
                    })

                # implicit dir
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.json
                self.assertTrue(data['success'])
                self.assertEqual(set(make_hashable(data['data'])), {
                    frozendict({
                        'name': 'index.html',
                        'type': 'file',
                        'size': 22,
                        'last_modified': 536601600,
                        }),
                    frozendict({
                        'name': 'subdir',
                        'type': 'dir',
                        'size': None,
                        'last_modified': None,
                        }),
                    })

                # implicit dir (recursive)
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'list', 'f': 'json', 'recursive': 1})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.json
                self.assertTrue(data['success'])
                self.assertEqual(set(make_hashable(data['data'])), {
                    frozendict({
                        'name': 'index.html',
                        'type': 'file',
                        'size': 22,
                        'last_modified': 536601600,
                        }),
                    frozendict({
                        'name': 'subdir',
                        'type': 'dir',
                        'size': None,
                        'last_modified': None,
                        }),
                    frozendict({
                        'name': 'subdir/index.html',
                        'type': 'file',
                        'size': 12,
                        'last_modified': 536605200,
                        }),
                    })

                etag = r.headers['ETag']
                lm =  r.headers['Last-Modified']

                # 304 for etag
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'list', 'f': 'json'}, headers={
                    'If-None-Match': etag,
                    })
                self.assertEqual(r.status_code, 304)

                # 304 for last-modified
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'list', 'f': 'json'}, headers={
                    'If-Modified-Since': lm,
                    })
                self.assertEqual(r.status_code, 304)

                # nested directory
                r = c.get('/archive.zip!/entry1.zip!/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.json
                self.assertTrue(data['success'])
                self.assertEqual(set(make_hashable(data['data'])), {
                    frozendict({
                        'name': 'index.html',
                        'type': 'file',
                        'size': 3,
                        'last_modified': 536774400,
                        }),
                    })
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_zip_nonexist(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist', query_string={'a': 'list', 'f': 'json'})
                mock_error.assert_called_once_with(404, 'Directory does not exist.', format='json')

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist/', query_string={'a': 'list', 'f': 'json'})
                mock_error.assert_called_once_with(404, 'Directory does not exist.', format='json')

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist.txt', query_string={'a': 'list', 'f': 'json'})
                mock_error.assert_called_once_with(404, 'Directory does not exist.', format='json')

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist.txt/', query_string={'a': 'list', 'f': 'json'})
                mock_error.assert_called_once_with(404, 'Directory does not exist.', format='json')
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_sse_directory(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'list', 'f': 'sse'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
            data = r.data.decode('UTF-8')
            self.assertTrue('data: {{"name": "file.txt", "type": "file", "size": 3, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime) in data)
            self.assertTrue('data: {{"name": "sub", "type": "dir", "size": null, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime) in data)
            self.assertTrue(data.endswith('\n\nevent: complete\ndata: \n\n'))

            r = c.get('/subdir/', query_string={'a': 'list', 'f': 'sse'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
            data = r.data.decode('UTF-8')
            self.assertTrue('data: {{"name": "file.txt", "type": "file", "size": 3, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime) in data)
            self.assertTrue('data: {{"name": "sub", "type": "dir", "size": null, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime) in data)
            self.assertTrue(data.endswith('\n\nevent: complete\ndata: \n\n'))

    def test_sse_directory_recursive(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'list', 'f': 'sse', 'recursive': 1})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
            data = r.data.decode('UTF-8')
            self.assertTrue('data: {{"name": "file.txt", "type": "file", "size": 3, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime) in data)
            self.assertTrue('data: {{"name": "sub", "type": "dir", "size": null, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime) in data)
            self.assertTrue('data: {{"name": "sub/subfile.txt", "type": "file", "size": 6, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'sub', 'subfile.txt')).st_mtime) in data)
            self.assertTrue(data.endswith('\n\nevent: complete\ndata: \n\n'))

            r = c.get('/subdir/', query_string={'a': 'list', 'f': 'sse', 'recursive': 1})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
            data = r.data.decode('UTF-8')
            self.assertTrue('data: {{"name": "file.txt", "type": "file", "size": 3, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime) in data)
            self.assertTrue('data: {{"name": "sub", "type": "dir", "size": null, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime) in data)
            self.assertTrue('data: {{"name": "sub/subfile.txt", "type": "file", "size": 6, "last_modified": {}}}\n\n'.format(
                    os.stat(os.path.join(server_root, 'subdir', 'sub', 'subfile.txt')).st_mtime) in data)
            self.assertTrue(data.endswith('\n\nevent: complete\ndata: \n\n'))

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_sse_file(self, mock_error):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'list', 'f': 'sse'})
            mock_error.assert_called_once_with(404, 'Directory does not exist.', format='sse')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_sse_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'list', 'f': 'sse'})
            mock_error.assert_called_once_with(404, 'Directory does not exist.', format='sse')

    def test_sse_zip(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('explicit_dir/', (1987, 1, 1, 0, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('explicit_dir/index.html', (1987, 1, 2, 0, 0, 0)), 'Hello World! 你好')
                zh.writestr(zipfile.ZipInfo('explicit_dir/subdir/', (1987, 1, 2, 1, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('implicit_dir/index.html', (1987, 1, 3, 0, 0, 0)), 'Hello World! 你好嗎')
                zh.writestr(zipfile.ZipInfo('implicit_dir/subdir/index.html', (1987, 1, 3, 1, 0, 0)), 'Hello World!')

            with app.test_client() as c:
                # explicit dir (no slash)
                r = c.get('/archive.zip!/explicit_dir', query_string={'a': 'list', 'f': 'sse'}, buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.data.decode('UTF-8')
                self.assertTrue('data: {"name": "index.html", "type": "file", "size": 19, "last_modified": 536515200}\n\n' in data)
                self.assertTrue('data: {"name": "subdir", "type": "dir", "size": null, "last_modified": 536518800}\n\n' in data)
                self.assertTrue(data.endswith('\n\nevent: complete\ndata: \n\n'))

                # explicit dir
                r = c.get('/archive.zip!/explicit_dir/', query_string={'a': 'list', 'f': 'sse'}, buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.data.decode('UTF-8')
                self.assertTrue('data: {"name": "index.html", "type": "file", "size": 19, "last_modified": 536515200}\n\n' in data)
                self.assertTrue('data: {"name": "subdir", "type": "dir", "size": null, "last_modified": 536518800}\n\n' in data)
                self.assertTrue(data.endswith('\n\nevent: complete\ndata: \n\n'))

                # implicit dir (no slash)
                r = c.get('/archive.zip!/implicit_dir', query_string={'a': 'list', 'f': 'sse'}, buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.data.decode('UTF-8')
                self.assertTrue('data: {"name": "index.html", "type": "file", "size": 22, "last_modified": 536601600}\n\n' in data)
                self.assertTrue('data: {"name": "subdir", "type": "dir", "size": null, "last_modified": null}\n\n' in data)
                self.assertTrue(data.endswith('\n\nevent: complete\ndata: \n\n'))

                # implicit dir
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'list', 'f': 'sse'}, buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
                data = r.data.decode('UTF-8')
                self.assertTrue('data: {"name": "index.html", "type": "file", "size": 22, "last_modified": 536601600}\n\n' in data)
                self.assertTrue('data: {"name": "subdir", "type": "dir", "size": null, "last_modified": null}\n\n' in data)
                self.assertTrue(data.endswith('\n\nevent: complete\ndata: \n\n'))

                etag = r.headers['ETag']
                lm =  r.headers['Last-Modified']

                # 304 for etag
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'list', 'f': 'sse'}, headers={
                    'If-None-Match': etag,
                    })
                self.assertEqual(r.status_code, 304)

                # 304 for last-modified
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'list', 'f': 'sse'}, headers={
                    'If-Modified-Since': lm,
                    })
                self.assertEqual(r.status_code, 304)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

class TestSource(unittest.TestCase):
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_format_check(self, mock_error):
        """No format."""
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'source', 'f': 'json'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format='json')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check1(self, mock_error):
        with app.test_client() as c, mock.patch('builtins.open', side_effect=PermissionError('Forbidden')):
            r = c.get('/index.html', query_string={'a': 'source'})
            mock_error.assert_called_once_with(403, format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check2(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass
            with app.test_client() as c, mock.patch('zipfile.ZipFile', side_effect=PermissionError('Forbidden')):
                r = c.get('/archive.zip!/', query_string={'a': 'source'})
                mock_error.assert_called_once_with(403, format=None)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_file_normal(self):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'source'}, buffered=True)
            r.encoding = 'UTF-8'
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=utf-8')
            self.assertEqual(r.headers['Content-Disposition'], 'inline')
            self.assertEqual(r.headers['Content-Length'], str(os.stat(os.path.join(server_root, 'index.html')).st_size))
            self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
            self.assertEqual(r.headers['Cache-Control'], 'no-cache')
            self.assertIsNotNone(r.headers['Last-Modified'])
            self.assertIsNotNone(r.headers['ETag'])
            self.assertEqual(r.data.decode('UTF-8').replace('\r\n', '\n'), """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body>Hello World! 你好</body>
</html>""")

            etag = r.headers['ETag']
            lm =  r.headers['Last-Modified']

            # 304 for etag
            r = c.get('/index.html', query_string={'a': 'source'}, headers={
                'If-None-Match': etag,
                }, buffered=True)
            self.assertEqual(r.status_code, 304)

            # 304 for last-modified
            r = c.get('/index.html', query_string={'a': 'source'}, headers={
                'If-Modified-Since': lm,
                }, buffered=True)
            self.assertEqual(r.status_code, 304)

            # 206 for a ranged request
            r = c.get('/index.html', query_string={'a': 'source'}, headers={
                'Range': 'bytes=0-14',
                }, buffered=True)
            self.assertEqual(r.status_code, 206)
            self.assertEqual(r.data.decode('UTF-8').replace('\r\n', '\n'), '<!DOCTYPE html>')

    def test_file_markdown(self):
        with app.test_client() as c:
            r = c.get('/index.md', query_string={'a': 'source'}, buffered=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=utf-8')
            self.assertEqual(r.headers['Content-Disposition'], 'inline')
            self.assertEqual(r.headers['Content-Length'], str(os.stat(os.path.join(server_root, 'index.md')).st_size))
            self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
            self.assertEqual(r.headers['Cache-Control'], 'no-cache')
            self.assertIsNotNone(r.headers['Last-Modified'])
            self.assertIsNotNone(r.headers['ETag'])
            self.assertEqual(r.data.decode('UTF-8').replace('\r\n', '\n'), '## Header\n\nHello 你好')

            etag = r.headers['ETag']
            lm =  r.headers['Last-Modified']

            # 304 for etag
            r = c.get('/index.md', query_string={'a': 'source'}, headers={
                'If-None-Match': etag,
                }, buffered=True)
            self.assertEqual(r.status_code, 304)

            # 304 for last-modified
            r = c.get('/index.md', query_string={'a': 'source'}, headers={
                'If-Modified-Since': lm,
                }, buffered=True)
            self.assertEqual(r.status_code, 304)

            # 206 for a ranged request
            r = c.get('/index.md', query_string={'a': 'source'}, headers={
                'Range': 'bytes=0-8',
                }, buffered=True)
            self.assertEqual(r.status_code, 206)
            self.assertEqual(r.data.decode('UTF-8').replace('\r\n', '\n'), '## Header')

    def test_file_binary(self):
        zip_filename = os.path.join(server_root, 'archive.htz')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('index.html', 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.htz', query_string={'a': 'source'}, buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=utf-8')
                self.assertEqual(r.headers['Content-Disposition'], 'inline')
                self.assertEqual(r.headers['Content-Length'], str(os.stat(os.path.join(server_root, 'archive.htz')).st_size))
                self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_file_encoding(self):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'source', 'e': 'big5'}, buffered=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=big5')

            r = c.get('/index.html', query_string={'a': 'source', 'encoding': 'big5'}, buffered=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=big5')

            r = c.get('/index.html', query_string={'a': 'source', 'encoding': 'big5'}, buffered=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=big5')

            r = c.get('/index.html', query_string={'a': 'source', 'encoding': 'big5', 'e': 'gbk'}, buffered=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=big5')

            r = c.get('/index.html', query_string={'a': 'source', 'e': 'gbk', 'encoding': 'big5'}, buffered=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=big5')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'source'}, buffered=True)
            mock_error.assert_called_once_with(404)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_directory(self, mock_error):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'source'})
            mock_error.assert_called_once_with(404)

        mock_error.reset_mock()

        with app.test_client() as c:
            r = c.get('/subdir/', query_string={'a': 'source'})
            mock_error.assert_called_once_with(404)

    def test_file_zip_subfile(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('index.html', 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.zip!/index.html', query_string={'a': 'source'}, buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/plain; charset=utf-8')
                self.assertEqual(r.headers['Content-Disposition'], 'inline')
                self.assertEqual(r.headers['Content-Length'], '19')
                self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
                self.assertEqual(r.headers['Cache-Control'], 'no-cache')
                self.assertIsNotNone(r.headers['Last-Modified'])
                self.assertIsNotNone(r.headers['ETag'])

                etag = r.headers['ETag']
                lm =  r.headers['Last-Modified']

                # 304 for etag
                r = c.get('/archive.zip!/index.html', query_string={'a': 'source'}, headers={
                    'If-None-Match': etag,
                    }, buffered=True)
                self.assertEqual(r.status_code, 304)

                # 304 for last-modified
                r = c.get('/archive.zip!/index.html', query_string={'a': 'source'}, headers={
                    'If-Modified-Since': lm,
                    }, buffered=True)
                self.assertEqual(r.status_code, 304)

                # 206 for a ranged request
                r = c.get('/archive.zip!/index.html', query_string={'a': 'source'}, headers={
                    'Range': 'bytes=0-11',
                    }, buffered=True)
                self.assertEqual(r.status_code, 206)
                self.assertEqual(r.data.decode('UTF-8').replace('\r\n', '\n'), 'Hello World!')
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file_zip_subdir(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('explicit_dir/', '')
                zh.writestr('explicit_dir/index.html', 'Hello World! 你好')
                zh.writestr('implicit_dir/index.html', 'Hello World! 你好嗎')

            with app.test_client() as c:
                r = c.get('/archive.zip!/explicit_dir', query_string={'a': 'source'}, buffered=True)
                mock_error.assert_called_once_with(404)

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/explicit_dir/', query_string={'a': 'source'}, buffered=True)
                mock_error.assert_called_once_with(404)

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/implicit_dir', query_string={'a': 'source'}, buffered=True)
                mock_error.assert_called_once_with(404)

            mock_error.reset_mock()

            with app.test_client() as c:
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'source'}, buffered=True)
                mock_error.assert_called_once_with(404)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file_zip_nonexist(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist', query_string={'a': 'source'}, buffered=True)
                mock_error.assert_called_once_with(404)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

class TestStatic(unittest.TestCase):
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_format_check(self, mock_error):
        """No format."""
        with app.test_client() as c:
            r = c.get('/index.css', query_string={'a': 'static', 'f': 'json'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format='json')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check(self, mock_error):
        with app.test_client() as c, mock.patch('builtins.open', side_effect=PermissionError('Forbidden')):
            r = c.get('/index.css', query_string={'a': 'static'})
            mock_error.assert_called_once_with(403, format=None)

    def test_file(self):
        with app.test_client() as c:
            r = c.get('/index.css', query_string={'a': 'static'}, buffered=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/css; charset=utf-8')
            self.assertEqual(r.headers['Accept-Ranges'], 'bytes')
            self.assertEqual(r.headers['Cache-Control'], 'no-cache')
            self.assertIsNotNone(r.headers['Last-Modified'])
            self.assertIsNotNone(r.headers['ETag'])

            css = r.data.decode('UTF-8').replace('\r\n', '\n')
            self.assertTrue('#data-table' in css)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'static'})
            mock_error.assert_called_once_with(404)

class TestConfig(unittest.TestCase):
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_format_check(self, mock_error):
        """Require format."""
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'config'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format=None)

    def test_config(self):
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            data = r.json
            self.assertTrue(data['success'])
            self.assertEqual(data['data'], {
                'app': {
                    'name': 'WebScrapBook',
                    'theme': 'default',
                    'base': '',
                    'is_local': True,
                    },
                'book': {
                    '': {
                        'name': 'scrapbook',
                        'top_dir': '',
                        'data_dir': '',
                        'tree_dir': WSB_DIR + '/tree',
                        'index': WSB_DIR + '/tree/map.html',
                        'no_tree': False,
                        }
                    },
                'VERSION': webscrapbook.__version__,
                'WSB_DIR': WSB_DIR,
                'WSB_LOCAL_CONFIG': WSB_LOCAL_CONFIG,
                })

class TestEdit(unittest.TestCase):
    def setUp(self):
        self.test_file = os.path.join(server_root, 'temp.html')
        self.test_zip = os.path.join(server_root, 'temp.maff')

    def tearDown(self):
        try:
            os.remove(self.test_file)
        except FileNotFoundError:
            pass
        try:
            os.remove(self.test_zip)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_format_check(self, mock_error):
        """No format."""
        with open(self.test_file, 'wb') as fh:
            fh.write('你好𧌒蟲'.encode('UTF-8'))

        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'edit', 'f': 'json'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format='json')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check1(self, mock_error):
        with app.test_client() as c, mock.patch('builtins.open', side_effect=PermissionError('Forbidden')):
            r = c.get('/temp.html', query_string={'a': 'edit'})
            mock_error.assert_called_once_with(403, format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check2(self, mock_error):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass
        with app.test_client() as c, mock.patch('zipfile.ZipFile', side_effect=PermissionError('Forbidden')):
            r = c.get('/temp.maff!/index.html', query_string={'a': 'edit'})
            mock_error.assert_called_once_with(403, format=None)

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_file_utf8(self, mock_template):
        with open(self.test_file, 'wb') as fh:
            fh.write('你好𧌒蟲'.encode('UTF-8'))

        with app.test_client() as c:
            r = c.get('/temp.html', query_string={'a': 'edit'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            mock_template.assert_called_once_with('edit.html',
            sitename='WebScrapBook',
            is_local=True,
            base='',
            path='/temp.html',
            body='你好𧌒蟲',
            encoding=None,
            )

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_file_utf8_encoding(self, mock_template):
        """Use ISO-8859-1 for bad encoding."""
        with open(self.test_file, 'wb') as fh:
            fh.write('你好𧌒蟲'.encode('UTF-8'))

        with app.test_client() as c:
            r = c.get('/temp.html', query_string={'a': 'edit', 'e': 'big5'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            mock_template.assert_called_once_with('edit.html',
            sitename='WebScrapBook',
            is_local=True,
            base='',
            path='/temp.html',
            body='你好𧌒蟲'.encode('UTF-8').decode('ISO-8859-1'),
            encoding='ISO-8859-1',
            )

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_file_big5(self, mock_template):
        """Use ISO-8859-1 for bad encoding."""
        with open(self.test_file, 'wb') as fh:
            fh.write('你好'.encode('Big5'))

        with app.test_client() as c:
            r = c.get('/temp.html', query_string={'a': 'edit'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            mock_template.assert_called_once_with('edit.html',
                sitename='WebScrapBook',
                is_local=True,
                base='',
                path='/temp.html',
                body='你好'.encode('Big5').decode('ISO-8859-1'),
                encoding='ISO-8859-1',
                )

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_file_big5_encoding(self, mock_template):
        with open(self.test_file, 'wb') as fh:
            fh.write('你好'.encode('Big5'))

        with app.test_client() as c:
            r = c.get('/temp.html', query_string={'a': 'edit', 'e': 'big5'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            mock_template.assert_called_once_with('edit.html',
                sitename='WebScrapBook',
                is_local=True,
                base='',
                path='/temp.html',
                body='你好',
                encoding='big5',
                )

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_zip(self, mock_template):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('19870101/index.html', 'Hello World! 你好')

        with app.test_client() as c:
            r = c.get('/temp.maff!/19870101/index.html', query_string={'a': 'edit'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            mock_template.assert_called_once_with('edit.html',
                sitename='WebScrapBook',
                is_local=True,
                base='',
                path='/temp.maff!/19870101/index.html',
                body='Hello World! 你好',
                encoding=None,
                )

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_zip_nested(self, mock_template):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            buf1 = io.BytesIO()
            with zipfile.ZipFile(buf1, 'w') as zh1:
                zh1.writestr('index.html', 'Hello World! 你好')
            zh.writestr('19870101/index.htz', buf1.getvalue())

        with app.test_client() as c:
            r = c.get('/temp.maff!/19870101/index.htz!/index.html', query_string={'a': 'edit'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            mock_template.assert_called_once_with('edit.html',
                sitename='WebScrapBook',
                is_local=True,
                base='',
                path='/temp.maff!/19870101/index.htz!/index.html',
                body='Hello World! 你好',
                encoding=None,
                )

class TestEditx(unittest.TestCase):
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_format_check(self, mock_error):
        """No format."""
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'editx', 'f': 'json'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format='json')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_permission_check(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass
            with app.test_client() as c, mock.patch('zipfile.ZipFile', side_effect=PermissionError('Forbidden')):
                r = c.get('/archive.zip!/index.html', query_string={'a': 'editx'})
                mock_error.assert_called_once_with(403, format=None)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_file(self, mock_template):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'editx'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            mock_template.assert_called_once_with('editx.html',
            sitename='WebScrapBook',
            is_local=True,
            base='',
            path='/index.html',
            )

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_zip(self, mock_template):
        zip_filename = os.path.join(server_root, 'temp.maff')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('19870101/index.html', 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/temp.maff!/19870101/index.html', query_string={'a': 'editx'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
                mock_template.assert_called_once_with('editx.html',
                    sitename='WebScrapBook',
                    is_local=True,
                    base='',
                    path='/temp.maff!/19870101/index.html',
                    )
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

class TestExec(unittest.TestCase):
    @mock.patch('webscrapbook.util.launch')
    def test_directory(self, mock_exec):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'exec'})
            self.assertEqual(r.status_code, 204)
            mock_exec.assert_called_once_with(os.path.join(server_root, 'subdir'))

    @mock.patch('webscrapbook.util.launch')
    def test_file(self, mock_exec):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'exec'})
            self.assertEqual(r.status_code, 204)
            mock_exec.assert_called_once_with(os.path.join(server_root, 'index.html'))

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.get('/nonexist.file', query_string={'a': 'exec'})
            mock_error.assert_called_once_with(404, 'File does not exist.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_zip(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.htz')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('index.html', 'Hello World!')

            with app.test_client() as c:
                r = c.get('/archive.htz!/index.html', query_string={'a': 'exec'})
                mock_error.assert_called_once_with(404, 'File does not exist.', format=None)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

class TestBrowse(unittest.TestCase):
    @mock.patch('webscrapbook.util.view_in_explorer')
    def test_directory(self, mock_browse):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'browse'})
            self.assertEqual(r.status_code, 204)
            mock_browse.assert_called_once_with(os.path.join(server_root, 'subdir'))

    @mock.patch('webscrapbook.util.view_in_explorer')
    def test_file(self, mock_browse):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'browse'})
            self.assertEqual(r.status_code, 204)
            mock_browse.assert_called_once_with(os.path.join(server_root, 'index.html'))

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.get('/nonexist.file', query_string={'a': 'browse'})
            mock_error.assert_called_once_with(404, 'File does not exist.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_zip(self, mock_error):
        zip_filename = os.path.join(server_root, 'archive.htz')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('index.html', 'Hello World!')

            with app.test_client() as c:
                r = c.get('/archive.htz!/index.html', query_string={'a': 'browse'})
                mock_error.assert_called_once_with(404, 'File does not exist.', format=None)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

class TestToken(unittest.TestCase):
    def test_token(self):
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'token'})
            token_file = os.path.join(server_root, WSB_DIR, 'server', 'tokens', r.data.decode('UTF-8'))
            try:
                self.assertEqual(r.status_code, 200)
                self.assertTrue(os.path.isfile(token_file))
            finally:
                try:
                    os.remove(token_file)
                except FileNotFoundError:
                    pass

    def test_token_json(self):
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'token', 'f': 'json'})
            data = r.json
            token_file = os.path.join(server_root, WSB_DIR, 'server', 'tokens', data['data'])
            try:
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertTrue(data['success'])
                self.assertTrue(isinstance(data['data'], str))
                self.assertTrue(os.path.isfile(token_file))
            finally:
                try:
                    os.remove(token_file)
                except FileNotFoundError:
                    pass

class TestLock(unittest.TestCase):
    def setUp(self):
        self.lock = os.path.join(server_root, WSB_DIR, 'server', 'locks', 'test')

    def tearDown(self):
        try:
            shutil.rmtree(self.lock)
        except NotADirectoryError:
            os.remove(self.lock)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_method_check(self, mock_error):
        """Require POST."""
        with app.test_client() as c:
            r = c.get('/', query_string={
                'token': token(c),
                'a': 'lock',
                'name': 'test',
                })

            mock_error.assert_called_once_with(405, format=None, valid_methods=['POST'])

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_token_check(self, mock_error):
        """Require token."""
        with app.test_client() as c:
            r = c.post('/', data={
                'a': 'lock',
                'name': 'test',
                })

            mock_error.assert_called_once_with(400, 'Invalid access token.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_params_check(self, mock_error):
        """Require name."""
        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'lock',
                })
            mock_error.assert_called_once_with(400, 'Lock name is not specified.', format=None)

    def test_normal(self):
        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'lock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isdir(self.lock))

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_directory_existed(self, mock_error):
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'lock',
                'name': 'test',
                'chkt': 0,
                })

            mock_error.assert_called_once_with(500, 'Unable to acquire lock "test".', format=None)

    def test_directory_staled(self):
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'lock',
                'name': 'test',
                'chks': 0,
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isdir(self.lock))

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file_existed(self, mock_error):
        os.makedirs(os.path.dirname(self.lock), exist_ok=True)
        with open(self.lock, 'w') as f:
            pass

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'lock',
                'name': 'test',
                'chkt': 0,
                })

            mock_error.assert_called_once_with(500, 'Unable to acquire lock "test".', format=None)

class TestUnlock(unittest.TestCase):
    def setUp(self):
        self.lock = os.path.join(server_root, WSB_DIR, 'server', 'locks', 'test')

    def tearDown(self):
        try:
            shutil.rmtree(self.lock)
        except NotADirectoryError:
            os.remove(self.lock)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_method_check(self, mock_error):
        """Require POST."""
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.get('/', query_string={
                'token': token(c),
                'a': 'unlock',
                'name': 'test',
                })

            mock_error.assert_called_once_with(405, format=None, valid_methods=['POST'])

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_token_check(self, mock_error):
        """Require token."""
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/', data={
                'a': 'unlock',
                'name': 'test',
                })

            mock_error.assert_called_once_with(400, 'Invalid access token.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_params_check(self, mock_error):
        """Require name."""
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'unlock',
                })

            mock_error.assert_called_once_with(400, 'Lock name is not specified.', format=None)

    def test_normal(self):
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'unlock',
                'name': 'test',
                })
            self.assertEqual(r.status_code, 204)
            self.assertFalse(os.path.exists(self.lock))

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'unlock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 204)
            self.assertFalse(os.path.exists(self.lock))

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_unremovable(self, mock_error, mock_stderr):
        os.makedirs(self.lock, exist_ok=True)
        with open(os.path.join(self.lock, 'temp.txt'), 'w') as f:
            pass

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'unlock',
                'name': 'test',
                })

            mock_error.assert_called_once_with(500, 'Unable to remove lock "test".', format=None)
            self.assertNotEqual(mock_stderr.getvalue(), '')

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_unremovable2(self, mock_error, mock_stderr):
        os.makedirs(os.path.dirname(self.lock), exist_ok=True)
        with open(self.lock, 'w') as f:
            pass

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'unlock',
                'name': 'test',
                })

            mock_error.assert_called_once_with(500, 'Unable to remove lock "test".', format=None)
            self.assertNotEqual(mock_stderr.getvalue(), '')

class TestMkdir(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(server_root, 'temp')
        self.test_zip = os.path.join(server_root, 'temp.maff')

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except NotADirectoryError:
            os.remove(self.test_dir)
        except FileNotFoundError:
            pass
        try:
            os.remove(self.test_zip)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_method_check(self, mock_error):
        """Require POST."""
        with app.test_client() as c:
            r = c.get('/temp', query_string={
                'token': token(c),
                'a': 'mkdir',
                })

            mock_error.assert_called_once_with(405, format=None, valid_methods=['POST'])

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_token_check(self, mock_error):
        """Require token."""
        with app.test_client() as c:
            r = c.post('/temp', data={
                'a': 'mkdir',
                })

            mock_error.assert_called_once_with(400, 'Invalid access token.', format=None)

    def test_directory(self):
        with app.test_client() as c:
            r = c.post('/temp', data={
                'token': token(c),
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isdir(self.test_dir))

    def test_directory_nested(self):
        test_dir = os.path.join(server_root, 'temp', 'subdir')

        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isdir(test_dir))

    def test_directory_existed(self):
        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isdir(self.test_dir))

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nondirectory_existed(self, mock_error):
        with open(self.test_dir, 'w') as f:
            pass

        with app.test_client() as c:
            r = c.post('/temp', data={
                'token': token(c),
                'a': 'mkdir',
                })

            mock_error.assert_called_once_with(400, 'Found a non-directory here.', format=None)

    def test_zip_directory(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp.maff!/temp', data={
                'token': token(c),
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                self.assertEqual(zh.namelist(), ['temp/'])

    def test_zip_directory_nested(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp.maff!/temp/subdir', data={
                'token': token(c),
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                self.assertEqual(zh.namelist(), ['temp/subdir/'])

    def test_zip_directory_existed(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('temp/subdir/', '')

        with app.test_client() as c:
            r = c.post('/temp.maff!/temp/subdir', data={
                'token': token(c),
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                self.assertEqual(zh.namelist(), ['temp/subdir/'])

class TestSave(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(server_root, 'temp')
        self.test_file = os.path.join(server_root, 'temp', 'test.txt')
        self.test_zip = os.path.join(server_root, 'temp.maff')

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except NotADirectoryError:
            os.remove(self.test_dir)
        except FileNotFoundError:
            pass
        try:
            os.remove(self.test_zip)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_method_check(self, mock_error):
        """Require POST."""
        os.makedirs(self.test_dir, exist_ok=True)

        with app.test_client() as c:
            r = c.get('/temp/test.txt', query_string={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            mock_error.assert_called_once_with(405, format=None, valid_methods=['POST'])

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_token_check(self, mock_error):
        """Require token."""
        os.makedirs(self.test_dir, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            mock_error.assert_called_once_with(400, 'Invalid access token.', format=None)

    def test_save_file(self):
        os.makedirs(self.test_dir, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_file))
            with open(self.test_file, 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    def test_save_file_nested(self):
        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_file))
            with open(self.test_file, 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    def test_save_file_existed(self):
        os.makedirs(self.test_dir, exist_ok=True)
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write('test')

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_file))
            with open(self.test_file, 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_save_nonfile_existed(self, mock_error):
        os.makedirs(self.test_file, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            mock_error.assert_called_once_with(400, 'Found a non-file here.', format=None)

    def test_save_zip_file(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp.maff!/index.html', data={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            self.assertEqual(r.status_code, 204)
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                with zh.open('index.html', 'r') as f:
                    self.assertEqual(f.read().decode('UTF-8'), 'ABC 你好')

    def test_save_zip_file_nested(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            self.assertEqual(r.status_code, 204)
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                with zh.open('subdir/index.html', 'r') as f:
                    self.assertEqual(f.read().decode('UTF-8'), 'ABC 你好')

    def test_save_zip_file_existed(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('subdir/index.html', 'dummy')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            self.assertEqual(r.status_code, 204)
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                with zh.open('subdir/index.html', 'r') as f:
                    self.assertEqual(f.read().decode('UTF-8'), 'ABC 你好')

    def test_upload_file(self):
        os.makedirs(self.test_dir, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'upload': (io.BytesIO('ABC 你好'.encode('UTF-8')), 'test.txt'),
                }, content_type='multipart/form-data')
            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_file))
            with open(self.test_file, 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    def test_upload_file_nested(self):
        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'upload': (io.BytesIO('ABC 你好'.encode('UTF-8')), 'test.txt'),
                }, content_type='multipart/form-data')

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_file))
            with open(self.test_file, 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    def test_upload_file_existed(self):
        os.makedirs(self.test_dir, exist_ok=True)
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            f.write('test')

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'upload': (io.BytesIO('ABC 你好'.encode('UTF-8')), 'test.txt'),
                }, content_type='multipart/form-data')

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_file))
            with open(self.test_file, 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_upload_nonfile_existed(self, mock_error):
        os.makedirs(self.test_file, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'upload': (io.BytesIO('ABC 你好'.encode('UTF-8')), 'test.txt'),
                }, content_type='multipart/form-data')

            mock_error.assert_called_once_with(400, 'Found a non-file here.', format=None)

    def test_upload_zip_file(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp.maff!/index.html', data={
                'token': token(c),
                'a': 'save',
                'upload': (io.BytesIO('ABC 你好'.encode('UTF-8')), 'test.txt'),
                }, content_type='multipart/form-data')

            self.assertEqual(r.status_code, 204)
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                with zh.open('index.html', 'r') as f:
                    self.assertEqual(f.read().decode('UTF-8'), 'ABC 你好')

    def test_upload_zip_file_nested(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'save',
                'upload': (io.BytesIO('ABC 你好'.encode('UTF-8')), 'test.txt'),
                }, content_type='multipart/form-data')

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                with zh.open('subdir/index.html', 'r') as f:
                    self.assertEqual(f.read().decode('UTF-8'), 'ABC 你好')

    def test_upload_zip_file_existed(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('subdir/index.html', 'dummy')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'save',
                'upload': (io.BytesIO('ABC 你好'.encode('UTF-8')), 'test.txt'),
                }, content_type='multipart/form-data')

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                with zh.open('subdir/index.html', 'r') as f:
                    self.assertEqual(f.read().decode('UTF-8'), 'ABC 你好')

class TestDelete(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(server_root, 'temp')
        self.test_file = os.path.join(server_root, 'temp', 'test.txt')
        self.test_zip = os.path.join(server_root, 'temp.maff')

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except NotADirectoryError:
            os.remove(self.test_dir)
        except FileNotFoundError:
            pass
        try:
            os.remove(self.test_zip)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_method_check(self, mock_error):
        """Require POST."""
        os.makedirs(self.test_dir, exist_ok=True)
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            pass

        with app.test_client() as c:
            r = c.get('/temp/test.txt', query_string={
                'token': token(c),
                'a': 'delete',
                })

            mock_error.assert_called_once_with(405, format=None, valid_methods=['POST'])

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_token_check(self, mock_error):
        """Require token."""
        os.makedirs(self.test_dir, exist_ok=True)
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            pass

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'a': 'delete',
                })

            mock_error.assert_called_once_with(400, 'Invalid access token.', format=None)

    def test_file(self):
        os.makedirs(self.test_dir, exist_ok=True)
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            pass

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 204)
            self.assertFalse(os.path.exists(self.test_file))

    def test_directory(self):
        os.makedirs(self.test_dir, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 204)
            self.assertFalse(os.path.exists(self.test_dir))

    def test_directory_with_content(self):
        os.makedirs(self.test_dir, exist_ok=True)
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            pass

        with app.test_client() as c:
            r = c.post('/temp', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 204)
            self.assertFalse(os.path.isfile(self.test_dir))

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.post('/temp', data={
                'token': token(c),
                'a': 'delete',
                })

            mock_error.assert_called_once_with(404, 'File does not exist.', format=None)

    def test_zip_file(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('file.txt', 'dummy')
            zh.writestr('subdir/index.html', '')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                self.assertEqual(zh.namelist(), ['file.txt'])

    def test_zip_directory(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('file.txt', 'dummy')
            zh.writestr('subdir/', '')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                self.assertEqual(zh.namelist(), ['file.txt'])

    def test_zip_directory_with_content(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('file.txt', 'dummy')
            zh.writestr('subdir/', '')
            zh.writestr('subdir/dir/', '')
            zh.writestr('subdir/index.html', '')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                self.assertEqual(zh.namelist(), ['file.txt'])

    def test_zip_implicit_directory_with_content(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('file.txt', 'dummy')
            zh.writestr('subdir/dir/', '')
            zh.writestr('subdir/index.html', '')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isfile(self.test_zip))
            with zipfile.ZipFile(self.test_zip, 'r') as zh:
                self.assertEqual(zh.namelist(), ['file.txt'])

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_zip_nonexist(self, mock_error):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('file.txt', 'dummy')

        with app.test_client() as c:
            r = c.post('/temp.maff!/nonexist', data={
                'token': token(c),
                'a': 'delete',
                })

            mock_error.assert_called_once_with(404, 'Entry does not exist in this ZIP file.', format=None)

class TestMove(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(server_root, 'temp')
        self.test_zip = os.path.join(server_root, 'temp.maff')

        os.makedirs(os.path.join(self.test_dir, 'subdir'), exist_ok=True)
        with open(os.path.join(self.test_dir, 'subdir', 'test.txt'), 'w', encoding='UTF-8') as f:
            f.write('ABC 你好')

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except NotADirectoryError:
            os.remove(self.test_dir)
        except FileNotFoundError:
            pass
        try:
            os.remove(self.test_zip)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_method_check(self, mock_error):
        """Require POST."""
        with app.test_client() as c:
            r = c.get('/temp/subdir/test.txt', query_string={
                'a': 'move',
                'target': '/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(405, format=None, valid_methods=['POST'])

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_token_check(self, mock_error):
        """Require token."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'a': 'move',
                'target': '/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(400, 'Invalid access token.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_params_check(self, mock_error):
        """Require target."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                })

            mock_error.assert_called_once_with(400, 'Target is not specified.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_path_check(self, mock_error):
        """Target must not beyond the root directory."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                'target': '../test_app_actions1/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(403, 'Unable to operate beyond the root directory.', format=None)

    def test_file(self):
        stat = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2/test2.txt',
                })

            self.assertEqual(r.status_code, 204)
            self.assertFalse(os.path.isfile(os.path.join(self.test_dir, 'subdir', 'test.txt')))
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt')), stat)
            with open(os.path.join(self.test_dir, 'subdir2', 'test2.txt'), 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    def test_directory(self):
        stat = os.stat(os.path.join(self.test_dir, 'subdir'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))

        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2/subsubdir',
                })

            self.assertEqual(r.status_code, 204)
            self.assertFalse(os.path.isdir(os.path.join(self.test_dir, 'subdir')))
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'subsubdir')), stat)
            self.assertTrue(os.path.isfile(os.path.join(self.test_dir, 'subdir2', 'subsubdir', 'test.txt')))
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'subsubdir', 'test.txt')), stat2)

    def test_directory_slash(self):
        stat = os.stat(os.path.join(self.test_dir, 'subdir'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))

        with app.test_client() as c:
            r = c.post('/temp/subdir/', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2/subsubdir/',
                })

            self.assertEqual(r.status_code, 204)
            self.assertFalse(os.path.isdir(os.path.join(self.test_dir, 'subdir')))
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'subsubdir')), stat)
            self.assertTrue(os.path.isfile(os.path.join(self.test_dir, 'subdir2', 'subsubdir', 'test.txt')))
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'subsubdir', 'test.txt')), stat2)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.post('/temp/nonexist', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2',
                })

            mock_error.assert_called_once_with(404, 'File does not exist.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file_to_file(self, mock_error):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        with open(os.path.join(self.test_dir, 'subdir2', 'test2.txt'), 'w', encoding='UTF-8') as f:
            f.write('你好 XYZ')
        stat = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt'))

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(400, 'Found something at target "/temp/subdir2/test2.txt".', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file_to_dir(self, mock_error):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        stat = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2'))

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2',
                })

            mock_error.assert_called_once_with(400, 'Found something at target "/temp/subdir2".', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_dir_to_dir(self, mock_error):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        stat = os.stat(os.path.join(self.test_dir, 'subdir'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2'))

        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2',
                })

            mock_error.assert_called_once_with(400, 'Found something at target "/temp/subdir2".', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_dir_to_file(self, mock_error):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        with open(os.path.join(self.test_dir, 'subdir2', 'test2.txt'), 'w', encoding='UTF-8') as f:
            f.write('你好 XYZ')
        stat = os.stat(os.path.join(self.test_dir, 'subdir'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt'))

        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(400, 'Found something at target "/temp/subdir2/test2.txt".', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_source_in_zip(self, mock_error):
        """No ZIP support."""
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('subdir/index.html', 'ABC 你好')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/index.html',
                })

            mock_error.assert_called_once_with(400, 'File is inside an archive file.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_target_in_zip(self, mock_error):
        """No ZIP support."""
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp.maff!/test.txt',
                })

            mock_error.assert_called_once_with(400, 'Target is inside an archive file.', format=None)

class TestCopy(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(server_root, 'temp')
        self.test_zip = os.path.join(server_root, 'temp.maff')

        os.makedirs(os.path.join(self.test_dir, 'subdir'), exist_ok=True)
        with open(os.path.join(self.test_dir, 'subdir', 'test.txt'), 'w', encoding='UTF-8') as f:
            f.write('ABC 你好')

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except NotADirectoryError:
            os.remove(self.test_dir)
        except FileNotFoundError:
            pass
        try:
            os.remove(self.test_zip)
        except FileNotFoundError:
            pass

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_method_check(self, mock_error):
        """Require POST."""
        with app.test_client() as c:
            r = c.get('/temp/subdir/test.txt', query_string={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(405, format=None, valid_methods=['POST'])

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_token_check(self, mock_error):
        """Require token."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'a': 'copy',
                'target': '/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(400, 'Invalid access token.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_params_check(self, mock_error):
        """Require target."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                })

            mock_error.assert_called_once_with(400, 'Target is not specified.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_path_check(self, mock_error):
        """Target must not beyond the root directory."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                'target': '../test_app_actions1/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(403, 'Unable to operate beyond the root directory.', format=None)

    def test_file(self):
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2/test2.txt',
                })

            self.assertEqual(r.status_code, 204)
            with open(os.path.join(self.test_dir, 'subdir', 'test.txt'), 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')
            with open(os.path.join(self.test_dir, 'subdir2', 'test2.txt'), 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

            stat1 = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
            stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt'))
            self.assertEqual(stat1.st_mode, stat2.st_mode)
            self.assertEqual(stat1.st_uid, stat2.st_uid)
            self.assertEqual(stat1.st_gid, stat2.st_gid)
            self.assertEqual(stat1.st_atime, stat2.st_atime)
            self.assertEqual(stat1.st_mtime, stat2.st_mtime)

    def test_directory(self):
        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2/subsubdir',
                })

            self.assertEqual(r.status_code, 204)

            stat1 = os.stat(os.path.join(self.test_dir, 'subdir'))
            stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'subsubdir'))
            self.assertEqual(stat1.st_mode, stat2.st_mode)
            self.assertEqual(stat1.st_uid, stat2.st_uid)
            self.assertEqual(stat1.st_gid, stat2.st_gid)
            self.assertEqual(stat1.st_atime, stat2.st_atime)
            self.assertEqual(stat1.st_mtime, stat2.st_mtime)

            stat1 = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
            stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'subsubdir', 'test.txt'))
            self.assertEqual(stat1.st_mode, stat2.st_mode)
            self.assertEqual(stat1.st_uid, stat2.st_uid)
            self.assertEqual(stat1.st_gid, stat2.st_gid)
            self.assertEqual(stat1.st_atime, stat2.st_atime)
            self.assertEqual(stat1.st_mtime, stat2.st_mtime)

            with open(os.path.join(self.test_dir, 'subdir', 'test.txt'), 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')
            with open(os.path.join(self.test_dir, 'subdir2', 'subsubdir', 'test.txt'), 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    def test_directory_slash(self):
        with app.test_client() as c:
            r = c.post('/temp/subdir/', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2/subsubdir/',
                })

            self.assertEqual(r.status_code, 204)

            stat1 = os.stat(os.path.join(self.test_dir, 'subdir'))
            stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'subsubdir'))
            self.assertEqual(stat1.st_mode, stat2.st_mode)
            self.assertEqual(stat1.st_uid, stat2.st_uid)
            self.assertEqual(stat1.st_gid, stat2.st_gid)
            self.assertEqual(stat1.st_atime, stat2.st_atime)
            self.assertEqual(stat1.st_mtime, stat2.st_mtime)

            stat1 = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
            stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'subsubdir', 'test.txt'))
            self.assertEqual(stat1.st_mode, stat2.st_mode)
            self.assertEqual(stat1.st_uid, stat2.st_uid)
            self.assertEqual(stat1.st_gid, stat2.st_gid)
            self.assertEqual(stat1.st_atime, stat2.st_atime)
            self.assertEqual(stat1.st_mtime, stat2.st_mtime)

            with open(os.path.join(self.test_dir, 'subdir', 'test.txt'), 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')
            with open(os.path.join(self.test_dir, 'subdir2', 'subsubdir', 'test.txt'), 'r', encoding='UTF-8') as f:
                self.assertEqual(f.read(), 'ABC 你好')

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_nonexist(self, mock_error):
        with app.test_client() as c:
            r = c.post('/temp/nonexist', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2',
                })

            mock_error.assert_called_once_with(404, 'File does not exist.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file_to_file(self, mock_error):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        with open(os.path.join(self.test_dir, 'subdir2', 'test2.txt'), 'w', encoding='UTF-8') as f:
            f.write('你好 XYZ')
        stat = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt'))

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(400, 'Found something at target "/temp/subdir2/test2.txt".', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_file_to_dir(self, mock_error):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        stat = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2'))

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2',
                })

            mock_error.assert_called_once_with(400, 'Found something at target "/temp/subdir2".', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_dir_to_dir(self, mock_error):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        stat = os.stat(os.path.join(self.test_dir, 'subdir'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2'))

        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2',
                })

            mock_error.assert_called_once_with(400, 'Found something at target "/temp/subdir2".', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_dir_to_file(self, mock_error):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        with open(os.path.join(self.test_dir, 'subdir2', 'test2.txt'), 'w', encoding='UTF-8') as f:
            f.write('你好 XYZ')
        stat = os.stat(os.path.join(self.test_dir, 'subdir'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt'))

        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2/test2.txt',
                })

            mock_error.assert_called_once_with(400, 'Found something at target "/temp/subdir2/test2.txt".', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_source_in_zip(self, mock_error):
        """No ZIP support."""
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('subdir/index.html', 'ABC 你好')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/index.html',
                })

            mock_error.assert_called_once_with(400, 'File is inside an archive file.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_target_in_zip(self, mock_error):
        """No ZIP support."""
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp.maff!/test.txt',
                })

            mock_error.assert_called_once_with(400, 'Target is inside an archive file.', format=None)

class TestUnknown(unittest.TestCase):
    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_unknown(self, mock_error):
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'unkonwn'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format=None)

    @mock.patch('webscrapbook.app.http_error', return_value=Response())
    def test_unknown_json(self, mock_error):
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'unkonwn', 'f': 'json'})
            mock_error.assert_called_once_with(400, 'Action not supported.', format='json')

if __name__ == '__main__':
    unittest.main()
