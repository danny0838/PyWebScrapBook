from unittest import mock
import unittest
import sys
import os
import io
import zipfile
from flask import current_app
import webscrapbook
from webscrapbook import WSB_DIR, WSB_LOCAL_CONFIG
from webscrapbook import app as wsbapp

root_dir = os.path.abspath(os.path.dirname(__file__))
server_root = os.path.join(root_dir, 'test_app_helpers')

mocking = None

def setUpModule():
    # mock out WSB_USER_CONFIG
    global mocking
    mocking = mock.patch('webscrapbook.WSB_USER_CONFIG', server_root)
    mocking.start()

def tearDownModule():
    # stop mock
    mocking.stop()

class TestFunctions(unittest.TestCase):
    def test_is_local_access(self):
        root = os.path.join(root_dir, 'test_app_helpers', 'general')
        app = wsbapp.make_app(root)

        # host is localhost
        with app.test_request_context('/',
                base_url='http://127.0.0.1',
                environ_base={'REMOTE_ADDR': '192.168.0.100'}):
            self.assertTrue(wsbapp.is_local_access())

        # host (with port) is localhost
        with app.test_request_context('/',
                base_url='http://127.0.0.1:8000',
                environ_base={'REMOTE_ADDR': '192.168.0.100'}):
            self.assertTrue(wsbapp.is_local_access())

        # remote is localhost
        with app.test_request_context('/',
                base_url='http://192.168.0.1',
                environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            self.assertTrue(wsbapp.is_local_access())

        # host = remote
        with app.test_request_context('/',
                base_url='http://example.com',
                environ_base={'REMOTE_ADDR': 'example.com'}):
            self.assertTrue(wsbapp.is_local_access())

        # host (with port) = remote
        with app.test_request_context('/',
                base_url='http://example.com:8000',
                environ_base={'REMOTE_ADDR': 'example.com'}):
            self.assertTrue(wsbapp.is_local_access())

        # otherwise non-local
        with app.test_request_context('/',
                base_url='http://example.com',
                environ_base={'REMOTE_ADDR': '192.168.0.100'}):
            self.assertFalse(wsbapp.is_local_access())

    def test_make_app1(self):
        # pass root
        root = os.path.join(root_dir, 'test_app_helpers', 'make_app1')

        app = wsbapp.make_app(root)
        with app.app_context():
            self.assertEqual(current_app.config['WEBSCRAPBOOK_RUNTIME']['config']['app']['name'], 'mywsb1')

    def test_make_app2(self):
        # pass root, config
        root = os.path.join(root_dir, 'test_app_helpers', 'make_app1')
        config_dir = os.path.join(root_dir, 'test_app_helpers', 'make_app2')
        config = webscrapbook.Config()
        config.load(config_dir)

        app = wsbapp.make_app(root, config)
        with app.app_context():
            self.assertEqual(current_app.config['WEBSCRAPBOOK_RUNTIME']['config']['app']['name'], 'mywsb2')

if __name__ == '__main__':
    unittest.main()
