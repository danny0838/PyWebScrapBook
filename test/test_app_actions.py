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
from flask import request
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
                subarchivepath=None,
                subentries={
                    ('file.txt', 'file', 3, os.stat(os.path.join(server_root, 'subdir', 'file.txt')).st_mtime),
                    ('sub', 'dir', None, os.stat(os.path.join(server_root, 'subdir', 'sub')).st_mtime),
                    },
                )

    def test_file_normal(self):
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

    def test_file_htz(self):
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

    def test_file_maff(self):
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

    def test_file_zip(self):
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

    @mock.patch('webscrapbook.app.render_template', return_value='')
    def test_file_zip_subdir(self, mock_template):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.zip!/', buffered=True)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'text/html')
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
                    subarchivepath='',
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

    def test_file_zip_subfile(self):
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

    def test_file_markdown(self):
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

    def test_file_meta_refresh(self):
        with app.test_client() as c:
            r = c.get('/refresh.htm')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/index.html')

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.get('/nonexist')
            self.assertEqual(r.status_code, 404)

    def test_json_directory(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'f': 'json'})
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

            r = c.get('/subdir/', query_string={'f': 'json'})
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

    def test_json_file_normal(self):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'f': 'json'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {
                'success': True,
                'data': {
                    'name': 'index.html',
                    'type': 'file',
                    'size': os.stat(os.path.join(server_root, 'index.html')).st_size,
                    'last_modified': os.stat(os.path.join(server_root, 'index.html')).st_mtime,
                    'mime': 'text/html',
                    },
                })

    def test_json_file_htz(self):
        zip_filename = os.path.join(server_root, 'archive.htz')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.htz', query_string={'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'archive.htz',
                        'type': 'file',
                        'size': os.stat(os.path.join(server_root, 'archive.htz')).st_size,
                        'last_modified': os.stat(os.path.join(server_root, 'archive.htz')).st_mtime,
                        'mime': 'application/html+zip',
                        },
                    })
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_json_file_maff(self):
        zip_filename = os.path.join(server_root, 'archive.maff')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('19870101/index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.maff', query_string={'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'archive.maff',
                        'type': 'file',
                        'size': os.stat(os.path.join(server_root, 'archive.maff')).st_size,
                        'last_modified': os.stat(os.path.join(server_root, 'archive.maff')).st_mtime,
                        'mime': 'application/x-maff',
                        },
                    })
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_json_file_zip(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.zip', query_string={'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'archive.zip',
                        'type': 'file',
                        'size': os.stat(os.path.join(server_root, 'archive.zip')).st_size,
                        'last_modified': os.stat(os.path.join(server_root, 'archive.zip')).st_mtime,
                        'mime': 'application/x-zip-compressed',
                        },
                    })
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_json_file_zip_subdir(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('explicit_dir/', (1987, 1, 1, 0, 0, 0)), '')
                zh.writestr(zipfile.ZipInfo('explicit_dir/index.html', (1987, 1, 2, 0, 0, 0)), 'Hello World! 你好')
                zh.writestr(zipfile.ZipInfo('implicit_dir/index.html', (1987, 1, 3, 0, 0, 0)), 'Hello World! 你好嗎')

            with app.test_client() as c:
                r = c.get('/archive.zip!/explicit_dir', query_string={'f': 'json'})
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

            with app.test_client() as c:
                r = c.get('/archive.zip!/implicit_dir', query_string={'f': 'json'})
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
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_json_file_zip_subfile(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr(zipfile.ZipInfo('index.html', (1987, 1, 1, 0, 0, 0)), 'Hello World! 你好')

            with app.test_client() as c:
                r = c.get('/archive.zip!/index.html', query_string={'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers['Content-Type'], 'application/json')
                self.assertEqual(r.json, {
                    'success': True,
                    'data': {
                        'name': 'index.html',
                        'type': 'file',
                        'size': 19,
                        'last_modified': 536428800,
                        'mime': 'text/html',
                        },
                    })
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_json_file_markdown(self):
        with app.test_client() as c:
            r = c.get('/index.md', query_string={'f': 'json'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {
                'success': True,
                'data': {
                    'name': 'index.md',
                    'type': 'file',
                    'size': os.stat(os.path.join(server_root, 'index.md')).st_size,
                    'last_modified': os.stat(os.path.join(server_root, 'index.md')).st_mtime,
                    'mime': 'text/markdown',
                    },
                })

    def test_json_nonexist(self):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'f': 'json'})
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
    def test_format_check(self):
        """Require format."""
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'list'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.headers['Content-Type'],'text/html; charset=utf-8')
            self.assertEqual(r.data.decode('UTF-8'), 'Action not supported.')

    def test_directory(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'list', 'f': 'json'})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/?a=list&f=json')

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
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/?a=list&f=json&recursive=1')

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

    def test_file(self):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'list', 'f': 'json'})
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {'error': {'status': 404, 'message': 'Directory does not exist.'}})

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'list', 'f': 'json'})
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {'error': {'status': 404, 'message': 'Directory does not exist.'}})

    def test_zip(self):
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
                r = c.get('/archive.zip!/explicit_dir', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], 'http://localhost/archive.zip!/explicit_dir/?a=list&f=json')

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
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], 'http://localhost/archive.zip!/implicit_dir/?a=list&f=json')

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
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_sse_directory(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'list', 'f': 'sse'})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/?a=list&f=sse')

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
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/?a=list&f=sse&recursive=1')

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

    def test_sse_file(self):
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'list', 'f': 'sse'})
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            self.assertEqual(r.data.decode('UTF-8'), 'Directory does not exist.')

    def test_sse_nonexist(self):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'list', 'f': 'sse'})
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            self.assertEqual(r.data.decode('UTF-8'), 'Directory does not exist.')

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
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], 'http://localhost/archive.zip!/explicit_dir/?a=list&f=sse')

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
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], 'http://localhost/archive.zip!/implicit_dir/?a=list&f=sse')

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
    def test_format_check(self):
        """No format."""
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'source', 'f': 'json'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {'error': {'status': 400, 'message': 'Action not supported.'}})

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

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'source'}, buffered=True)
            self.assertEqual(r.status_code, 404)

    def test_directory(self):
        with app.test_client() as c:
            r = c.get('/subdir', query_string={'a': 'source'})
            self.assertEqual(r.status_code, 404)

        with app.test_client() as c:
            r = c.get('/subdir/', query_string={'a': 'source'})
            self.assertEqual(r.status_code, 404)

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

    def test_file_zip_subdir(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                zh.writestr('explicit_dir/', '')
                zh.writestr('explicit_dir/index.html', 'Hello World! 你好')
                zh.writestr('implicit_dir/index.html', 'Hello World! 你好嗎')

            with app.test_client() as c:
                r = c.get('/archive.zip!/explicit_dir', query_string={'a': 'source'}, buffered=True)
                self.assertEqual(r.status_code, 404)

            with app.test_client() as c:
                r = c.get('/archive.zip!/explicit_dir/', query_string={'a': 'source'}, buffered=True)
                self.assertEqual(r.status_code, 404)

            with app.test_client() as c:
                r = c.get('/archive.zip!/implicit_dir', query_string={'a': 'source'}, buffered=True)
                self.assertEqual(r.status_code, 404)

            with app.test_client() as c:
                r = c.get('/archive.zip!/implicit_dir/', query_string={'a': 'source'}, buffered=True)
                self.assertEqual(r.status_code, 404)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

    def test_file_zip_nonexist(self):
        zip_filename = os.path.join(server_root, 'archive.zip')
        try:
            with zipfile.ZipFile(zip_filename, 'w') as zh:
                pass

            with app.test_client() as c:
                r = c.get('/archive.zip!/nonexist', query_string={'a': 'source'}, buffered=True)
                self.assertEqual(r.status_code, 404)
        finally:
            try:
                os.remove(zip_filename)
            except FileNotFoundError:
                pass

class TestStatic(unittest.TestCase):
    def test_format_check(self):
        """No format."""
        with app.test_client() as c:
            r = c.get('/index.css', query_string={'a': 'static', 'f': 'json'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {'error': {'status': 400, 'message': 'Action not supported.'}})

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

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'static'})
            self.assertEqual(r.status_code, 404)

