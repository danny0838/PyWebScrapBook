# @FIXME: Some cases have an unclosed file issue. Although adding
#     buffered=True temporarily suppresses it, a further investigation
#     for a possible leak of the source code is pending.
import os
import shutil
import tempfile
import unittest
from base64 import b64encode
from functools import partial
from unittest import mock

from flask import request

from webscrapbook import WSB_DIR
from webscrapbook import app as wsbapp
from webscrapbook.app import make_app

from . import PROG_DIR, ROOT_DIR, TEMP_DIR, TestBookMixin

THEMES_DIR = os.path.join(PROG_DIR, 'themes')


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='config-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(os.path.join(_tmpdir.name, 'd'))
    shutil.copytree(os.path.join(ROOT_DIR, 'test_app_config'), tmpdir)

    global server_root
    server_root = tmpdir

    # mock out user config
    global WSB_USER_DIR
    WSB_USER_DIR = os.path.join(server_root, 'wsb')
    global mockings
    mockings = (
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', WSB_USER_DIR),
        mock.patch('webscrapbook.WSB_USER_DIR', WSB_USER_DIR),
        mock.patch('webscrapbook.WSB_USER_CONFIG', os.devnull),
    )
    for mocking in mockings:
        mocking.start()


def tearDownModule():
    # cleanup the temp directory
    _tmpdir.cleanup()

    # stop mock
    for mocking in mockings:
        mocking.stop()


def token(get):
    """Wrapper to quickly retrieve a token."""
    return get('/', query_string={'a': 'token'}).data.decode('UTF-8')


