# @FIXME: Some cases have an unclosed file issue. Although adding
#     buffered=True temporarily suppresses it, a further investigation
#     for a possible leak of the source code is pending.
from unittest import mock
import unittest
import sys
import os
import shutil
from base64 import b64encode
from functools import partial
from flask import request
from webscrapbook import WSB_DIR, WSB_LOCAL_CONFIG
from webscrapbook.app import make_app

root_dir = os.path.abspath(os.path.dirname(__file__))
server_root = os.path.join(root_dir, 'test_app_config')
server_config = os.path.join(server_root, WSB_DIR, WSB_LOCAL_CONFIG)

mocking = None

def setUpModule():
    # create temp folders
    os.makedirs(os.path.dirname(server_config), exist_ok=True)

    # mock out WSB_USER_CONFIG
    global mocking
    mocking = mock.patch('webscrapbook.WSB_USER_CONFIG', server_root)
    mocking.start()

def tearDownModule():
    # purge WSB_DIR
    try:
        shutil.rmtree(os.path.join(server_root, WSB_DIR))
    except FileNotFoundError:
        pass

    # stop mock
    mocking.stop()

def token(get):
    """Wrapper to quickly retrieve a token."""
    return get('/', query_string={'a': 'token'}).data.decode('UTF-8')

class TestApp(unittest.TestCase):
    def test_name(self):
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
name = mywsb
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get)

            # /
            r = get('/')
            html = r.data.decode('UTF-8')
            self.assertTrue('<h1 id="header" class="breadcrumbs"><a>mywsb</a>/</h1>' in html)

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')
            self.assertTrue('<h1 id="header" class="breadcrumbs"><a href="/">mywsb</a>/<a>subdir</a>/</h1>' in html)

    @mock.patch('jinja2.FileSystemLoader')
    def test_theme(self, mock_loader):
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
theme = default
""")

        app = make_app(server_root)
        self.assertEqual(
            os.path.normcase(mock_loader.call_args[0][0][0]),
            os.path.normcase(os.path.join(server_root, WSB_DIR, 'themes', 'default', 'templates')))
        self.assertEqual(
            os.path.normcase(mock_loader.call_args[0][0][1]),
            os.path.normcase(os.path.abspath(os.path.join(__file__, '..', '..', 'webscrapbook',  'themes', 'default', 'templates'))))

    def test_root(self):
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
root = subdir
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get, buffered=True)

            r = get('/index.html')
            html = r.data.decode('UTF-8')
            self.assertEqual(html, 'Subdirectory Hello World! 你好')

    def test_base(self):
        # base = / (no base)
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
base =
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get)

            # /
            r = get('/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/common.css?a=static"' in html)
            self.assertTrue('href="/index.css?a=static"' in html)
            self.assertTrue('src="/common.js?a=static"' in html)
            self.assertTrue('src="/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a>WebScrapBook</a>/</h1>' in html)
            self.assertTrue('data-base="" data-path="/"' in html)


            # /subdir/
            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/')

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/common.css?a=static"' in html)
            self.assertTrue('href="/index.css?a=static"' in html)
            self.assertTrue('src="/common.js?a=static"' in html)
            self.assertTrue('src="/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a href="/">WebScrapBook</a>/<a>subdir</a>/</h1>' in html)
            self.assertTrue('data-base="" data-path="/subdir/"' in html)

        # base = /sb
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
base = /sb
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get)

            # /
            r = get('/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/sb/common.css?a=static"' in html)
            self.assertTrue('href="/sb/index.css?a=static"' in html)
            self.assertTrue('src="/sb/common.js?a=static"' in html)
            self.assertTrue('src="/sb/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a>WebScrapBook</a>/</h1>' in html)
            self.assertTrue('data-base="/sb" data-path="/"' in html)

            # /subdir/
            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/sb/subdir/')

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/sb/common.css?a=static"' in html)
            self.assertTrue('href="/sb/index.css?a=static"' in html)
            self.assertTrue('src="/sb/common.js?a=static"' in html)
            self.assertTrue('src="/sb/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a href="/sb/">WebScrapBook</a>/<a>subdir</a>/</h1>' in html)
            self.assertTrue('data-base="/sb" data-path="/subdir/"' in html)

    def test_x_prefix(self):
        # allowed_x_prefix = 0
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
allowed_x_prefix = 0
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get, headers={
                'X-Forwarded-Prefix': '/sb',
                })

            # /
            r = get('/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/common.css?a=static"' in html)
            self.assertTrue('href="/index.css?a=static"' in html)
            self.assertTrue('src="/common.js?a=static"' in html)
            self.assertTrue('src="/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a>WebScrapBook</a>/</h1>' in html)
            self.assertTrue('data-base="" data-path="/"' in html)

            # /subdir/
            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/')

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/common.css?a=static"' in html)
            self.assertTrue('href="/index.css?a=static"' in html)
            self.assertTrue('src="/common.js?a=static"' in html)
            self.assertTrue('src="/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a href="/">WebScrapBook</a>/<a>subdir</a>/</h1>' in html)
            self.assertTrue('data-base="" data-path="/subdir/"' in html)

        # allowed_x_prefix = 1
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
allowed_x_prefix = 1
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get, headers={
                'X-Forwarded-Prefix': '/sb',
                })

            # /
            r = get('/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/sb/common.css?a=static"' in html)
            self.assertTrue('href="/sb/index.css?a=static"' in html)
            self.assertTrue('src="/sb/common.js?a=static"' in html)
            self.assertTrue('src="/sb/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a>WebScrapBook</a>/</h1>' in html)
            self.assertTrue('data-base="/sb" data-path="/"' in html)

            # /subdir/
            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/sb/subdir/')

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/sb/common.css?a=static"' in html)
            self.assertTrue('href="/sb/index.css?a=static"' in html)
            self.assertTrue('src="/sb/common.js?a=static"' in html)
            self.assertTrue('src="/sb/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a href="/sb/">WebScrapBook</a>/<a>subdir</a>/</h1>' in html)
            self.assertTrue('data-base="/sb" data-path="/subdir/"' in html)

    def test_x_host(self):
        # x_.. = 0
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
allowed_x_proto = 0
allowed_x_host = 0
allowed_x_port = 0
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            # host + port
            get = partial(c.get, headers={
                'X-Forwarded-Proto': 'https',
                'X-Forwarded-Host': 'example.com',
                'X-Forwarded-Port': '8000',
                })

            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/')

        # x_.. = 1
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
allowed_x_proto = 1
allowed_x_host = 1
allowed_x_port = 1
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            # host + port
            get = partial(c.get, headers={
                'X-Forwarded-Proto': 'https',
                'X-Forwarded-Host': 'example.com',
                'X-Forwarded-Port': '8000',
                })

            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'https://example.com:8000/subdir/')

            # host:port
            get = partial(c.get, headers={
                'X-Forwarded-Proto': 'https',
                'X-Forwarded-Host': 'example.com:8888',
                })

            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'https://example.com:8888/subdir/')

            # host:port + port
            get = partial(c.get, headers={
                'X-Forwarded-Proto': 'https',
                'X-Forwarded-Host': 'example.com:8888',
                'X-Forwarded-Port': '8000',
                })

            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'https://example.com:8000/subdir/')

    # emulate that the app is run behind a reverse proxy server at "example.com"
    @mock.patch('werkzeug.wrappers.base_request.BaseRequest.host', 'example.com')
    def test_x_for(self):
        # allowed_x_for = 0
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
allowed_x_for = 0
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            # single value
            get = partial(c.get, headers={
                'X-Forwarded-For': '192.168.0.100',
                })

            r = get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(request.remote_addr, '127.0.0.1')
            data = r.json
            self.assertTrue(data['data']['app']['is_local'])

            # multiple values
            get = partial(c.get, headers={
                'X-Forwarded-For': '203.0.113.195, 70.41.3.18, 150.172.238.178',
                })

            r = get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(request.remote_addr, '127.0.0.1')
            data = r.json
            self.assertTrue(data['data']['app']['is_local'])

        # allowed_x_for = 1
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
allowed_x_for = 1
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            # single value
            get = partial(c.get, headers={
                'X-Forwarded-For': '192.168.0.100',
                })

            r = get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(request.remote_addr, '192.168.0.100')
            data = r.json
            self.assertFalse(data['data']['app']['is_local'])

            # multiple values
            get = partial(c.get, headers={
                'X-Forwarded-For': '203.0.113.195, 70.41.3.18, 150.172.238.178',
                })

            r = get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(request.remote_addr, '150.172.238.178')
            data = r.json
            self.assertFalse(data['data']['app']['is_local'])

        # allowed_x_for > 1
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
allowed_x_for = 2
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            # single value
            get = partial(c.get, headers={
                'X-Forwarded-For': '192.168.0.100',
                })

            r = get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(request.remote_addr, '127.0.0.1')
            data = r.json
            self.assertTrue(data['data']['app']['is_local'])

            # multiple values
            get = partial(c.get, headers={
                'X-Forwarded-For': '203.0.113.195, 70.41.3.18, 150.172.238.178',
                })

            r = get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(request.remote_addr, '70.41.3.18')
            data = r.json
            self.assertFalse(data['data']['app']['is_local'])

class TestAuth(unittest.TestCase):
    def simple_auth_headers(self, user, password):
        credentials = b64encode('{}:{}'.format(user, password).encode('utf-8')).decode('utf-8')
        return {'Authorization': 'Basic {}'.format(credentials)}

    def simple_auth_check(self, response):
        self.assertRegex(response.headers['WWW-Authenticate'], r'Basic realm="([^"]*)"')

    def test_basic(self):
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[auth "user"]
user = user
pw = pass
pw_salt = 
pw_type = plain
permission = all

[auth "user1"]
user = user1
pw = pass1salt
pw_salt = salt
pw_type = plain
permission = all

[auth "user2"]
user = user2
pw = 408b0a14ed182f24415c327b90981c3d89051920
pw_salt = salt2
pw_type = sha1
permission = all
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get)

            # no auth input
            r = get('/')
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            # anonymous
            r = get('/', headers=self.simple_auth_headers('', ''))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            r = get('/', headers=self.simple_auth_headers('', 'pass'))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            # unknown
            r = get('/', headers=self.simple_auth_headers('nonexist', ''))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            r = get('/', headers=self.simple_auth_headers('nonexist', 'pass'))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            # user
            r = get('/', headers=self.simple_auth_headers('user', 'pass'))
            self.assertEqual(r.status_code, 200)

            r = get('/', headers=self.simple_auth_headers('user', ''))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            r = get('/', headers=self.simple_auth_headers('user', 'passsalt'))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            r = get('/', headers=self.simple_auth_headers('user', 'pass1'))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            # user1
            r = get('/', headers=self.simple_auth_headers('user1', 'pass1'))
            self.assertEqual(r.status_code, 200)

            r = get('/', headers=self.simple_auth_headers('user1', 'pass'))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            # user2
            r = get('/', headers=self.simple_auth_headers('user2', 'pass2'))
            self.assertEqual(r.status_code, 200)

            r = get('/', headers=self.simple_auth_headers('user2', 'pass'))
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

    def test_permission(self):
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[auth "user1"]
user = user1
pw = passsalt
pw_salt = salt
pw_type = plain
permission = all

[auth "user2"]
user = user2
pw = passsalt
pw_salt = salt
pw_type = plain
permission = read

[auth "user3"]
user = user3
pw = passsalt
pw_salt = salt
pw_type = plain
permission = view

[auth "user4"]
user = user4
pw = passsalt
pw_salt = salt
pw_type = plain
permission =
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            try:
                # no auth input
                get = partial(c.get)
                post = partial(c.post)

                r = get('/')
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/index.html', query_string={'a': 'source'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/common.css', query_string={'a': 'static'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'config', 'f': 'json'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'token'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = post('/temp/test.txt', data={
                    'token': token(get),
                    'a': 'save',
                    'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                    })
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                # user1 - all
                get = partial(c.get, headers=self.simple_auth_headers('user1', 'pass'), buffered=True)
                post = partial(c.post, headers=self.simple_auth_headers('user1', 'pass'))

                r = get('/')
                self.assertEqual(r.status_code, 200)

                r = get('/index.html', query_string={'a': 'source'})
                self.assertEqual(r.status_code, 200)

                r = get('/common.css', query_string={'a': 'static'})
                self.assertEqual(r.status_code, 200)

                r = get('/', query_string={'a': 'config', 'f': 'json'})
                self.assertEqual(r.status_code, 200)

                r = get('/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 200)

                r = get('/', query_string={'a': 'token'})
                self.assertEqual(r.status_code, 200)

                r = post('/', data={
                    'token': token(get),
                    'a': 'lock',
                    'name': 'test',
                    })
                self.assertEqual(r.status_code, 204)

                r = post('/', data={
                    'token': token(get),
                    'a': 'unlock',
                    'name': 'test',
                    })
                self.assertEqual(r.status_code, 204)

                r = post('/temp/subdir', data={
                    'token': token(get),
                    'a': 'mkdir',
                    })
                self.assertEqual(r.status_code, 204)

                r = post('/temp/test.txt', data={
                    'token': token(get),
                    'a': 'save',
                    'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                    })
                self.assertEqual(r.status_code, 204)

                r = post('/temp/test.txt', data={
                    'token': token(get),
                    'a': 'delete',
                    })
                self.assertEqual(r.status_code, 204)

                # user2 - read
                get = partial(c.get, headers=self.simple_auth_headers('user2', 'pass'), buffered=True)
                post = partial(c.post, headers=self.simple_auth_headers('user2', 'pass'))

                r = get('/')
                self.assertEqual(r.status_code, 200)

                r = get('/index.html', query_string={'a': 'source'})
                self.assertEqual(r.status_code, 200)

                r = get('/common.css', query_string={'a': 'static'})
                self.assertEqual(r.status_code, 200)

                r = get('/', query_string={'a': 'config', 'f': 'json'})
                self.assertEqual(r.status_code, 200)

                r = get('/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 200)

                r = get('/', query_string={'a': 'token'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = post('/temp/test.txt', data={
                    'token': token(get),
                    'a': 'save',
                    'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                    })
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                # user3 - view
                get = partial(c.get, headers=self.simple_auth_headers('user3', 'pass'), buffered=True)
                post = partial(c.post, headers=self.simple_auth_headers('user3', 'pass'))

                r = get('/')
                self.assertEqual(r.status_code, 200)

                r = get('/index.html', query_string={'a': 'source'})
                self.assertEqual(r.status_code, 200)

                r = get('/common.css', query_string={'a': 'static'})
                self.assertEqual(r.status_code, 200)

                r = get('/', query_string={'a': 'config', 'f': 'json'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'token'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = post('/temp/test.txt', data={
                    'token': token(get),
                    'a': 'save',
                    'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                    })
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                # user4 - none
                get = partial(c.get, headers=self.simple_auth_headers('user4', 'pass'))
                post = partial(c.post, headers=self.simple_auth_headers('user4', 'pass'))

                r = get('/')
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/index.html', query_string={'a': 'source'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/common.css', query_string={'a': 'static'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'config', 'f': 'json'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'token'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = post('/temp/test.txt', data={
                    'token': token(get),
                    'a': 'save',
                    'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                    })
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)
            finally:
                try:
                    shutil.rmtree(os.path.join(server_root, 'temp'))
                except NotADirectoryError:
                    os.remove(os.path.join(server_root, 'temp'))
                except FileNotFoundError:
                    pass

    def test_anonymous(self):
        # Check if no input works same as empty user and password.
        # Check if permission for an anonymous user works.
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[auth "anonymous"]
user =
pw =
pw_salt =
pw_type = plain
permission = view
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            # no auth input
            get = partial(c.get)
            post = partial(c.post)

            r = get('/')
            self.assertEqual(r.status_code, 200)

            r = get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            r = get('/', query_string={'a': 'token'})
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            # anonymous
            get = partial(get, headers=self.simple_auth_headers('', ''))
            post = partial(post, headers=self.simple_auth_headers('', ''))

            r = get('/')
            self.assertEqual(r.status_code, 200)

            r = get('/', query_string={'a': 'config', 'f': 'json'})
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

            r = get('/', query_string={'a': 'token'})
            self.assertEqual(r.status_code, 401)
            self.simple_auth_check(r)

if __name__ == '__main__':
    unittest.main()
