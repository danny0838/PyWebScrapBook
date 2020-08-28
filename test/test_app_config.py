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
from webscrapbook.app import make_app, action_handler

root_dir = os.path.abspath(os.path.dirname(__file__))
server_root = os.path.join(root_dir, 'test_app_config')
server_config = os.path.join(server_root, WSB_DIR, WSB_LOCAL_CONFIG)

all_actions = [attr for attr in dir(action_handler) if not attr.startswith('_')]
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

        # base = /scrap%20%E6%9B%B8
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
base = /scrap%20%E6%9B%B8
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get)

            # /
            r = get('/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/scrap%20%E6%9B%B8/common.css?a=static"' in html)
            self.assertTrue('href="/scrap%20%E6%9B%B8/index.css?a=static"' in html)
            self.assertTrue('src="/scrap%20%E6%9B%B8/common.js?a=static"' in html)
            self.assertTrue('src="/scrap%20%E6%9B%B8/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a>WebScrapBook</a>/</h1>' in html)
            self.assertTrue('data-base="/scrap 書" data-path="/"' in html)

            # /subdir/
            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/scrap%20%E6%9B%B8/subdir/')

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/scrap%20%E6%9B%B8/common.css?a=static"' in html)
            self.assertTrue('href="/scrap%20%E6%9B%B8/index.css?a=static"' in html)
            self.assertTrue('src="/scrap%20%E6%9B%B8/common.js?a=static"' in html)
            self.assertTrue('src="/scrap%20%E6%9B%B8/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a href="/scrap%20%E6%9B%B8/">WebScrapBook</a>/<a>subdir</a>/</h1>' in html)
            self.assertTrue('data-base="/scrap 書" data-path="/subdir/"' in html)

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
                'X-Forwarded-Prefix': '/scrap 書',
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
                'X-Forwarded-Prefix': '/scrap 書'.encode('UTF-8'),
                })

            # /
            r = get('/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/scrap%20%E6%9B%B8/common.css?a=static"' in html)
            self.assertTrue('href="/scrap%20%E6%9B%B8/index.css?a=static"' in html)
            self.assertTrue('src="/scrap%20%E6%9B%B8/common.js?a=static"' in html)
            self.assertTrue('src="/scrap%20%E6%9B%B8/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a>WebScrapBook</a>/</h1>' in html)
            self.assertTrue('data-base="/scrap 書" data-path="/"' in html)

            # /subdir/
            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/scrap%20%E6%9B%B8/subdir/')

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')

            self.assertTrue('href="/scrap%20%E6%9B%B8/common.css?a=static"' in html)
            self.assertTrue('href="/scrap%20%E6%9B%B8/index.css?a=static"' in html)
            self.assertTrue('src="/scrap%20%E6%9B%B8/common.js?a=static"' in html)
            self.assertTrue('src="/scrap%20%E6%9B%B8/index.js?a=static"' in html)

            self.assertTrue('<h1 id="header" class="breadcrumbs"><a href="/scrap%20%E6%9B%B8/">WebScrapBook</a>/<a>subdir</a>/</h1>' in html)
            self.assertTrue('data-base="/scrap 書" data-path="/subdir/"' in html)

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

    def simple_auth_check(self, response, bool=True):
        if bool:
            self.assertRegex(response.headers['WWW-Authenticate'], r'Basic realm="([^"]*)"')
        else:
            with self.assertRaises(KeyError):
                response.headers['WWW-Authenticate']

    @mock.patch('webscrapbook.app.ActionHandler._handle_action', return_value='')
    @mock.patch('webscrapbook.app.get_permission')
    def test_get_permission(self, mock_perm, *_):
        """Check if HTTP authorization info is passed to get_permission()."""
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[auth "anony"]
user =
pw = salt
pw_salt = salt
pw_type = plain
permission = view
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            for method in ('HEAD', 'GET', 'POST'):
                for auth in (None, ('', ''), ('user', ''), ('', 'pass'), ('user', 'pass')):
                    with self.subTest(method=method, auth=auth):
                        if auth is None:
                            headers = None
                            expected = None
                        else:
                            user, pw = auth
                            headers = self.simple_auth_headers(user, pw)
                            expected = {'username': user, 'password': pw}

                        mock_perm.reset_mock()
                        c.open('/', method=method, headers=headers)
                        self.assertEqual(mock_perm.call_args[0][0], expected)

    @mock.patch('webscrapbook.app.ActionHandler._handle_action', return_value='')
    @mock.patch('webscrapbook.app.verify_authorization')
    def test_verify_authorization(self, mock_auth, *_):
        """Check if action is passed to verify_authorization()."""
        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            for method in ('HEAD', 'GET', 'POST'):
                for action in [None, *all_actions]:
                    with self.subTest(method=method, action=action):
                        if action is None:
                            query = None
                            expected = 'view'
                        else:
                            query = {'a': action}
                            expected = action

                        mock_auth.reset_mock()
                        c.open('/', method=method, query_string=query)
                        self.assertEqual(mock_auth.call_args[0][1], expected)

    def test_request(self):
        """Random request challanges."""
        with open(server_config, 'w', encoding='UTF-8') as f:
            f.write("""\
[auth "anony"]
user =
pw = salt
pw_salt = salt
pw_type = plain
permission = view

[auth "user1"]
user = user1
pw = pass1salt
pw_salt = salt
pw_type = plain
permission = read

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
            try:
                # no auth input = anonymous
                get = partial(c.get)
                post = partial(c.post)

                r = get('/')
                self.assertEqual(r.status_code, 200)
                self.simple_auth_check(r, False)

                r = get('/', query_string={'a': 'config', 'f': 'json'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                r = get('/', query_string={'a': 'token'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                # user1 - read
                get = partial(c.get, headers=self.simple_auth_headers('user1', 'pass1'), buffered=True)
                post = partial(c.post, headers=self.simple_auth_headers('user1', 'pass1'))

                r = get('/index.html', query_string={'a': 'source'})
                self.assertEqual(r.status_code, 200)
                self.simple_auth_check(r, False)

                r = get('/', query_string={'a': 'list', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.simple_auth_check(r, False)

                r = get('/', query_string={'a': 'token'})
                self.assertEqual(r.status_code, 401)
                self.simple_auth_check(r)

                # user2 - all
                get = partial(c.get, headers=self.simple_auth_headers('user2', 'pass2'), buffered=True)
                post = partial(c.post, headers=self.simple_auth_headers('user2', 'pass2'))

                r = get('/common.css', query_string={'a': 'static'})
                self.assertEqual(r.status_code, 200)
                self.simple_auth_check(r, False)

                r = get('/', query_string={'a': 'config', 'f': 'json'})
                self.assertEqual(r.status_code, 200)
                self.simple_auth_check(r, False)

                r = post('/temp/test.txt', data={
                    'token': token(get),
                    'a': 'save',
                    'text': 'ABC 你好'.encode('UTF-8').decode('ISO-8859-1'),
                    })
                self.assertEqual(r.status_code, 204)
                self.simple_auth_check(r, False)
            finally:
                try:
                    shutil.rmtree(os.path.join(server_root, 'temp'))
                except NotADirectoryError:
                    os.remove(os.path.join(server_root, 'temp'))
                except FileNotFoundError:
                    pass

if __name__ == '__main__':
    unittest.main()