class TestApp(TestBookMixin, unittest.TestCase):
    def test_name(self):
        self.init_host(server_root, config="""[app]
name = mywsb
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get)

            # /
            r = get('/')
            html = r.data.decode('UTF-8')
            self.assertIn('<h1 id="header" class="breadcrumbs"><a>mywsb</a>/</h1>', html)

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')
            self.assertIn('<h1 id="header" class="breadcrumbs"><a href="/">mywsb</a>/<a>subdir</a>/</h1>', html)

    def test_name2(self):
        """app.name should be used as auth realm"""
        self.init_host(server_root, config="""[app]
name = mywsb

[auth "id1"]
user = user1
pw = pass1salt
pw_salt = salt
pw_type = plain
permission = all
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get)

            # /
            r = get('/')
            self.assertEqual(r.www_authenticate['realm'], 'mywsb')

    @mock.patch('jinja2.FileSystemLoader')
    def test_theme(self, mock_loader):
        self.init_host(server_root, config="""[app]
theme = default
""")

        make_app(server_root)
        self.assertListEqual([os.path.normcase(i) for i in mock_loader.call_args[0][0]], [
            os.path.normcase(os.path.join(server_root, WSB_DIR, 'themes', 'default', 'templates')),
            os.path.normcase(os.path.abspath(os.path.join(WSB_USER_DIR, 'themes', 'default', 'templates'))),
            os.path.normcase(os.path.abspath(os.path.join(THEMES_DIR, 'default', 'templates'))),
        ])

    def test_root(self):
        self.init_host(server_root, config="""[app]
root = subdir
""")

        os.makedirs(os.path.join(server_root, WSB_DIR, 'themes', 'default', 'static'))
        with open(os.path.join(server_root, WSB_DIR, 'themes', 'default', 'static', 'index.js'), 'w', encoding='UTF-8') as fh:
            fh.write('console.log("test");')

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get, buffered=True)
            post = partial(c.post, buffered=True)

            r = get('/index.html')
            html = r.data.decode('UTF-8')
            self.assertEqual(html, 'Subdirectory Hello World! 你好')

            # check if server dependent files are at the right path
            r = get('/index.js', query_string={'a': 'static'})
            self.assertEqual(r.data.decode('UTF-8'), 'console.log("test");')

            t = token(post)
            self.assertEqual(len(os.listdir(os.path.join(server_root, WSB_DIR, 'server', 'tokens'))), 1)

            r = post('/', data={
                'token': t,
                'a': 'lock',
                'f': 'json',
                'name': 'test',
            })
            self.assertTrue(os.path.lexists(os.path.join(server_root, WSB_DIR, 'locks', '098f6bcd4621d373cade4e832627b4f6.lock')))

    def test_x_prefix(self):
        # allowed_x_prefix = 0
        self.init_host(server_root, config="""[app]
allowed_x_prefix = 0
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get, headers={
                'X-Forwarded-Prefix': '/scrap',
            })

            # /
            r = get('/')
            html = r.data.decode('UTF-8')

            self.assertIn('href="/common.css?a=static"', html)
            self.assertIn('href="/index.css?a=static"', html)
            self.assertIn('src="/common.js?a=static"', html)
            self.assertIn('src="/index.js?a=static"', html)

            self.assertIn('<h1 id="header" class="breadcrumbs"><a>WebScrapBook</a>/</h1>', html)
            self.assertIn('data-base="" data-path="/"', html)

            # /subdir/
            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/subdir/')

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')

            self.assertIn('href="/common.css?a=static"', html)
            self.assertIn('href="/index.css?a=static"', html)
            self.assertIn('src="/common.js?a=static"', html)
            self.assertIn('src="/index.js?a=static"', html)

            self.assertIn('<h1 id="header" class="breadcrumbs"><a href="/">WebScrapBook</a>/<a>subdir</a>/</h1>', html)
            self.assertIn('data-base="" data-path="/subdir/"', html)

        # allowed_x_prefix = 1
        self.init_host(server_root, config="""[app]
allowed_x_prefix = 1
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            get = partial(c.get, headers={
                'X-Forwarded-Prefix': '/scrap',
            })

            # /
            r = get('/')
            html = r.data.decode('UTF-8')

            self.assertIn('href="/scrap/common.css?a=static"', html)
            self.assertIn('href="/scrap/index.css?a=static"', html)
            self.assertIn('src="/scrap/common.js?a=static"', html)
            self.assertIn('src="/scrap/index.js?a=static"', html)

            self.assertIn('<h1 id="header" class="breadcrumbs"><a>WebScrapBook</a>/</h1>', html)
            self.assertIn('data-base="/scrap" data-path="/"', html)

            # /subdir/
            r = get('/subdir')
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers['Location'], 'http://localhost/scrap/subdir/')

            # /subdir/
            r = get('/subdir/')
            html = r.data.decode('UTF-8')

            self.assertIn('href="/scrap/common.css?a=static"', html)
            self.assertIn('href="/scrap/index.css?a=static"', html)
            self.assertIn('src="/scrap/common.js?a=static"', html)
            self.assertIn('src="/scrap/index.js?a=static"', html)

            self.assertIn('<h1 id="header" class="breadcrumbs"><a href="/scrap/">WebScrapBook</a>/<a>subdir</a>/</h1>', html)
            self.assertIn('data-base="/scrap" data-path="/subdir/"', html)

    def test_x_host(self):
        # x_.. = 0
        self.init_host(server_root, config="""[app]
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
        self.init_host(server_root, config="""[app]
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
    @mock.patch('werkzeug.wrappers.request.Request.host', 'example.com')
    def test_x_for(self):
        # allowed_x_for = 0
        self.init_host(server_root, config="""[app]
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
        self.init_host(server_root, config="""[app]
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
        self.init_host(server_root, config="""[app]
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

    def test_csp(self):
        # content_security_policy == 'strict'
        self.init_host(server_root, config="""[app]
content_security_policy = strict
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            r = c.get('/')
            self.assertEqual(r.headers['Content-Security-Policy'], "frame-ancestors 'none';")
            self.assertEqual(r.headers['X-Frame-Options'], 'deny')

            r = c.get('/index.html', buffered=True)
            self.assertEqual(r.headers['Content-Security-Policy'], "connect-src 'none'; form-action 'none';")

            r = c.get('/index.md')
            self.assertEqual(r.headers['Content-Security-Policy'], "connect-src 'none'; form-action 'none';")

        # content_security_policy == ''
        self.init_host(server_root, config="""[app]
content_security_policy =
""")

        app = make_app(server_root)
        app.testing = True
        with app.test_client() as c:
            r = c.get('/')
            self.assertIsNone(r.headers.get('Content-Security-Policy'))
            self.assertIsNone(r.headers.get('X-Frame-Options'))

            r = c.get('/index.html', buffered=True)
            self.assertIsNone(r.headers.get('Content-Security-Policy'))

            r = c.get('/index.md')
            self.assertIsNone(r.headers.get('Content-Security-Policy'))


class TestAuth(TestBookMixin, unittest.TestCase):
    def simple_auth_headers(self, user, password):
        credentials = b64encode(f'{user}:{password}'.encode('utf-8')).decode('utf-8')
        return {'Authorization': f'Basic {credentials}'}

    def simple_auth_check(self, response, has_auth=True):
        if has_auth:
            self.assertIn('realm', response.www_authenticate)
        else:
            with self.assertRaises(KeyError):
                response.headers['WWW-Authenticate']

    @mock.patch('webscrapbook.app.get_permission', side_effect=SystemExit)
    def test_get_permission(self, mock_perm):
        """Check if HTTP authorization info is passed to get_permission()."""
        self.init_host(server_root, config="""\
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
                            user = pw = ''
                            headers = None
                        else:
                            user, pw = auth
                            headers = self.simple_auth_headers(user, pw)

                        try:
                            c.open('/', method=method, headers=headers)
                        except SystemExit:
                            pass

                        mock_perm.assert_called_with(user, pw, mock.ANY)

    @mock.patch('webscrapbook.app.verify_authorization', side_effect=SystemExit)
    def test_verify_authorization(self, mock_auth):
        """Check if action is passed to verify_authorization()."""
        self.init_host(server_root, config="""\
[auth "anony"]
user =
pw = salt
pw_salt = salt
pw_type = plain
permission = view
""")
        all_actions = (fn[7:] for fn in dir(wsbapp) if fn.startswith('action_'))
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

                        try:
                            c.open('/', method=method, query_string=query)
                        except SystemExit:
                            pass

                        mock_auth.assert_called_with(mock.ANY, expected)

    def test_request(self):
        """Random request challanges."""
        self.init_host(server_root, config="""\
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
                    'token': token(post),
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
