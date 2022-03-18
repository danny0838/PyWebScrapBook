from unittest import mock
import unittest
import os
import shutil
import re
import time
from webscrapbook import WSB_DIR, Config
from webscrapbook import util
from webscrapbook.scrapbook import host as wsb_host
from webscrapbook.scrapbook.host import Host

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_scrapbook_host')

def setUpModule():
    # mock out user config
    global mockings
    mockings = [
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(test_root, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_DIR', os.path.join(test_root, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_CONFIG', test_root),
        ]
    for mocking in mockings:
        mocking.start()

def tearDownModule():
    # stop mock
    for mocking in mockings:
        mocking.stop()

class TestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192
        cls.test_root = os.path.join(test_root, 'general')
        cls.test_wsbdir = os.path.join(cls.test_root, WSB_DIR)
        cls.test_config = os.path.join(cls.test_root, WSB_DIR, 'config.ini')

    def setUp(self):
        """Set up a general temp test folder
        """
        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

        os.makedirs(self.test_wsbdir)

    def tearDown(self):
        """Remove general temp test folder
        """
        try:
            shutil.rmtree(self.test_root)
        except NotADirectoryError:
            os.remove(self.test_root)
        except FileNotFoundError:
            pass

class TestHost(TestBase):
    @mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(test_root, 'general', 'wsb'))
    def test_init01(self):
        """Check basic"""
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
name = myhost
theme = custom
root = public
backup_dir = mybackups

[book ""]
name = mybook

[book "id2"]
name = mybook2
""")
        host = Host(self.test_root)

        self.assertEqual(host.root, self.test_root)
        self.assertEqual(host.name, 'myhost')

        self.assertEqual(host.chroot, os.path.join(self.test_root, 'public'))
        self.assertEqual(host.backup_dir, os.path.join(self.test_root, 'mybackups'))
        self.assertEqual([os.path.normcase(f) for f in host.themes], [
            os.path.normcase(os.path.join(self.test_root, WSB_DIR, 'themes', 'custom')),
            os.path.normcase(os.path.join(self.test_root, 'wsb', 'themes', 'custom')),
            os.path.normcase(os.path.abspath(os.path.join(wsb_host.__file__, '..', '..', 'themes', 'custom'))),
            ])
        self.assertEqual([os.path.normcase(f) for f in host.statics], [
            os.path.normcase(os.path.join(self.test_root, WSB_DIR, 'themes', 'custom', 'static')),
            os.path.normcase(os.path.join(self.test_root, 'wsb', 'themes', 'custom', 'static')),
            os.path.normcase(os.path.abspath(os.path.join(wsb_host.__file__, '..', '..', 'themes', 'custom', 'static'))),
            ])
        self.assertEqual([os.path.normcase(f) for f in host.templates], [
            os.path.normcase(os.path.join(self.test_root, WSB_DIR, 'themes', 'custom', 'templates')),
            os.path.normcase(os.path.join(self.test_root, 'wsb', 'themes', 'custom', 'templates')),
            os.path.normcase(os.path.abspath(os.path.join(wsb_host.__file__, '..', '..', 'themes', 'custom', 'templates'))),
            ])
        self.assertEqual(host.locks, os.path.join(self.test_root, WSB_DIR, 'locks'))
        self.assertEqual({i: host.books[i].name for i in host.books}, {
            '': 'mybook',
            'id2': 'mybook2',
            })

    @mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(test_root, 'general', 'wsb'))
    def test_init02(self):
        """Check config param"""
        other_root = os.path.join(self.test_root, 'rootdir')
        os.makedirs(other_root)
        with open(self.test_config, 'w', encoding='UTF-8') as f:
            f.write("""[app]
name = myhost
theme = custom
root = public
backup_dir = mybackups