class TestConfig(unittest.TestCase):
    def test_format_check(self):
        """Require format."""
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'config'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.headers['Content-Type'],'text/html; charset=utf-8')
            self.assertEqual(r.data.decode('UTF-8'), 'Action not supported.')

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

    def test_format_check(self):
        """No format."""
        with open(self.test_file, 'wb') as fh:
            fh.write('你好𧌒蟲'.encode('UTF-8'))

        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'edit', 'f': 'json'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {'error': {'status': 400, 'message': 'Action not supported.'}})

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

class TestEditx(unittest.TestCase):
    def test_format_check(self):
        """No format."""
        with app.test_client() as c:
            r = c.get('/index.html', query_string={'a': 'editx', 'f': 'json'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {'error': {'status': 400, 'message': 'Action not supported.'}})
    
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

    def test_method_check(self):
        """Require POST."""
        with app.test_client() as c:
            r = c.get('/', query_string={
                'token': token(c),
                'a': 'lock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 405)
            self.assertEqual(r.data.decode('UTF-8'), 'Method "GET" not allowed.')
            self.assertFalse(os.path.isdir(self.lock))

    def test_token_check(self):
        """Require token."""
        with app.test_client() as c:
            r = c.post('/', data={
                'a': 'lock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Invalid access token.')
            self.assertFalse(os.path.isdir(self.lock))

    def test_params_check(self):
        """Require name."""
        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'lock',
                })
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Lock name is not specified.')
            self.assertFalse(os.path.isdir(self.lock))

    def test_normal(self):
        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'lock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 204)
            self.assertTrue(os.path.isdir(self.lock))

    def test_directory_existed(self):
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'lock',
                'name': 'test',
                'chkt': 0,
                })

            self.assertEqual(r.status_code, 500)
            self.assertEqual(r.data.decode('UTF-8'), 'Unable to acquire lock "test".')
            self.assertTrue(os.path.isdir(self.lock))

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

    def test_file_existed(self):
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

            self.assertEqual(r.status_code, 500)
            self.assertEqual(r.data.decode('UTF-8'), 'Unable to acquire lock "test".')
            self.assertTrue(os.path.isfile(self.lock))

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

    def test_method_check(self):
        """Require POST."""
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.get('/', query_string={
                'token': token(c),
                'a': 'unlock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 405)
            self.assertEqual(r.data.decode('UTF-8'), 'Method "GET" not allowed.')
            self.assertTrue(os.path.isdir(self.lock))

    def test_token_check(self):
        """Require token."""
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/', data={
                'a': 'unlock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Invalid access token.')
            self.assertTrue(os.path.isdir(self.lock))

    def test_params_check(self):
        """Require name."""
        os.makedirs(self.lock, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'unlock',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Lock name is not specified.')
            self.assertTrue(os.path.isdir(self.lock))

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
    def test_unremovable(self, mock_stderr):
        os.makedirs(self.lock, exist_ok=True)
        with open(os.path.join(self.lock, 'temp.txt'), 'w') as f:
            pass

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'unlock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 500)
            self.assertEqual(r.data.decode('UTF-8'), 'Unable to remove lock "test".')
            self.assertTrue(os.path.isdir(self.lock))
            self.assertNotEqual(mock_stderr.getvalue(), '')

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    def test_unremovable2(self, mock_stderr):
        os.makedirs(os.path.dirname(self.lock), exist_ok=True)
        with open(self.lock, 'w') as f:
            pass

        with app.test_client() as c:
            r = c.post('/', data={
                'token': token(c),
                'a': 'unlock',
                'name': 'test',
                })

            self.assertEqual(r.status_code, 500)
            self.assertEqual(r.data.decode('UTF-8'), 'Unable to remove lock "test".')
            self.assertTrue(os.path.isfile(self.lock))
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

    def test_method_check(self):
        """Require POST."""
        with app.test_client() as c:
            r = c.get('/temp', query_string={
                'token': token(c),
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 405)
            self.assertEqual(r.data.decode('UTF-8'), 'Method "GET" not allowed.')
            self.assertFalse(os.path.isdir(self.test_dir))

    def test_token_check(self):
        """Require token."""
        with app.test_client() as c:
            r = c.post('/temp', data={
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Invalid access token.')
            self.assertFalse(os.path.isdir(self.test_dir))

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

    def test_nondirectory_existed(self):
        with open(self.test_dir, 'w') as f:
            pass

        with app.test_client() as c:
            r = c.post('/temp', data={
                'token': token(c),
                'a': 'mkdir',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found a non-directory here.')
            self.assertTrue(os.path.isfile(self.test_dir))

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

    def test_method_check(self):
        """Require POST."""
        os.makedirs(self.test_dir, exist_ok=True)

        with app.test_client() as c:
            r = c.get('/temp/test.txt', query_string={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })
            self.assertEqual(r.status_code, 405)
            self.assertEqual(r.data.decode('UTF-8'), 'Method "GET" not allowed.')
            self.assertFalse(os.path.isfile(self.test_file))

    def test_token_check(self):
        """Require token."""
        os.makedirs(self.test_dir, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Invalid access token.')
            self.assertFalse(os.path.isfile(self.test_file))

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

    def test_save_nonfile_existed(self):
        os.makedirs(self.test_file, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found a non-file here.')
            self.assertFalse(os.path.isfile(self.test_file))

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

    def test_upload_nonfile_existed(self):
        os.makedirs(self.test_file, exist_ok=True)

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'token': token(c),
                'a': 'save',
                'upload': (io.BytesIO('ABC 你好'.encode('UTF-8')), 'test.txt'),
                }, content_type='multipart/form-data')

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found a non-file here.')
            self.assertFalse(os.path.isfile(self.test_file))

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

    def test_method_check(self):
        """Require POST."""
        os.makedirs(self.test_dir, exist_ok=True)
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            pass

        with app.test_client() as c:
            r = c.get('/temp/test.txt', query_string={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 405)
            self.assertEqual(r.data.decode('UTF-8'), 'Method "GET" not allowed.')
            self.assertTrue(os.path.isfile(self.test_file))

    def test_token_check(self):
        """Require token."""
        os.makedirs(self.test_dir, exist_ok=True)
        with open(self.test_file, 'w', encoding='UTF-8') as f:
            pass

        with app.test_client() as c:
            r = c.post('/temp/test.txt', data={
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Invalid access token.')
            self.assertTrue(os.path.isfile(self.test_file))

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

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.post('/temp', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.data.decode('UTF-8'), 'File does not exist.')
            self.assertFalse(os.path.exists(self.test_dir))

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

    def test_zip_nonexist(self):
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('file.txt', 'dummy')

        with app.test_client() as c:
            r = c.post('/temp.maff!/nonexist', data={
                'token': token(c),
                'a': 'delete',
                })

            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.data.decode('UTF-8'), 'Entry does not exist in this ZIP file.')

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

    def test_method_check(self):
        """Require POST."""
        with app.test_client() as c:
            r = c.get('/temp/subdir/test.txt', query_string={
                'a': 'move',
                'target': '/temp/subdir2/test2.txt',
                })

            self.assertEqual(r.status_code, 405)
            self.assertEqual(r.data.decode('UTF-8'), 'Method "GET" not allowed.')

    def test_token_check(self):
        """Require token."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'a': 'move',
                'target': '/temp/subdir2/test2.txt',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Invalid access token.')

    def test_params_check(self):
        """Require target."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Target is not specified.')

    def test_path_check(self):
        """Target must not beyond the root directory."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                'target': '../test_app_actions1/temp/subdir2/test2.txt',
                })

            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.data.decode('UTF-8'), 'Unable to operate beyond the root directory.')

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

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.post('/temp/nonexist', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2',
                })
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.data.decode('UTF-8'), 'File does not exist.')
            self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'nonexist')))
            self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'subdir2')))

    def test_file_to_file(self):
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

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found something at target "/temp/subdir2/test2.txt".')
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt')), stat)
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt')), stat2)

    def test_file_to_dir(self):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        stat = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2'))

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found something at target "/temp/subdir2".')
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt')), stat)
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2')), stat2)

    def test_dir_to_dir(self):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        stat = os.stat(os.path.join(self.test_dir, 'subdir'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2'))

        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/subdir2',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found something at target "/temp/subdir2".')
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir')), stat)
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2')), stat2)

    def test_dir_to_file(self):
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

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found something at target "/temp/subdir2/test2.txt".')
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir')), stat)
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt')), stat2)

    def test_source_in_zip(self):
        """No ZIP support."""
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('subdir/index.html', 'ABC 你好')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp/index.html',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'File is inside an archive file.')

    def test_target_in_zip(self):
        """No ZIP support."""
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'move',
                'target': '/temp.maff!/test.txt',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Move target is inside an archive file.')

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

    def test_method_check(self):
        """Require POST."""
        with app.test_client() as c:
            r = c.get('/temp/subdir/test.txt', query_string={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2/test2.txt',
                })

            self.assertEqual(r.status_code, 405)
            self.assertEqual(r.data.decode('UTF-8'), 'Method "GET" not allowed.')

    def test_token_check(self):
        """Require token."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'a': 'copy',
                'target': '/temp/subdir2/test2.txt',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Invalid access token.')

    def test_params_check(self):
        """Require target."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Target is not specified.')

    def test_path_check(self):
        """Target must not beyond the root directory."""
        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                'target': '../test_app_actions1/temp/subdir2/test2.txt',
                })

            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.data.decode('UTF-8'), 'Unable to operate beyond the root directory.')

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

    def test_nonexist(self):
        with app.test_client() as c:
            r = c.post('/temp/nonexist', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2',
                })

            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.data.decode('UTF-8'), 'File does not exist.')
            self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'nonexist')))
            self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'subdir2')))

    def test_file_to_file(self):
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

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found something at target "/temp/subdir2/test2.txt".')
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt')), stat)
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt')), stat2)

    def test_file_to_dir(self):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        stat = os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2'))

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found something at target "/temp/subdir2".')
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir', 'test.txt')), stat)
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2')), stat2)

    def test_dir_to_dir(self):
        os.makedirs(os.path.join(self.test_dir, 'subdir2'), exist_ok=True)
        stat = os.stat(os.path.join(self.test_dir, 'subdir'))
        stat2 = os.stat(os.path.join(self.test_dir, 'subdir2'))

        with app.test_client() as c:
            r = c.post('/temp/subdir', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/subdir2',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found something at target "/temp/subdir2".')
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir')), stat)
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2')), stat2)

    def test_dir_to_file(self):
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

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Found something at target "/temp/subdir2/test2.txt".')
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir')), stat)
            self.assertEqual(os.stat(os.path.join(self.test_dir, 'subdir2', 'test2.txt')), stat2)

    def test_source_in_zip(self):
        """No ZIP support."""
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            zh.writestr('subdir/index.html', 'ABC 你好')

        with app.test_client() as c:
            r = c.post('/temp.maff!/subdir/index.html', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp/index.html',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'File is inside an archive file.')

    def test_target_in_zip(self):
        """No ZIP support."""
        with zipfile.ZipFile(self.test_zip, 'w') as zh:
            pass

        with app.test_client() as c:
            r = c.post('/temp/subdir/test.txt', data={
                'token': token(c),
                'a': 'copy',
                'target': '/temp.maff!/test.txt',
                })

            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data.decode('UTF-8'), 'Copy target is inside an archive file.')

class TestUnknown(unittest.TestCase):
    def test_unknown(self):
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'unkonwn'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.headers['Content-Type'], 'text/html; charset=utf-8')
            self.assertEqual(r.data.decode('UTF-8'), 'Action not supported.')

    def test_unknown_json(self):
        with app.test_client() as c:
            r = c.get('/', query_string={'a': 'unkonwn', 'f': 'json'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {'error': {'status': 400, 'message': 'Action not supported.'}})

if __name__ == '__main__':
    unittest.main()
