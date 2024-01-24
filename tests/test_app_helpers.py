import hashlib
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

from flask import current_app, request

import webscrapbook
from webscrapbook import WSB_DIR
from webscrapbook import app as wsbapp
from webscrapbook import util
from webscrapbook._polyfill import zipfile

from . import (
    DUMMY_TS,
    DUMMY_TS2,
    DUMMY_TS3,
    DUMMY_TS4,
    DUMMY_ZIP_DT,
    DUMMY_ZIP_DT2,
    DUMMY_ZIP_DT3,
    DUMMY_ZIP_DT4,
    ROOT_DIR,
    TEMP_DIR,
    require_junction,
    require_sep,
    require_symlink,
    test_file_cleanup,
)


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='helpers-', dir=TEMP_DIR)
    tmpdir = _tmpdir.name

    # mock out user config
    global mockings
    mockings = (
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.devnull),
        mock.patch('webscrapbook.WSB_USER_DIR', os.devnull),
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


class Test(unittest.TestCase):
    def setup_test(self, subdir):
        root = tempfile.mkdtemp(dir=tmpdir)
        root = os.path.realpath(os.path.join(root, 'd'))
        shutil.copytree(os.path.join(ROOT_DIR, 'test_app_helpers', subdir), root)
        return root


class TestFunctions(Test):
    def test_is_local_access(self):
        root = self.setup_test('general')
        app = wsbapp.make_app(root)

        # host is localhost
        with app.test_request_context(
            '/',
            base_url='http://127.0.0.1',
            environ_base={'REMOTE_ADDR': '192.168.0.100'},
        ):
            self.assertTrue(wsbapp.is_local_access())

        # host (with port) is localhost
        with app.test_request_context(
            '/',
            base_url='http://127.0.0.1:8000',
            environ_base={'REMOTE_ADDR': '192.168.0.100'},
        ):
            self.assertTrue(wsbapp.is_local_access())

        # remote is localhost
        with app.test_request_context(
            '/',
            base_url='http://192.168.0.1',
            environ_base={'REMOTE_ADDR': '127.0.0.1'},
        ):
            self.assertTrue(wsbapp.is_local_access())

        # host = remote
        with app.test_request_context(
            '/',
            base_url='http://example.com',
            environ_base={'REMOTE_ADDR': 'example.com'},
        ):
            self.assertTrue(wsbapp.is_local_access())

        # host (with port) = remote
        with app.test_request_context(
            '/',
            base_url='http://example.com:8000',
            environ_base={'REMOTE_ADDR': 'example.com'},
        ):
            self.assertTrue(wsbapp.is_local_access())

        # otherwise non-local
        with app.test_request_context(
            '/',
            base_url='http://example.com',
            environ_base={'REMOTE_ADDR': '192.168.0.100'},
        ):
            self.assertFalse(wsbapp.is_local_access())

    def test_get_breadcrumbs(self):
        # directory
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/directory/'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('directory', '/path/to/directory/', '/', True)
        ])

        # conflicting directory/file
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/fake.ext!/'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('fake.ext!', '/path/to/fake.ext!/', '/', True),
        ])

        # sub-archive path(s)
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', True),
        ])

        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', 'subdir'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/subdir/', '/', True),
        ])

        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', 'nested1.zip', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('nested1.zip', '/path/to/archive.ext!/nested1.zip!/', '!/', True),
        ])

        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', 'nested1.zip', 'subdir'])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('nested1.zip', '/path/to/archive.ext!/nested1.zip!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/nested1.zip!/subdir/', '/', True),
        ])

        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/archive.ext', 'subdir/nested1.zip', ''])), [
            ('.', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('archive.ext', '/path/to/archive.ext!/', '!/', False),
            ('subdir', '/path/to/archive.ext!/subdir/', '/', False),
            ('nested1.zip', '/path/to/archive.ext!/subdir/nested1.zip!/', '!/', True),
        ])

        # base
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/directory/'], base='/wsb')), [
            ('.', '/wsb/', '/', False),
            ('path', '/wsb/path/', '/', False),
            ('to', '/wsb/path/to/', '/', False),
            ('directory', '/wsb/path/to/directory/', '/', True),
        ])

        # base (with slash)
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/directory/'], base='/wsb/')), [
            ('.', '/wsb/', '/', False),
            ('path', '/wsb/path/', '/', False),
            ('to', '/wsb/path/to/', '/', False),
            ('directory', '/wsb/path/to/directory/', '/', True),
        ])

        # topname
        self.assertEqual(list(wsbapp.get_breadcrumbs(['/path/to/directory/'], topname='MyWsb')), [
            ('MyWsb', '/', '/', False),
            ('path', '/path/', '/', False),
            ('to', '/path/to/', '/', False),
            ('directory', '/path/to/directory/', '/', True)
        ])

    def test_make_app1(self):
        # pass root
        root = self.setup_test('make_app1')

        app = wsbapp.make_app(root)
        with app.app_context():
            self.assertEqual(current_app.config['WEBSCRAPBOOK_HOST'].config['app']['name'], 'mywsb1')

    def test_make_app2(self):
        # pass root, config
        root = self.setup_test('make_app1')
        config_dir = self.setup_test('make_app2')
        config = webscrapbook.Config()
        config.load(config_dir)

        app = wsbapp.make_app(root, config)
        with app.app_context():
            self.assertEqual(current_app.config['WEBSCRAPBOOK_HOST'].config['app']['name'], 'mywsb2')


