import os
import shutil
import tempfile
import unittest
from unittest import mock

from webscrapbook import WSB_CONFIG, WSB_DIR, server

from . import ROOT_DIR, TEMP_DIR


def setUpModule():
    """Set up a temp directory for testing."""
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='server-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(os.path.join(_tmpdir.name, 'd'))
    shutil.copytree(os.path.join(ROOT_DIR, 'test_server'), tmpdir)

    global server_root, server_config
    server_root = tmpdir
    server_config = os.path.join(server_root, WSB_DIR, WSB_CONFIG)

    # mock out user config
    global mockings
    mockings = [
        mock.patch('webscrapbook.WSB_USER_DIR', os.path.join(tmpdir, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_CONFIG', tmpdir),
    ]
    for mocking in mockings:
        mocking.start()


def tearDownModule():
    """Cleanup the temp directory."""
    _tmpdir.cleanup()

    # stop mock
    for mocking in mockings:
        mocking.stop()


class TestConfigServer(unittest.TestCase):
    @mock.patch('webscrapbook.server.make_server')
    def test_root(self, mock_make_server):
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
browse = false
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[2][1][1], f'Document Root: {server_root}')

    @mock.patch('webscrapbook.server.make_server')
    def test_host_port1(self, mock_make_server):
        # IPv4
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 80
browse = false
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.call_args[1]['host'], '127.0.0.1')
        self.assertEqual(mock_make_server.call_args[1]['port'], 80)
        self.assertEqual(mock_make_server.mock_calls[3][1][1], 'Listening on http://127.0.0.1:80')

    @mock.patch('webscrapbook.server.make_server')
    def test_host_port2(self, mock_make_server):
        # IPv6 => with []
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = ::1
port = 8000
browse = false
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.call_args[1]['host'], '::1')
        self.assertEqual(mock_make_server.call_args[1]['port'], 8000)
        self.assertEqual(mock_make_server.mock_calls[3][1][1], 'Listening on http://[::1]:8000')

    @mock.patch('webscrapbook.server.make_server')
    def test_host_port3(self, mock_make_server):
        # domain_name (the server will actually bind to the resolved IP.)
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = localhost
port = 7357
browse = false
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.call_args[1]['host'], 'localhost')
        self.assertEqual(mock_make_server.call_args[1]['port'], 7357)
        self.assertEqual(mock_make_server.mock_calls[3][1][1], 'Listening on http://localhost:7357')

    @mock.patch('webscrapbook.server.make_server')
    def test_ssl1(self, mock_make_server):
        # SSL off
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = false
ssl_key = .wsb/test.key
ssl_cert = .wsb/test.pem
browse = false
""")

        server.serve(server_root)
        self.assertIs(mock_make_server.call_args[1]['ssl_context'], None)

    @mock.patch('webscrapbook.server.make_server')
    def test_ssl2(self, mock_make_server):
        # SSL with an adhoc key
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = true
ssl_key =
ssl_cert =
browse = false
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.call_args[1]['ssl_context'], 'adhoc')

    @mock.patch('webscrapbook.server.make_server')
    def test_ssl3(self, mock_make_server):
        # SSL with missing key => adhoc
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = true
ssl_key =
ssl_cert = .wsb/test.pem
browse = false
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.call_args[1]['ssl_context'], 'adhoc')

    @mock.patch('webscrapbook.server.make_server')
    def test_ssl4(self, mock_make_server):
        # SSL with missing cert => adhoc
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = true
ssl_key = .wsb/test.key
ssl_cert =
browse = false
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.call_args[1]['ssl_context'], 'adhoc')

    @mock.patch('webscrapbook.server.make_server')
    def test_ssl5(self, mock_make_server):
        # SSL with key and cert
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = true
ssl_key = .wsb/test.key
ssl_cert = .wsb/test.pem
browse = false
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.call_args[1]['ssl_context'], (
            os.path.join(server_root, WSB_DIR, 'test.pem'),
            os.path.join(server_root, WSB_DIR, 'test.key'),
        ))


class TestConfigBrowser(unittest.TestCase):
    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_command1(self, mock_make_server, mock_browser):
        # server.browse = false
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 80
browse = false

[browser]
command =
""")

        server.serve(server_root)
        mock_browser.assert_not_called()

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_command2(self, mock_make_server, mock_browser):
        # server.browse = true, browser.command not set
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 80
browse = true

[browser]
command =
""")

        server.serve(server_root)
        mock_browser.assert_called_once_with(None)

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_command3(self, mock_make_server, mock_browser):
        # server.browse = true, browser.command set
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write(r"""[server]
host = 127.0.0.1
port = 80
browse = true

[browser]
command = "C:\Program Files\Mozilla Firefox\firefox.exe" %s &
""")

        server.serve(server_root)
        mock_browser.assert_called_once_with(r'"C:\Program Files\Mozilla Firefox\firefox.exe" %s &')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_scheme1(self, mock_make_server, mock_browser):
        # http
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = false
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://127.0.0.1:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_scheme2(self, mock_make_server, mock_browser):
        # https
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = true
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at https://127.0.0.1:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_host1(self, mock_make_server, mock_browser):
        # IPv4
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://127.0.0.1:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_host2(self, mock_make_server, mock_browser):
        # IPv6 => with []
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = ::1
port = 7357
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://[::1]:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_host3(self, mock_make_server, mock_browser):
        # domain name
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = localhost
port = 7357
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://localhost:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_host4(self, mock_make_server, mock_browser):
        # null host (0.0.0.0) => localhost
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 0.0.0.0
port = 7357
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://localhost:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_host5(self, mock_make_server, mock_browser):
        # null host (::) => localhost
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = ::
port = 7357
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://localhost:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_port1(self, mock_make_server, mock_browser):
        # normal port
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = false
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://127.0.0.1:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_port2(self, mock_make_server, mock_browser):
        # 80 for http
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 80
ssl_on = false
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://127.0.0.1 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_port3(self, mock_make_server, mock_browser):
        # 443 for https
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 443
ssl_on = true
browse = true

[app]
base =

[browser]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at https://127.0.0.1 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_path1(self, mock_make_server, mock_browser):
        # app.index not set
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = false
browse = true

[app]
index =
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://127.0.0.1:7357 ...')

    @mock.patch('webbrowser.get')
    @mock.patch('webscrapbook.server.make_server')
    def test_url_path2(self, mock_make_server, mock_browser):
        # app.index set
        with open(server_config, 'w', encoding='UTF-8') as fh:
            fh.write("""[server]
host = 127.0.0.1
port = 7357
ssl_on = false
browse = true

[app]
index = index.html
""")

        server.serve(server_root)
        self.assertEqual(mock_make_server.mock_calls[5][1][1], 'Launching browser at http://127.0.0.1:7357/index.html ...')


if __name__ == '__main__':
    unittest.main()