[book "id2"]
name = mybook2
""")
        conf = Config()
        conf.load(self.test_root)

        host = Host(other_root, config=conf)

        self.assertEqual(host.root, other_root)
        self.assertEqual(host.name, 'myhost')

        self.assertEqual(host.chroot, os.path.join(other_root, 'public'))
        self.assertEqual(host.backup_dir, os.path.join(other_root, 'mybackups'))
        self.assertEqual([os.path.normcase(f) for f in host.themes], [
            os.path.normcase(os.path.join(other_root, WSB_DIR, 'themes', 'custom')),
            os.path.normcase(os.path.join(self.test_root, 'wsb', 'themes', 'custom')),
            os.path.normcase(os.path.abspath(os.path.join(wsb_host.__file__, '..', '..', 'themes', 'custom'))),
            ])
        self.assertEqual([os.path.normcase(f) for f in host.statics], [
            os.path.normcase(os.path.join(other_root, WSB_DIR, 'themes', 'custom', 'static')),
            os.path.normcase(os.path.join(self.test_root, 'wsb', 'themes', 'custom', 'static')),
            os.path.normcase(os.path.abspath(os.path.join(wsb_host.__file__, '..', '..', 'themes', 'custom', 'static'))),
            ])
        self.assertEqual([os.path.normcase(f) for f in host.templates], [
            os.path.normcase(os.path.join(other_root, WSB_DIR, 'themes', 'custom', 'templates')),
            os.path.normcase(os.path.join(self.test_root, 'wsb', 'themes', 'custom', 'templates')),
            os.path.normcase(os.path.abspath(os.path.join(wsb_host.__file__, '..', '..', 'themes', 'custom', 'templates'))),
            ])
        self.assertEqual(host.locks, os.path.join(other_root, WSB_DIR, 'locks'))
        self.assertEqual({i: host.books[i].name for i in host.books}, {
            '': 'scrapbook',
            'id2': 'mybook2',
            })

    @mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(test_root, 'general', 'wsb'))
    def test_init03(self):
        """Validate theme name to avoid a potential bad path."""
        for theme, theme_fixed in [
                ('', '_'),
                ('.', '_'),
                ('..', '_'),
                ('foo/bar', 'foo_bar'),
                ('foo\\bar', 'foo_bar'),
                ]:
            with self.subTest(theme=theme):
                with open(self.test_config, 'w', encoding='UTF-8') as f:
                    f.write(f"[app]\ntheme = {theme}")
                host = Host(self.test_root)
                self.assertEqual([os.path.normcase(f) for f in host.themes], [
                    os.path.normcase(os.path.join(self.test_root, WSB_DIR, 'themes', theme_fixed)),
                    os.path.normcase(os.path.join(self.test_root, 'wsb', 'themes', theme_fixed)),
                    os.path.normcase(os.path.abspath(os.path.join(wsb_host.__file__, '..', '..', 'themes', theme_fixed))),
                    ])

    def test_get_static_file01(self):
        """Lookup static file from built-in themes"""
        host = Host(self.test_root)
        self.assertEqual(os.path.normcase(host.get_static_file('index.css')),
            os.path.normcase(os.path.abspath(os.path.join(wsb_host.__file__, '..', '..', 'themes', 'default', 'static', 'index.css')))
            )

    @mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(test_root, 'general', 'wsb'))
    def test_get_static_file02(self):
        """Lookup static file from user themes"""
        other_static = os.path.join(self.test_root, 'wsb', 'themes', 'default', 'static', 'test.txt')
        os.makedirs(os.path.dirname(other_static))
        with open(other_static, 'w') as fh:
            pass

        host = Host(self.test_root)
        self.assertEqual(host.get_static_file('test.txt'), other_static)

    def test_get_static_file03(self):
        """Lookup static file from local themes"""
        other_static = os.path.join(self.test_root, WSB_DIR, 'themes', 'default', 'static', 'test.txt')
        os.makedirs(os.path.dirname(other_static))
        with open(other_static, 'w') as fh:
            pass

        host = Host(self.test_root)
        self.assertEqual(host.get_static_file('test.txt'), other_static)

    @mock.patch('webscrapbook.scrapbook.host.FileLock')
    def test_get_lock01(self, mock_filelock):
        host = Host(self.test_root)
        host.get_lock('test')
        mock_filelock.assert_called_once_with(host, 'test')

    @mock.patch('webscrapbook.scrapbook.host.FileLock')
    def test_get_lock02(self, mock_filelock):
        """With parameters"""
        host = Host(self.test_root)
        host.get_lock('test',
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True)
        mock_filelock.assert_called_once_with(host, 'test',
            timeout=10, stale=120, poll_interval=0.3, assume_acquired=True)

    def test_backup01(self):
        """A common case."""
        test_backup_dir = os.path.join(self.test_root, 'backup')
        os.makedirs(test_backup_dir)
        test_file = os.path.join(self.test_root, 'tree', 'meta.js')
        os.makedirs(os.path.dirname(test_file))
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('abc')

        host = Host(self.test_root)
        host.backup(test_file, test_backup_dir)

        with open(os.path.join(test_backup_dir, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')

    def test_backup02(self):
        """A common directory case."""
        test_backup_dir = os.path.join(self.test_root, 'backup')
        os.makedirs(test_backup_dir)
        test_dir = os.path.join(self.test_root, 'tree')
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write('abc')
        with open(os.path.join(test_dir, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write('def')

        host = Host(self.test_root)
        host.backup(test_dir, test_backup_dir)

        with open(os.path.join(test_backup_dir, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')
        with open(os.path.join(test_backup_dir, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'def')

    def test_backup03(self):
        """Pass if file not exist."""
        test_backup_dir = os.path.join(self.test_root, 'backup')
        os.makedirs(test_backup_dir)
        test_file = os.path.join(self.test_wsbdir, 'icon', 'nonexist.txt')

        host = Host(self.test_root)
        host.backup(test_file, test_backup_dir)

        self.assertFalse(os.path.lexists(os.path.join(test_backup_dir, WSB_DIR, 'icon', 'nonexist.txt')))

    def test_backup04(self):
        """Pass if file outside the host root."""
        test_backup_dir = os.path.join(self.test_root, 'backup')
        os.makedirs(test_backup_dir)

        host = Host(self.test_root)
        host.backup(__file__, test_backup_dir)

        self.assertListEqual(os.listdir(test_backup_dir), [])

    def test_backup05(self):
        """Test base param."""
        test_backup_dir = os.path.join(self.test_root, 'backup')
        os.makedirs(test_backup_dir)
        test_base_dir = os.path.join(test_root, 'backup')

        host = Host(self.test_root)
        host.backup(os.path.join(test_base_dir, 'test.txt'), test_backup_dir, base=test_base_dir)

        with open(os.path.join(test_backup_dir, 'test.txt'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'ABC123')

    def test_backup06(self):
        """Test move param."""
        test_backup_dir = os.path.join(self.test_root, 'backup')
        os.makedirs(test_backup_dir)
        test_dir = os.path.join(self.test_root, 'tree')
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write('abc')
        with open(os.path.join(test_dir, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write('def')

        host = Host(self.test_root)
        host.backup(test_dir, test_backup_dir, move=True)

        self.assertFalse(os.path.lexists(test_dir))
        with open(os.path.join(test_backup_dir, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')
        with open(os.path.join(test_backup_dir, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'def')

    def test_backup07(self):
        """A common case."""
        test_file = os.path.join(self.test_root, 'tree', 'meta.js')
        os.makedirs(os.path.dirname(test_file))
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('abc')

        host = Host(self.test_root)
        host.backup(test_file)

        backup_dirname = os.listdir(os.path.join(self.test_wsbdir, 'backup'))[0]
        self.assertRegex(backup_dirname, r'^\d{17}$')
        with open(os.path.join(self.test_wsbdir, 'backup', backup_dirname, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')

    def test_unbackup01(self):
        """A common case."""
        test_backup_dir = os.path.join(self.test_root, 'backup')
        os.makedirs(test_backup_dir)

        host = Host(self.test_root)
        host.unbackup(test_backup_dir)

        self.assertFalse(os.path.lexists(test_backup_dir))

    def test_unbackup02(self):
        """Pass if backup dir not exist."""
        test_backup_dir = os.path.join(self.test_root, 'backup')

        host = Host(self.test_root)
        host.unbackup(test_backup_dir)

        self.assertFalse(os.path.lexists(test_backup_dir))

    def test_init_backup01(self):
        """Test ts param."""
        host = Host(self.test_root)

        host.init_backup(True)
        self.assertRegex(
            host._backup_dir,
            r'^' + re.escape(os.path.join(self.test_root, WSB_DIR, 'backup', '')) + r'\d{17}$',
            )

        ts = util.datetime_to_id()
        host.init_backup(ts)
        self.assertEqual(
            host._backup_dir,
            os.path.join(self.test_root, WSB_DIR, 'backup', ts),
            )

        host.init_backup(False)
        self.assertIsNone(host._backup_dir)

    def test_init_backup02(self):
        """Test note param."""
        host = Host(self.test_root)

        host.init_backup(True, 'foo~bar')
        self.assertRegex(
            host._backup_dir,
            r'^' + re.escape(os.path.join(self.test_root, WSB_DIR, 'backup', '')) + r'\d{17}-foo-bar',
            )

        ts = util.datetime_to_id()
        host.init_backup(ts, note='foo:bar:中文?')
        self.assertEqual(
            host._backup_dir,
            os.path.join(self.test_root, WSB_DIR, 'backup', ts + '-foo_bar_中文_'),
            )

    def test_auto_backup01(self):
        """A common case."""
        test_file = os.path.join(self.test_root, 'tree', 'meta.js')
        os.makedirs(os.path.dirname(test_file))
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('abc')

        host = Host(self.test_root)
        host.init_backup()
        host.backup(test_file)

        with open(os.path.join(host._backup_dir, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')

    def test_auto_backup01(self):
        """A common case."""
        test_file = os.path.join(self.test_root, 'tree', 'meta.js')
        os.makedirs(os.path.dirname(test_file))
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('abc')

        host = Host(self.test_root)
        host.init_backup()
        host.auto_backup(test_file)

        with open(os.path.join(host._backup_dir, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')

    def test_backup02(self):
        """A common directory case."""
        test_dir = os.path.join(self.test_root, 'tree')
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, 'meta.js'), 'w', encoding='UTF-8') as fh:
            fh.write('abc')
        with open(os.path.join(test_dir, 'toc.js'), 'w', encoding='UTF-8') as fh:
            fh.write('def')

        host = Host(self.test_root)
        host.init_backup()
        host.auto_backup(test_dir)

        with open(os.path.join(host._backup_dir, 'tree', 'meta.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'abc')
        with open(os.path.join(host._backup_dir, 'tree', 'toc.js'), encoding='UTF-8') as fh:
            self.assertEqual(fh.read(), 'def')

    def test_backup03(self):
        """Pass if _backup_dir not set."""
        test_file = os.path.join(self.test_wsbdir, 'icon', 'test.txt')
        os.makedirs(os.path.dirname(test_file))
        with open(test_file, 'w', encoding='UTF-8') as fh:
            fh.write('abc')
        test_stat = os.stat(test_file)

        host = Host(self.test_root)
        host.auto_backup(test_file)

        self.assertListEqual(os.listdir(self.test_wsbdir), ['icon'])

class TestFileLock(TestBase):
    def test_init01(self):
        """Normal"""
        lock_file = os.path.join(self.test_root, WSB_DIR, 'locks', '098f6bcd4621d373cade4e832627b4f6.lock')

        host = Host(self.test_root)
        lock = wsb_host.FileLock(host, 'test')

        self.assertEqual(lock.host, host)
        self.assertEqual(lock.name, 'test')
        self.assertEqual(lock.timeout, 5)
        self.assertEqual(lock.stale, 60)
        self.assertEqual(lock.file, lock_file)
        self.assertIsInstance(lock.id, str)
        self.assertEqual(lock._lock, False)

    def test_init02(self):
        """Parameters."""
        lock_file = os.path.join(self.test_root, WSB_DIR, 'locks', '098f6bcd4621d373cade4e832627b4f6.lock')

        host = Host(self.test_root)
        lock = wsb_host.FileLock(host, 'test',
            timeout=2, stale=120)
        self.assertEqual(lock.host, host)
        self.assertEqual(lock.name, 'test')
        self.assertEqual(lock.timeout, 2)
        self.assertEqual(lock.stale, 120)
        self.assertEqual(lock.file, lock_file)
        self.assertIsInstance(lock.id, str)
        self.assertEqual(lock._lock, False)

    def test_persist01(self):
        """Normal case."""
        lock_file = os.path.join(self.test_root, WSB_DIR, 'locks', '098f6bcd4621d373cade4e832627b4f6.lock')
        os.makedirs(os.path.dirname(lock_file))
        with open(lock_file, 'w', encoding='UTF-8') as fh:
            fh.write('oldid')

        host = Host(self.test_root)
        lock = wsb_host.FileLock(host, 'test', persist='oldid')

        self.assertEqual(lock.id, 'oldid')
        self.assertEqual(lock._lock, True)

    def test_persist02(self):
        """Wrong ID."""
        lock_file = os.path.join(self.test_root, WSB_DIR, 'locks', '098f6bcd4621d373cade4e832627b4f6.lock')
        os.makedirs(os.path.dirname(lock_file))
        with open(lock_file, 'w', encoding='UTF-8') as fh:
            fh.write('oldid')

        host = Host(self.test_root)

        with self.assertRaises(wsb_host.LockPersistUnmatchError):
            wsb_host.FileLock(host, 'test', persist='dummy')

    def test_persist03(self):
        """Lock file missing (or inaccessible)."""
        lock_file = os.path.join(self.test_root, WSB_DIR, 'locks', '098f6bcd4621d373cade4e832627b4f6.lock')

        host = Host(self.test_root)

        with self.assertRaises(wsb_host.LockPersistOSError):
            wsb_host.FileLock(host, 'test', persist='dummy')

    def test_acquire01(self):
        """Normal case"""
        lock = Host(self.test_root).get_lock('test')

        lock.acquire()

        with open(lock.file) as fh:
            self.assertTrue(fh.read(), lock.id)
        self.assertTrue(lock.locked)

    def test_acquire02(self):
        """Already exists"""
        lock = Host(self.test_root).get_lock('test', timeout=0)

        os.makedirs(os.path.dirname(lock.file))
        with open(lock.file, 'w') as fh:
            pass

        with self.assertRaises(wsb_host.LockTimeoutError):
            lock.acquire()

    def test_acquire03(self):
        """Already exists, timeout as acquire param"""
        lock = Host(self.test_root).get_lock('test')

        os.makedirs(os.path.dirname(lock.file))
        with open(lock.file, 'w') as fh:
            pass

        with self.assertRaises(wsb_host.LockTimeoutError):
            lock.acquire(timeout=0)

    def test_acquire04(self):
        """Stale lock should be regenerated"""
        lock = Host(self.test_root).get_lock('test', timeout=1, stale=0)
        os.makedirs(os.path.dirname(lock.file))
        with open(lock.file, 'w') as fh:
            fh.write('oldid')

        lock.acquire()

        with open(lock.file) as fh:
            self.assertTrue(fh.read(), lock.id)
        self.assertNotEqual(lock.id, 'oldid')
        self.assertTrue(lock.locked)

    def test_acquire05(self):
        """Unable to generate upper directory"""
        lock = Host(self.test_root).get_lock('test')

        with open(os.path.join(self.test_root, WSB_DIR, 'locks'), 'wb') as fh:
            pass

        with self.assertRaises(wsb_host.LockGenerateError):
            lock.acquire()

    def test_acquire06(self):
        """Occupied by a directory"""
        lock = Host(self.test_root).get_lock('test')

        os.makedirs(lock.file)

        with self.assertRaises(wsb_host.LockGenerateError):
            lock.acquire()

    def test_acquire_with(self):
        """Lock should be released after an with statement."""
        lock = Host(self.test_root).get_lock('test')

        with lock.acquire() as lh:
            self.assertTrue(os.path.isfile(lock.file))
            self.assertTrue(lock.locked)
            self.assertEqual(lh, lock)

        self.assertFalse(os.path.exists(lock.file))
        self.assertFalse(lock.locked)

    def test_extend01(self):
        """Nnormal case"""
        lock = Host(self.test_root).get_lock('test')

        lock.acquire()
        prev_time = os.stat(lock.file).st_mtime
        time.sleep(0.05)
        lock.extend()
        cur_time = os.stat(lock.file).st_mtime

        self.assertGreater(cur_time, prev_time)
        self.assertTrue(lock.locked)

    def test_extend02(self):
        """Not acquired"""
        lock = Host(self.test_root).get_lock('test')

        with self.assertRaises(wsb_host.LockExtendNotAcquiredError):
            lock.extend()

    def test_extend03(self):
        """File not exist"""
        lock = Host(self.test_root).get_lock('test')

        lock.acquire()
        os.remove(lock.file)

        with self.assertRaises(wsb_host.LockExtendNotFoundError):
            lock.extend()

    def test_release01(self):
        """Nnormal case"""
        lock = Host(self.test_root).get_lock('test')

        lock.acquire()
        lock.release()

        self.assertFalse(os.path.lexists(lock.file))
        self.assertFalse(lock.locked)

    def test_release02(self):
        """Not acquired"""
        lock = Host(self.test_root).get_lock('test')

        with self.assertRaises(wsb_host.LockReleaseNotAcquiredError):
            lock.release()

    def test_release03(self):
        """File not exist"""
        lock = Host(self.test_root).get_lock('test')

        lock.acquire()
        os.remove(lock.file)

        with self.assertRaises(wsb_host.LockReleaseNotFoundError):
            lock.release()

    def test_keep01(self):
        """Lock should be auto-extended until released."""
        lock_file = os.path.join(self.test_root, WSB_DIR, 'locks', '098f6bcd4621d373cade4e832627b4f6.lock')
        lock = Host(self.test_root).get_lock('test', stale=0.01)

        lock.acquire()
        try:
            lock.keep()
            mtime = os.stat(lock_file).st_mtime

            # poll up to 0.5 seconds in case thread delay due to busyness
            start = time.time()
            while True:
                time.sleep(0.005)
                try:
                    self.assertGreater(os.stat(lock_file).st_mtime, mtime)
                except AssertionError as exc:
                    if time.time() - start > 0.5: raise exc
                else:
                    break
        finally:
            lock.release()

    def test_keep02(self):
        """Lock should be auto-extended until released."""
        lock_file = os.path.join(self.test_root, WSB_DIR, 'locks', '098f6bcd4621d373cade4e832627b4f6.lock')
        lock = Host(self.test_root).get_lock('test', stale=0.01)

        with lock.acquire() as lh:
            mtime = os.stat(lock_file).st_mtime

            # poll up to 0.5 seconds in case thread delay due to busyness
            start = time.time()
            while True:
                time.sleep(0.005)
                try:
                    self.assertGreater(os.stat(lock_file).st_mtime, mtime)
                except AssertionError as exc:
                    if time.time() - start > 0.5: raise exc
                else:
                    break

if __name__ == '__main__':
    unittest.main()
