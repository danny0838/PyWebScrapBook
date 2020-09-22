from unittest import mock
import unittest
import os
import io
from collections import OrderedDict
import webscrapbook

root_dir = os.path.abspath(os.path.dirname(__file__))

def setUpModule():
    # mock out WSB_USER_CONFIG
    global mocking
    mocking = mock.patch('webscrapbook.WSB_USER_CONFIG', os.path.join(root_dir, 'test_config', '.wsb'))
    mocking.start()

def tearDownModule():
    # stop mock
    mocking.stop()

class TestClassConfig(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.maxDiff = None

    def test_load(self):
        conf = webscrapbook.Config()
        conf.load(os.path.join(root_dir, 'test_config'))
        self.assertDictEqual(conf['app'], OrderedDict([
            ('name', 'mywsb'),
            ('theme', 'mytheme'),
            ('root', 'myroot'),
            ('base', 'mybase'),
            ('content_security_policy', 'strict'),
            ('allowed_x_for', 1),
            ('allowed_x_proto', 1),
            ('allowed_x_host', 0),
            ('allowed_x_port', 0),
            ('allowed_x_prefix', 0),
            ]))
        self.assertDictEqual(conf['server'], OrderedDict([
            ('port', 9999),
            ('host', 'localhost'),
            ('ssl_on', True),
            ('ssl_key', './wsb/wsb.key'),
            ('ssl_cert', './wsb/wsb.crt'),
            ('ssl_pw', ''),
            ('browse', True),
            ]))
        self.assertDictEqual(conf['browser'], OrderedDict([
            ('command', ''),
            ('index', ''),
            ('cache_prefix', 'wsb.'),
            ('cache_expire', 123456),
            ('use_jar', False),
            ]))
        self.assertDictEqual(conf['book'], OrderedDict([
            ('', OrderedDict([
                ('name', 'mybook'),
                ('top_dir', ''),
                ('data_dir', ''),
                ('tree_dir', '.wsb/tree'),
                ('index', '.wsb/tree/map.html'),
                ('no_tree', False),
                ])),
            ('book2', OrderedDict([
                ('name', 'mybook2'),
                ('no_tree', True),
                ])),
            ]))
        self.assertDictEqual(conf['auth'], OrderedDict([
            ('user1', OrderedDict([
                ('user', 'myuser1'),
                ('permission', 'all'),
                ])),
            ]))

    def test_load_repeated(self):
        conf = webscrapbook.Config()
        conf.load(os.path.join(root_dir, 'test_config'))

        # check if previous loaded config entries no more exist
        conf.load(os.path.join(root_dir, 'test_config_load_repeated'))
        self.assertDictEqual(conf['app'], OrderedDict([
            ('name', 'mywsb2'),
            ('theme', 'default'),
            ('root', '.'),
            ('base', ''),
            ('content_security_policy', 'strict'),
            ('allowed_x_for', 0),
            ('allowed_x_proto', 0),
            ('allowed_x_host', 0),
            ('allowed_x_port', 0),
            ('allowed_x_prefix', 0),
            ]))
        with self.assertRaises(KeyError):
            conf['book']['book2']
        with self.assertRaises(KeyError):
            conf['auth']

    @mock.patch('webscrapbook.WSB_LOCAL_CONFIG', 'localconfig.ini')
    @mock.patch('webscrapbook.WSB_DIR', '.wsbdir')
    @mock.patch('webscrapbook.WSB_USER_CONFIG', os.path.join(root_dir, 'test_config_load_constants', 'userconfig.ini'))
    def test_load_constants(self):
        # check if WSB_USER_CONFIG, WSB_DIR, and WSB_LOCAL_CONFIG are honored
        conf = webscrapbook.Config()
        conf.load(os.path.join(root_dir, 'test_config_load_constants'))
        self.assertEqual(conf['app']['name'], 'myuserwsb')
        self.assertEqual(conf['app']['theme'], 'mytheme')
        self.assertEqual(conf['server']['port'], 8888)
        self.assertEqual(conf['book']['']['name'], 'myuserbook')
        self.assertEqual(conf['book']['']['no_tree'], True)
        self.assertEqual(conf['book']['book1']['name'], 'mybook1')
        self.assertEqual(conf['book']['book2']['name'], 'mybook2')

    def test_getitem(self):
        # test lazy loading
        _cwd = os.getcwd()
        os.chdir(os.path.join(root_dir, 'test_config'))

        try:
            conf = webscrapbook.Config()
            self.assertEqual(conf['app']['name'], 'mywsb')
            self.assertEqual(conf['app']['allowed_x_for'], 1)
            self.assertEqual(conf['server']['ssl_on'], True)
            self.assertEqual(conf['server']['browse'], True)
            self.assertEqual(conf['book']['']['name'], 'mybook')
            self.assertEqual(conf['book']['book2']['name'], 'mybook2')
        finally:
            os.chdir(_cwd)

    def test_iter(self):
        # test lazy loading
        _cwd = os.getcwd()
        os.chdir(os.path.join(root_dir, 'test_config'))

        try:
            conf = webscrapbook.Config()
            self.assertEqual(list(iter(conf)), ['app', 'server', 'browser', 'book', 'auth'])
        finally:
            os.chdir(_cwd)

    def test_getname(self):
        # test lazy loading
        _cwd = os.getcwd()
        os.chdir(os.path.join(root_dir, 'test_config'))

        try:
            conf = webscrapbook.Config()
            self.assertEqual(conf.getname('app.name'), 'mywsb')
            self.assertEqual(conf.getname('app.allowed_x_for'), '1')
            self.assertEqual(conf.getname('server.ssl_on'), 'true')
            self.assertEqual(conf.getname('server.browse'), 'yes')
            self.assertEqual(conf.getname('book..name'), 'mybook')
            self.assertEqual(conf.getname('book.book2.name'), 'mybook2')
        finally:
            os.chdir(_cwd)

    def test_dump(self):
        # test lazy loading
        _cwd = os.getcwd()
        os.chdir(os.path.join(root_dir, 'test_config'))

        try:
            conf = webscrapbook.Config()
            with io.StringIO() as fh:
                conf.dump(fh)
                output = fh.getvalue()
            self.assertEqual(output, """[app]
name = mywsb
theme = mytheme
root = myroot
base = mybase
content_security_policy = strict
allowed_x_for = 1
allowed_x_proto = 1
allowed_x_host = 0
allowed_x_port = 0
allowed_x_prefix = 0

[server]
port = 9999
host = localhost
ssl_on = true
ssl_key = ./wsb/wsb.key
ssl_cert = ./wsb/wsb.crt
ssl_pw = 
browse = yes

[browser]
command = 
index = 
cache_prefix = wsb.
cache_expire = 123456
use_jar = no

[book ""]
name = mybook
top_dir = 
data_dir = 
tree_dir = .wsb/tree
index = .wsb/tree/map.html
no_tree = false

[book "book2"]
name = mybook2
no_tree = on

[auth "user1"]
user = myuser1
permission = all

""")
        finally:
            os.chdir(_cwd)

    def test_dump_object(self):
        # test lazy loading
        _cwd = os.getcwd()
        os.chdir(os.path.join(root_dir, 'test_config'))

        try:
            conf = webscrapbook.Config()
            self.assertDictEqual(conf.dump_object(), OrderedDict([
                ('app', OrderedDict([
                    ('name', 'mywsb'),
                    ('theme', 'mytheme'),
                    ('root', 'myroot'),
                    ('base', 'mybase'),
                    ('content_security_policy', 'strict'),
                    ('allowed_x_for', 1),
                    ('allowed_x_proto', 1),
                    ('allowed_x_host', 0),
                    ('allowed_x_port', 0),
                    ('allowed_x_prefix', 0),
                    ])),
                ('server', OrderedDict([
                    ('port', 9999),
                    ('host', 'localhost'),
                    ('ssl_on', True),
                    ('ssl_key', './wsb/wsb.key'),
                    ('ssl_cert', './wsb/wsb.crt'),
                    ('ssl_pw', ''),
                    ('browse', True),
                    ])),
                ('browser', OrderedDict([
                    ('command', ''),
                    ('index', ''),
                    ('cache_prefix', 'wsb.'),
                    ('cache_expire', 123456),
                    ('use_jar', False),
                    ])),
                ('book', OrderedDict([
                    ('', OrderedDict([
                        ('name', 'mybook'),
                        ('top_dir', ''),
                        ('data_dir', ''),
                        ('tree_dir', '.wsb/tree'),
                        ('index', '.wsb/tree/map.html'),
                        ('no_tree', False),
                        ])),
                    ('book2', OrderedDict([
                        ('name', 'mybook2'),
                        ('no_tree', True),
                        ])),
                    ])),
                ('auth', OrderedDict([
                    ('user1', OrderedDict([
                        ('user', 'myuser1'),
                        ('permission', 'all'),
                        ])),
                    ])),
                ]))
        finally:
            os.chdir(_cwd)

if __name__ == '__main__':
    unittest.main()