class TestRequest(Test):
    def setUp(self):
        self.root = self.setup_test('general')

    def test_action(self):
        app = wsbapp.make_app(self.root)
        with app.test_client() as c:
            c.get('/index.html')
            self.assertEqual(request.action, 'view')

            c.get('/index.html', query_string={'action': 'source'})
            self.assertEqual(request.action, 'source')

            c.get('/index.html', query_string={'a': 'source'})
            self.assertEqual(request.action, 'source')

            c.get('/index.html', query_string={'a': 'source', 'action': 'static'})
            self.assertEqual(request.action, 'static')

    def test_format(self):
        app = wsbapp.make_app(self.root)
        with app.test_client() as c:
            c.get('/index.html')
            self.assertEqual(request.format, None)

            c.get('/index.html', query_string={'format': 'json'})
            self.assertEqual(request.format, 'json')

            c.get('/index.html', query_string={'f': 'json'})
            self.assertEqual(request.format, 'json')

            c.get('/index.html', query_string={'f': 'json', 'format': 'sse'})
            self.assertEqual(request.format, 'sse')


class TestHandlers(Test):
    def setUp(self):
        self.root = self.setup_test('general')

    def test_handle_error(self):
        app = wsbapp.make_app(self.root)

        # json
        with app.test_client() as c:
            r = c.get('/nonexist', query_string={'a': 'list', 'f': 'json'})
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.headers['Content-Type'], 'application/json')
            self.assertEqual(r.json, {
                'error': {
                    'status': 404,
                    'message': 'Directory does not exist.'
                }
            })

        # other
        with app.test_client() as c:
            r = c.get('/nonexist')
            self.assertEqual(r.status_code, 404)
            html = r.data.decode('UTF-8')
            self.assertIn('<h1>Not Found</h1>', html)


class TestWebHost(Test):
    def setUp(self):
        self.root = self.setup_test('general')
        self.token_dir = os.path.join(self.root, WSB_DIR, 'server', 'tokens')
        os.makedirs(self.token_dir, exist_ok=True)

    @mock.patch('webscrapbook.app.WebHost.token_check_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_DEFAULT_EXPIRY', 10)
    def test_token_acquire1(self, mock_check):
        now = time.time()
        expected_expire_time = int(now) + 10

        handler = wsbapp.WebHost(self.root)
        token = handler.token_acquire()
        token_file = os.path.join(self.token_dir, token)

        self.assertTrue(os.path.isfile(token_file))
        with open(token_file, 'r', encoding='UTF-8') as fh:
            self.assertAlmostEqual(int(fh.read()), expected_expire_time, delta=1)
        self.assertAlmostEqual(mock_check.call_args[0][0], now, delta=1)

    @mock.patch('webscrapbook.app.WebHost.token_check_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_DEFAULT_EXPIRY', 30)
    def test_token_acquire2(self, mock_check):
        now = 30000
        expected_expire_time = int(now) + 30

        handler = wsbapp.WebHost(self.root)
        token = handler.token_acquire(now)
        token_file = os.path.join(self.token_dir, token)

        self.assertTrue(os.path.isfile(token_file))
        with open(token_file, 'r', encoding='UTF-8') as fh:
            self.assertEqual(int(fh.read()), expected_expire_time)
        self.assertEqual(mock_check.call_args[0][0], now)

    def test_token_validate1(self):
        token = 'sampleToken'
        token_time = int(time.time()) + 3

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as fh:
            fh.write(str(token_time))

        handler = wsbapp.WebHost(self.root)
        self.assertTrue(handler.token_validate(token))

    def test_token_validate2(self):
        token = 'sampleToken'
        token_time = int(time.time()) - 3

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as fh:
            fh.write(str(token_time))

        handler = wsbapp.WebHost(self.root)
        self.assertFalse(handler.token_validate(token))

    def test_token_validate3(self):
        token = 'sampleToken'
        now = 30000
        token_time = 30001

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as fh:
            fh.write(str(token_time))

        handler = wsbapp.WebHost(self.root)
        self.assertTrue(handler.token_validate(token, now))

    def test_token_validate4(self):
        token = 'sampleToken'
        now = 30000
        token_time = 29999

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as fh:
            fh.write(str(token_time))

        handler = wsbapp.WebHost(self.root)
        self.assertFalse(handler.token_validate(token, now))

    def test_token_delete(self):
        token = 'sampleToken'

        token_file = os.path.join(self.token_dir, token)
        with open(token_file, 'w', encoding='UTF-8') as fh:
            fh.write(str(32768))

        handler = wsbapp.WebHost(self.root)
        handler.token_delete(token)
        self.assertFalse(os.path.exists(token_file))

    def test_token_delete_expire1(self):
        now = int(time.time())

        with open(os.path.join(self.token_dir, 'sampleToken1'), 'w', encoding='UTF-8') as fh:
            fh.write(str(now - 100))
        with open(os.path.join(self.token_dir, 'sampleToken2'), 'w', encoding='UTF-8') as fh:
            fh.write(str(now - 10))
        with open(os.path.join(self.token_dir, 'sampleToken3'), 'w', encoding='UTF-8') as fh:
            fh.write(str(now + 10))
        with open(os.path.join(self.token_dir, 'sampleToken4'), 'w', encoding='UTF-8') as fh:
            fh.write(str(now + 100))

        handler = wsbapp.WebHost(self.root)
        handler.token_delete_expire()

        self.assertFalse(os.path.exists(os.path.join(self.token_dir, 'sampleToken1')))
        self.assertFalse(os.path.exists(os.path.join(self.token_dir, 'sampleToken2')))
        self.assertTrue(os.path.exists(os.path.join(self.token_dir, 'sampleToken3')))
        self.assertTrue(os.path.exists(os.path.join(self.token_dir, 'sampleToken4')))

    def test_token_delete_expire2(self):
        now = 30000

        with open(os.path.join(self.token_dir, 'sampleToken1'), 'w', encoding='UTF-8') as fh:
            fh.write(str(29000))
        with open(os.path.join(self.token_dir, 'sampleToken2'), 'w', encoding='UTF-8') as fh:
            fh.write(str(29100))
        with open(os.path.join(self.token_dir, 'sampleToken3'), 'w', encoding='UTF-8') as fh:
            fh.write(str(30100))
        with open(os.path.join(self.token_dir, 'sampleToken4'), 'w', encoding='UTF-8') as fh:
            fh.write(str(30500))

        handler = wsbapp.WebHost(self.root)
        handler.token_delete_expire(now)

        self.assertFalse(os.path.exists(os.path.join(self.token_dir, 'sampleToken1')))
        self.assertFalse(os.path.exists(os.path.join(self.token_dir, 'sampleToken2')))
        self.assertTrue(os.path.exists(os.path.join(self.token_dir, 'sampleToken3')))
        self.assertTrue(os.path.exists(os.path.join(self.token_dir, 'sampleToken4')))

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    def test_token_check_delete_expire1(self, mock_delete):
        now = int(time.time())

        handler = wsbapp.WebHost(self.root)
        self.assertEqual(handler.token_last_purge, 0)

        handler.token_check_delete_expire()
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.token_last_purge, now, delta=1)

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_PURGE_INTERVAL', 1000)
    def test_token_check_delete_expire2(self, mock_delete):
        now = int(time.time())

        handler = wsbapp.WebHost(self.root)
        handler.token_last_purge = now - 1100

        handler.token_check_delete_expire()
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.token_last_purge, now, delta=1)

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_PURGE_INTERVAL', 1000)
    def test_token_check_delete_expire3(self, mock_delete):
        now = int(time.time())

        handler = wsbapp.WebHost(self.root)
        handler.token_last_purge = now - 900

        handler.token_check_delete_expire()
        mock_delete.assert_not_called()
        self.assertEqual(handler.token_last_purge, now - 900)

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_PURGE_INTERVAL', 1000)
    def test_token_check_delete_expire4(self, mock_delete):
        now = 40000

        handler = wsbapp.WebHost(self.root)
        handler.token_last_purge = now - 1100

        handler.token_check_delete_expire(now)
        self.assertAlmostEqual(mock_delete.call_args[0][0], now, delta=1)
        self.assertAlmostEqual(handler.token_last_purge, now, delta=1)

    @mock.patch('webscrapbook.app.WebHost.token_delete_expire')
    @mock.patch('webscrapbook.app.WebHost.TOKEN_PURGE_INTERVAL', 1000)
    def test_token_check_delete_expire5(self, mock_delete):
        now = 40000

        handler = wsbapp.WebHost(self.root)
        handler.token_last_purge = now - 900

        handler.token_check_delete_expire(now)
        mock_delete.assert_not_called()
        self.assertEqual(handler.token_last_purge, now - 900)

    @mock.patch('webscrapbook.app.check_password_hash', wraps=wsbapp.check_password_hash)
    def test_get_permission1(self, mock_encrypt):
        """Return corresponding permission for the matched user and '' for unmatched."""
        root = self.setup_test('get_permission1')
        app = wsbapp.make_app(root)
        with app.app_context():
            # check_password_hash should be called with the inputting password for the matched user
            mock_encrypt.reset_mock()

            self.assertEqual(wsbapp.host.get_permission('user1', 'pass1'), '')
            mock_encrypt.assert_called_with(
                'pbkdf2:sha1:1$z$ab55d4e716ba0d6cc1a7259f346c42280e09a1e3',
                'pass1',
            )

            self.assertEqual(wsbapp.host.get_permission('user2', 'pass2'), 'view')
            mock_encrypt.assert_called_with(
                'pbkdf2:sha1:1$ewiu$892bc69b184583b8c903328836a622284a279f2e',
                'pass2',
            )

            self.assertEqual(wsbapp.host.get_permission('user3', 'pass3'), 'read')
            mock_encrypt.assert_called_with(
                'pbkdf2:sha256:1$d$2b5a1bca9321ed5e9cf0a7ac1fbe4b786a746d11664748278fb1fd1ff8ac6ab4',
                'pass3',
            )

            self.assertEqual(wsbapp.host.get_permission('user4', 'pass4'), 'all')
            mock_encrypt.assert_called_with(
                'pbkdf2:sha256:1$D9tO$b62cd702008d95caf8c699ee76a00db468a5e0891f431475b9a0aeab148e43cb',
                'pass4',
            )

            # Password check should be handled by check_password_hash properly.
            # Here are just some quick fail tests for certain cases:
            # - empty input should not work
            # - inputting hashed value should not work
            mock_encrypt.reset_mock()

            self.assertEqual(wsbapp.host.get_permission('user4', ''), '')
            mock_encrypt.assert_called_with(
                'pbkdf2:sha256:1$D9tO$b62cd702008d95caf8c699ee76a00db468a5e0891f431475b9a0aeab148e43cb',
                '',
            )

            self.assertEqual(wsbapp.host.get_permission(
                'user4',
                'pbkdf2:sha256:1$D9tO$b62cd702008d95caf8c699ee76a00db468a5e0891f431475b9a0aeab148e43cb',
            ), '')
            mock_encrypt.assert_called_with(
                'pbkdf2:sha256:1$D9tO$b62cd702008d95caf8c699ee76a00db468a5e0891f431475b9a0aeab148e43cb',
                'pbkdf2:sha256:1$D9tO$b62cd702008d95caf8c699ee76a00db468a5e0891f431475b9a0aeab148e43cb',
            )

            # check_password_hash should NOT be called for an unmatched user
            mock_encrypt.reset_mock()

            self.assertEqual(wsbapp.host.get_permission('', ''), '')
            mock_encrypt.assert_not_called()

            self.assertEqual(wsbapp.host.get_permission('', 'pass'), '')
            mock_encrypt.assert_not_called()

            self.assertEqual(wsbapp.host.get_permission('userx', ''), '')
            mock_encrypt.assert_not_called()

            self.assertEqual(wsbapp.host.get_permission('userx', 'pass'), '')
            mock_encrypt.assert_not_called()

    @mock.patch('webscrapbook.app.check_password_hash', wraps=wsbapp.check_password_hash)
    def test_get_permission2(self, mock_encrypt):
        """Check against empty password without hashing if pw is empty."""
        root = self.setup_test('get_permission2')
        app = wsbapp.make_app(root)
        with app.app_context():
            # allow empty password
            self.assertEqual(wsbapp.host.get_permission('user1', ''), 'view')
            mock_encrypt.assert_not_called()

            # disallow non-empty password
            self.assertEqual(wsbapp.host.get_permission('user1', 'abc'), '')
            mock_encrypt.assert_not_called()

    @mock.patch('webscrapbook.app.check_password_hash', wraps=wsbapp.check_password_hash)
    def test_get_permission3(self, mock_encrypt):
        """Use permission for the first matched user and password."""
        root = self.setup_test('get_permission3')
        app = wsbapp.make_app(root)
        with app.app_context():
            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('', ''), 'view')
            mock_encrypt.assert_not_called()

            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('user1', 'pass1'), 'read')
            self.assertEqual(mock_encrypt.call_args_list[0][0], ('pbkdf2:sha1:1$B$ad86239f72026404244ba6de19d4270ad2ecf397', 'pass1'))
            self.assertEqual(mock_encrypt.call_args_list[1][0], ('pbkdf2:sha1:1$1$1cb0b20ced97f764a8ae152b282fc622b7d22303', 'pass1'))

    @mock.patch('webscrapbook.app.check_password_hash', wraps=wsbapp.check_password_hash)
    def test_get_permission4(self, mock_encrypt):
        """Read from cache for repeated user-password input."""
        root = self.setup_test('get_permission4')
        app = wsbapp.make_app(root)
        with app.app_context():
            # invalid user
            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('unknown', ''), '')
            mock_encrypt.assert_not_called()
            self.assertEqual(wsbapp.host._get_permission_cache, {})

            # invalid password
            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('user1', 'unknown'), '')
            mock_encrypt.assert_called_with(
                'pbkdf2:sha1:1$z$ab55d4e716ba0d6cc1a7259f346c42280e09a1e3',
                'unknown',
            )
            self.assertEqual(wsbapp.host._get_permission_cache, {})

            # invalid empty password
            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('', 'unknown'), '')
            mock_encrypt.assert_not_called()
            self.assertEqual(wsbapp.host._get_permission_cache, {})

            # anonymous
            cache_key1 = hashlib.sha512('\0'.encode('UTF-8')).digest()

            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('', ''), 'view')
            mock_encrypt.assert_not_called()
            self.assertEqual(wsbapp.host._get_permission_cache, {
                cache_key1: 'view',
            })

            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('', ''), 'view')
            mock_encrypt.assert_not_called()
            self.assertEqual(wsbapp.host._get_permission_cache, {
                cache_key1: 'view',
            })

            # user1
            cache_key2 = hashlib.sha512('user1\0pass1'.encode('UTF-8')).digest()

            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('user1', 'pass1'), 'all')
            mock_encrypt.assert_called_with(
                'pbkdf2:sha1:1$z$ab55d4e716ba0d6cc1a7259f346c42280e09a1e3',
                'pass1',
            )
            self.assertEqual(wsbapp.host._get_permission_cache, {
                cache_key1: 'view',
                cache_key2: 'all',
            })

            mock_encrypt.reset_mock()
            self.assertEqual(wsbapp.host.get_permission('user1', 'pass1'), 'all')
            mock_encrypt.assert_not_called()
            self.assertEqual(wsbapp.host._get_permission_cache, {
                cache_key1: 'view',
                cache_key2: 'all',
            })

    def test_check_permission(self):
        for action in {'view', 'info', 'source', 'download', 'static', 'unknown'}:
            with self.subTest(action=action):
                self.assertFalse(wsbapp.WebHost.check_permission('', action))
                self.assertTrue(wsbapp.WebHost.check_permission('view', action))
                self.assertTrue(wsbapp.WebHost.check_permission('read', action))
                self.assertTrue(wsbapp.WebHost.check_permission('all', action))

        for action in {'list', 'edit', 'editx', 'exec', 'browse', 'config', 'search'}:
            with self.subTest(action=action):
                self.assertFalse(wsbapp.WebHost.check_permission('', action))
                self.assertFalse(wsbapp.WebHost.check_permission('view', action))
                self.assertTrue(wsbapp.WebHost.check_permission('read', action))
                self.assertTrue(wsbapp.WebHost.check_permission('all', action))

        for action in {
            'token', 'lock', 'unlock',
            'mkdir', 'mkzip', 'save', 'delete', 'move', 'copy',
            'backup', 'unbackup', 'cache', 'check', 'export', 'import', 'query',
        }:
            with self.subTest(action=action):
                self.assertFalse(wsbapp.WebHost.check_permission('', action))
                self.assertFalse(wsbapp.WebHost.check_permission('view', action))
                self.assertFalse(wsbapp.WebHost.check_permission('read', action))
                self.assertTrue(wsbapp.WebHost.check_permission('all', action))


class TestFilesystemHelpers(unittest.TestCase):
    def test_file_info(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'listdir')
        dst2 = os.path.join(root, 'listdir', 'folder')
        dst3 = os.path.join(root, 'listdir', 'folder', '.gitkeep')
        dst4 = os.path.join(root, 'listdir', 'file.txt')
        os.makedirs(dst)
        os.makedirs(dst2)
        with open(dst3, 'w'):
            pass
        with open(dst4, 'w') as fh:
            fh.write('123')

        # nonexist
        self.assertEqual(
            wsbapp.file_info(os.path.join(dst, 'nonexist.file')),
            ('nonexist.file', None, None, None),
        )
        self.assertEqual(
            wsbapp.file_info(os.path.join(dst, 'deep', 'nonexist.file')),
            ('nonexist.file', None, None, None),
        )

        # file
        self.assertEqual(
            wsbapp.file_info(dst4),
            ('file.txt', 'file', 3, os.stat(dst4).st_mtime),
        )

        # dir
        self.assertEqual(
            wsbapp.file_info(dst2),
            ('folder', 'dir', None, os.stat(dst2).st_mtime),
        )

        # with base
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'subdir', 'file.txt')
        os.makedirs(os.path.dirname(dst))
        with open(dst, 'w') as fh:
            fh.write('123')

        self.assertEqual(
            wsbapp.file_info(dst, base=root),
            ('deep/subdir/file.txt', 'file', 3, os.stat(dst).st_mtime),
        )

        self.assertEqual(
            wsbapp.file_info(dst, base=os.path.join(root, 'deep')),
            ('subdir/file.txt', 'file', 3, os.stat(dst).st_mtime),
        )

        self.assertEqual(
            wsbapp.file_info(dst, base=os.path.join(root, 'deep', 'subdir')),
            ('file.txt', 'file', 3, os.stat(dst).st_mtime),
        )

        # invalid base
        with self.assertRaises(ValueError):
            wsbapp.file_info(dst, base=os.path.join(root, 'nonexist'))

        with self.assertRaises(ValueError):
            wsbapp.file_info(dst, base=os.path.join(root, 'deep', 'subdir', 'file'))

        with self.assertRaises(ValueError):
            wsbapp.file_info(dst, base=os.path.join(root, 'deep', 'subdir', 'file.txt'))

    @require_sep()
    def test_file_info_no_altsep(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'deep', 'subdir', r'file\name.txt')
        os.makedirs(os.path.dirname(dst))
        with open(dst, 'w') as fh:
            fh.write('123')

        self.assertEqual(
            wsbapp.file_info(dst),
            (r'file\name.txt', 'file', 3, os.stat(dst).st_mtime),
        )

        self.assertEqual(
            wsbapp.file_info(dst, base=os.path.join(root, 'deep')),
            (r'subdir/file\name.txt', 'file', 3, os.stat(dst).st_mtime),
        )

        with self.assertRaises(ValueError):
            wsbapp.file_info(dst, base='file')

    @require_junction()
    def test_file_info_junction(self):
        # dir
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'folder')
        dst = os.path.join(root, 'junction')
        os.makedirs(ref)
        util.fs.junction(ref, dst)
        with test_file_cleanup(dst):
            self.assertEqual(
                wsbapp.file_info(dst),
                ('junction', 'link', None, os.lstat(dst).st_mtime),
            )

        # file (invalid)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'file.txt')
        dst = os.path.join(root, 'junction')
        with open(ref, 'w') as fh:
            fh.write('123')
        util.fs.junction(ref, dst)
        with test_file_cleanup(dst):
            self.assertEqual(
                wsbapp.file_info(dst),
                ('junction', 'link', None, os.lstat(dst).st_mtime),
            )

        # nonexist
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        dst = os.path.join(root, 'junction')
        util.fs.junction(ref, dst)
        with test_file_cleanup(dst):
            self.assertEqual(
                wsbapp.file_info(dst),
                ('junction', 'link', None, os.lstat(dst).st_mtime),
            )

    @require_symlink()
    def test_file_info_symlink(self):
        # file
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'file.txt')
        dst = os.path.join(root, 'symlink')
        with open(ref, 'w') as fh:
            fh.write('123')
        os.symlink(ref, dst)
        self.assertEqual(
            wsbapp.file_info(dst),
            ('symlink', 'link', None, os.lstat(dst).st_mtime),
        )

        # dir
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'folder')
        dst = os.path.join(root, 'symlink')
        os.makedirs(ref)
        os.symlink(ref, dst)
        self.assertEqual(
            wsbapp.file_info(dst),
            ('symlink', 'link', None, os.lstat(dst).st_mtime),
        )

        # nonexist (file)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        dst = os.path.join(root, 'symlink')
        os.symlink(ref, dst, target_is_directory=False)
        self.assertEqual(
            wsbapp.file_info(dst),
            ('symlink', 'link', None, os.lstat(dst).st_mtime),
        )

        # nonexist (dir)
        root = tempfile.mkdtemp(dir=tmpdir)
        ref = os.path.join(root, 'nonexist')
        dst = os.path.join(root, 'symlink')
        os.symlink(ref, dst, target_is_directory=True)
        self.assertEqual(
            wsbapp.file_info(dst),
            ('symlink', 'link', None, os.lstat(dst).st_mtime),
        )

    def test_listdir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        dst = os.path.join(root, 'listdir')
        dst2 = os.path.join(root, 'listdir', 'folder')
        dst3 = os.path.join(root, 'listdir', 'folder', '.gitkeep')
        dst4 = os.path.join(root, 'listdir', 'file.txt')
        os.makedirs(dst)
        os.makedirs(dst2)
        with open(dst3, 'w'):
            pass
        with open(dst4, 'w') as fh:
            fh.write('123')
        self.assertEqual(set(wsbapp.listdir(dst)), {
            ('folder', 'dir', None, os.stat(dst2).st_mtime),
            ('file.txt', 'file', 3, os.stat(dst4).st_mtime),
        })
        self.assertEqual(set(wsbapp.listdir(dst, recursive=True)), {
            ('folder', 'dir', None, os.stat(dst2).st_mtime),
            ('folder/.gitkeep', 'file', 0, os.stat(dst3).st_mtime),
            ('file.txt', 'file', 3, os.stat(dst4).st_mtime),
        })

    def test_zip_file_info(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', DUMMY_ZIP_DT), '123456')
            zh.writestr(zipfile.ZipInfo('folder/', DUMMY_ZIP_DT2), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', DUMMY_ZIP_DT3), '123')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', DUMMY_ZIP_DT4), '1234')

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'file.txt'),
            ('file.txt', 'file', 6, DUMMY_TS),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'folder'),
            ('folder', 'dir', None, DUMMY_TS2),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'folder/'),
            ('folder', 'dir', None, DUMMY_TS2),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'folder/.gitkeep'),
            ('.gitkeep', 'file', 3, DUMMY_TS3),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, ''),
            ('', None, None, None),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'implicit_folder'),
            ('implicit_folder', None, None, None),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'implicit_folder/'),
            ('implicit_folder', None, None, None),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, '', check_implicit_dir=True),
            ('', 'dir', None, None),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'implicit_folder', check_implicit_dir=True),
            ('implicit_folder', 'dir', None, None),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'implicit_folder/', check_implicit_dir=True),
            ('implicit_folder', 'dir', None, None),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'implicit_folder/.gitkeep'),
            ('.gitkeep', 'file', 4, DUMMY_TS4),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'nonexist'),
            ('nonexist', None, None, None),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'nonexist/'),
            ('nonexist', None, None, None),
        )

        # take zipfile.ZipFile
        with zipfile.ZipFile(zfile, 'r') as zh:
            self.assertEqual(
                wsbapp.zip_file_info(zh, 'file.txt'),
                ('file.txt', 'file', 6, DUMMY_TS),
            )

        # with base
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('deep/subdir/file.txt', DUMMY_ZIP_DT), '123456')
            zh.writestr(zipfile.ZipInfo('deep/subdir/folder/', DUMMY_ZIP_DT2), '')
            zh.writestr(zipfile.ZipInfo('deep/subdir/folder/.gitkeep', DUMMY_ZIP_DT3), '123')

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base=''),
            ('deep/subdir/file.txt', 'file', 6, DUMMY_TS),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='/'),
            ('deep/subdir/file.txt', 'file', 6, DUMMY_TS),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='deep/'),
            ('subdir/file.txt', 'file', 6, DUMMY_TS),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='deep'),
            ('subdir/file.txt', 'file', 6, DUMMY_TS),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='deep/subdir/'),
            ('file.txt', 'file', 6, DUMMY_TS),
        )

        self.assertEqual(
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='deep/subdir'),
            ('file.txt', 'file', 6, DUMMY_TS),
        )

        # invalid base
        with self.assertRaises(ValueError):
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='nonexist')

        with self.assertRaises(ValueError):
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='nonexist/')

        with self.assertRaises(ValueError):
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='deep/subdir/file')

        with self.assertRaises(ValueError):
            wsbapp.zip_file_info(zfile, 'deep/subdir/file.txt', base='deep/subdir/file.txt')

    def test_zip_listdir(self):
        root = tempfile.mkdtemp(dir=tmpdir)
        zfile = os.path.join(root, 'zipfile.zip')
        with zipfile.ZipFile(zfile, 'w') as zh:
            zh.writestr(zipfile.ZipInfo('file.txt', DUMMY_ZIP_DT), '123456')
            zh.writestr(zipfile.ZipInfo('folder/', DUMMY_ZIP_DT2), '')
            zh.writestr(zipfile.ZipInfo('folder/.gitkeep', DUMMY_ZIP_DT3), '123')
            zh.writestr(zipfile.ZipInfo('implicit_folder/.gitkeep', DUMMY_ZIP_DT4), '1234')

        self.assertEqual(set(wsbapp.zip_listdir(zfile, '')), {
            ('folder', 'dir', None, DUMMY_TS2),
            ('implicit_folder', 'dir', None, None),
            ('file.txt', 'file', 6, DUMMY_TS),
        })

        self.assertEqual(set(wsbapp.zip_listdir(zfile, '/')), {
            ('folder', 'dir', None, DUMMY_TS2),
            ('implicit_folder', 'dir', None, None),
            ('file.txt', 'file', 6, DUMMY_TS),
        })

        self.assertEqual(set(wsbapp.zip_listdir(zfile, '', recursive=True)), {
            ('folder', 'dir', None, DUMMY_TS2),
            ('folder/.gitkeep', 'file', 3, DUMMY_TS3),
            ('implicit_folder', 'dir', None, None),
            ('implicit_folder/.gitkeep', 'file', 4, DUMMY_TS4),
            ('file.txt', 'file', 6, DUMMY_TS),
        })

        self.assertEqual(set(wsbapp.zip_listdir(zfile, 'folder')), {
            ('.gitkeep', 'file', 3, DUMMY_TS3)
        })

        self.assertEqual(set(wsbapp.zip_listdir(zfile, 'folder/')), {
            ('.gitkeep', 'file', 3, DUMMY_TS3)
        })

        self.assertEqual(set(wsbapp.zip_listdir(zfile, 'implicit_folder')), {
            ('.gitkeep', 'file', 4, DUMMY_TS4)
        })

        self.assertEqual(set(wsbapp.zip_listdir(zfile, 'implicit_folder/')), {
            ('.gitkeep', 'file', 4, DUMMY_TS4)
        })

        with self.assertRaises(wsbapp.ZipDirNotFoundError):
            set(wsbapp.zip_listdir(zfile, 'nonexist'))

        with self.assertRaises(wsbapp.ZipDirNotFoundError):
            set(wsbapp.zip_listdir(zfile, 'nonexist/'))

        with self.assertRaises(wsbapp.ZipDirNotFoundError):
            set(wsbapp.zip_listdir(zfile, 'file.txt'))

        # take zipfile.ZipFile
        with zipfile.ZipFile(zfile, 'r') as zh:
            self.assertEqual(set(wsbapp.zip_listdir(zh, '')), {
                ('folder', 'dir', None, DUMMY_TS2),
                ('implicit_folder', 'dir', None, None),
                ('file.txt', 'file', 6, DUMMY_TS),
            })


if __name__ == '__main__':
    unittest.main()
