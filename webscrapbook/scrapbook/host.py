"""Scrapbook host handler.
"""
import hashlib
import os
import shutil
import stat
import time
from collections import UserDict
from secrets import token_urlsafe
from threading import Thread

from .. import WSB_DIR, Config, util
from ..locales import I18N
from . import book


class LockError(Exception):
    def __init__(self, msg, name=None, file=None, id=None):
        self.msg = msg
        self.name = name
        self.file = file
        self.id = id


class LockAcquireError(LockError):
    pass


class LockTimeoutError(LockAcquireError):
    pass


class LockGenerateError(LockAcquireError):
    pass


class LockRegenerateError(LockGenerateError):
    pass


class LockPersistError(LockAcquireError):
    pass


class LockPersistOSError(LockPersistError):
    pass


class LockPersistUnmatchError(LockPersistError):
    pass


class LockExtendError(LockError):
    pass


class LockExtendNotAcquiredError(LockExtendError):
    pass


class LockExtendNotFoundError(LockExtendError):
    pass


class LockReleaseError(LockError):
    pass


class LockReleaseNotAcquiredError(LockReleaseError):
    pass


class LockReleaseNotFoundError(LockReleaseError):
    pass


class _FileLockAcquireProxy:
    """A help class object returned by FileLock.acquire() for using in a
       with statement.
    """
    def __init__(self, lock):
        self.lock = lock

    def __enter__(self):
        self.lock.keep()
        return self.lock

    def __exit__(self, exc_type, exc_value, traceback):
        if self.lock.locked:
            self.lock.release()


class FileLock:
    """Controller of a file lock.
    """
    def __init__(self, host, name, *,
                 timeout=5, stale=60, persist=False):
        self.host = host
        self.name = name
        self.timeout = timeout
        self.stale = stale
        self.file = os.path.join(host.locks, f'{hashlib.md5(name.encode("utf8")).hexdigest()}.lock')
        self._keeper = None

        if isinstance(persist, str) and persist:
            try:
                with open(self.file, encoding='UTF-8') as fh:
                    assert fh.read() == persist
            except OSError as exc:
                raise LockPersistOSError(
                    f'unable to access lock file for {name!r}',
                    name=self.name, file=self.file, id=persist
                ) from exc
            except AssertionError as exc:
                raise LockPersistUnmatchError(
                    f'unable to persist lock {name!r} with given ID',
                    name=self.name, file=self.file, id=persist
                ) from exc

            self.id = persist
            self._lock = True
        else:
            self.id = token_urlsafe()
            self._lock = False

    @property
    def locked(self):
        """Check if this object holds a locking.
        """
        return self._lock

    def acquire(self, timeout=None, poll_interval=0.1):
        """Acquire the lock.

        Use this method in a context manager:

            with lock.acquire():
                '''do something'''

        or an acquire...release way:

            lock.acquire()
            try:
                '''do something'''
            finally:
                lock.release()

        In the former case an automatic keeper will be set to keep the lock
        from getting expired during the context.

        Args:
            timeout: float timeout to wait for a lock. < 0 to block until the
                lock can be acquired. None to use default timeout.
            poll_interval: float interval of seconds to check whether the lock
                is available.

        Raises:
            LockTimeoutError: if timeout expires
            LockGenerateError: if failed to create lock file
            LockRegenerateError: if failed to reuse a stale lock file
        """
        # skip if we are already locking
        if self._lock:
            return _FileLockAcquireProxy(self)

        if timeout is None:
            timeout = self.timeout

        timeout_time = time.time() + timeout if timeout >= 0 else float('inf')

        try:
            os.makedirs(os.path.dirname(self.file))
        except FileExistsError:
            pass
        except OSError as exc:
            raise LockGenerateError(
                f'unable to create lock {self.name!r}',
                name=self.name, file=self.file
            ) from exc

        while True:
            try:
                with open(self.file, 'x', encoding='UTF-8') as fh:
                    fh.write(self.id)
            except FileExistsError as exc:
                try:
                    st = os.lstat(self.file)
                except FileNotFoundError:
                    # A rare case that lock file has been removed during the
                    # short inverval. Try acquire again.
                    continue
                except OSError as exc:
                    # error out if self.file cannot be stated
                    raise LockGenerateError(
                        f'unable to create lock {self.name!r}',
                        name=self.name, file=self.file
                    ) from exc

                # error out if self.file is not a regular file in POSIX
                # (Windows raises PermissionError rather than FileExistsError
                # in such case)
                if not stat.S_ISREG(st.st_mode):
                    raise LockGenerateError(
                        f'unable to create lock {self.name!r}',
                        name=self.name, file=self.file
                    ) from exc

                t = time.time()

                if t >= timeout_time:
                    raise LockTimeoutError(
                        f'timeout when acquiring lock {self.name!r}',
                        name=self.name, file=self.file
                    ) from None

                stale_time = st.st_mtime + self.stale

                if t >= stale_time:
                    # Current lock file is stale. Rewrite with current ID.
                    try:
                        with open(self.file, 'w', encoding='UTF-8') as fh:
                            fh.write(self.id)
                    except OSError as exc:
                        raise LockRegenerateError(
                            f'unable to regenerate stale lock {self.name!r}',
                            name=self.name, file=self.file) from exc
                    else:
                        break

                time.sleep(poll_interval)
            except OSError as exc:
                raise LockGenerateError(
                    f'unable to create lock {self.name!r}',
                    name=self.name, file=self.file
                ) from exc
            else:
                break

        self._lock = True
        return _FileLockAcquireProxy(self)

    def extend(self):
        """Extend duration of the lock.

        Raises:
            LockExtendError: if the lock cannot be extended
            LockExtendNotAcquiredError: if the lock hasn't been acquired
            LockExtendNotFoundError: if the lock file not exist
        """
        if not self._lock:
            raise LockExtendNotAcquiredError(
                f'lock {self.name!r} has not been acquired',
                name=self.name, file=self.file
            )

        try:
            os.utime(self.file)
        except FileNotFoundError as exc:
            raise LockExtendNotFoundError(
                f'file for lock {self.name!r} does not exist',
                name=self.name, file=self.file
            ) from exc
        except OSError as exc:
            raise LockExtendError(
                f'unable to extend lock {self.name!r}',
                name=self.name, file=self.file
            ) from exc

    def release(self):
        """Release the lock.

        Raises:
            LockReleaseError: if the lock cannot be released
            LockReleaseNotAcquiredError: if the lock hasn't been acquired
            LockReleaseNotFoundError: if the lock file not exist
        """
        if not self._lock:
            raise LockReleaseNotAcquiredError(
                f'lock {self.name!r} has not been acquired',
                name=self.name, file=self.file
            )

        try:
            os.remove(self.file)
        except FileNotFoundError as exc:
            raise LockReleaseNotFoundError(
                f'file for lock {self.name!r} does not exist',
                name=self.name, file=self.file
            ) from exc
        except OSError as exc:
            raise LockReleaseError(
                f'unable to release lock {self.name!r}',
                name=self.name, file=self.file
            ) from exc
        else:
            self._lock = False

    def keep(self):
        """Spawn a keeper thread to keep the lock fresh until released.

        Do not respawn if already have one.
        """
        if self._keeper:
            return self._keeper

        if not self._lock:
            return None

        self._keeper = Thread(target=self._extend, daemon=True)
        self._keeper.start()
        return self._keeper

    def _extend(self):
        """Auto extend the lock before stale in a shorter interval.
        """
        poll_interval = self.stale * 0.2
        while True:
            time.sleep(poll_interval)

            # Skip if the lock has been released.
            # If this lock is re-acquired after a previous release, this
            # keeper will keep working until next release.
            if not self._lock:
                self._keeper = None
                break

            self.extend()


class BooksProxy(UserDict):
    """A proxied dict for Books.

    Generate a Book object when first retrieved and cache it for future
    retrieval.
    """
    def __init__(self, host):
        super().__init__()
        self.host = host
        for book_id in host.config['book']:
            self.data[book_id] = NotImplemented

    def __getitem__(self, key):
        rv = self.data[key]
        if rv is NotImplemented:
            rv = self.data[key] = book.Book(self.host, key)
        return rv


class Host:
    """Controller for a scrapbook set defined by a root directory and configs.
    """
    REPR_ATTRS = ('name', 'root')

    def __init__(self, root, config=None):
        # use the same realpath during the process lifetime
        root = os.path.realpath(root)

        if not config:
            config = Config()
            config.load(root)

        self.root = root
        self.config = config
        self.name = config['app']['name']

        self.chroot = os.path.normpath(os.path.join(root, self.config['app']['root']))
        self.backup_dir = os.path.normpath(os.path.join(root, self.config['app']['backup_dir']))

        theme = util.validate_filename(config['app']['theme'])
        self.themes = [
            os.path.join(root, WSB_DIR, 'themes', theme),
            os.path.join(Config.user_config_dir(), 'themes', theme),
            os.path.normpath(os.path.join(__file__, '..', '..', 'themes', theme)),
        ]
        self.statics = [os.path.join(t, 'static') for t in self.themes]
        self.templates = [os.path.join(t, 'templates') for t in self.themes]
        self.locales = [os.path.join(t, 'locales') for t in self.themes]

        self.locks = os.path.join(root, WSB_DIR, 'locks')

        self.books = BooksProxy(self)

        self._auto_backup_dir = None  # directory for auto backup

    def __repr__(self):
        repr_str = ', '.join(f'{attr}={repr(getattr(self, attr))}' for attr in self.REPR_ATTRS)
        return f'{self.__class__.__name__}({repr_str})'

    def get_i18n(self, lang=None, domain=None):
        return I18N(self.locales, lang, domain)

    def get_static_file(self, filepath):
        """Search for a static file.
        """
        for i in self.statics:
            file = os.path.join(i, filepath)
            if os.path.isfile(file):
                return file
        return None

    def get_lock(self, name, *args, **kwargs):
        """Get a lock object to control lock.
        """
        return FileLock(self, name, *args, **kwargs)

    def get_subpath(self, file):
        """Get subpath of a file relative to (ch)root.

        Also canonicalize path separators to "/".
        """
        path = os.path.relpath(file, self.chroot)

        # Convert non-standard path separators to '/'. (Currently this only
        # happens on Windows, which uses '\', and it's safe to do so since
        # Windows does not allow '/' in filename.)
        path = util.unify_pathsep(path)

        return path

    def backup(self, file, backup_dir=None, base=None, move=False):
        """Create a backup for the file or directory.

        Args:
            file: a path-like for the file or directory to backup. Silently
                skipped if it doesn't exists or the backup cannot be performed.
            backup_dir: a path-like for the directory to create a backup, or
                None to auto-generate one.
            base: an arbitrary base directory (as an absolute path)
                to calculate the backup file path since, or None to use
                (ch)root by default.
            move: True to move file to backup; copy otherwise.

        Raises:
            OSError: failed to copy or move
        """
        if base is None:
            base = self.chroot

        if backup_dir is None:
            ts = util.datetime_to_id()
            backup_dir = os.path.join(self.backup_dir, ts)

        if not os.path.exists(file):
            return

        if not os.path.normcase(os.path.abspath(file)).startswith(os.path.normcase(os.path.join(base, ''))):
            return

        dst = os.path.join(backup_dir, os.path.relpath(file, base))
        if os.path.lexists(dst):
            try:
                shutil.rmtree(dst)
            except NotADirectoryError:
                os.remove(dst)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
        if move:
            shutil.move(file, dst)
        else:
            try:
                shutil.copytree(file, dst)
            except NotADirectoryError:
                shutil.copy2(file, dst)

    def unbackup(self, backup_dir):
        """Remove a backup.

        Args:
            backup_dir: a path-like for the backup.
        """
        try:
            shutil.rmtree(backup_dir)
        except FileNotFoundError:
            pass

    def get_auto_backup_dir(self, ts=True, note=None):
        """Get the path of a subdir for backup.

        Args:
            ts: a webscrapbook ID as timestamp. True to generate one from
                the current time.
            note: a note text for the backup, sanitized to a valid filename

        Returns:
            str: the backup dir path
        """
        if ts is True:
            ts = util.datetime_to_id()

        filename = ts + (f'-{util.validate_filename(note)}' if note else '')

        return os.path.join(self.backup_dir, filename)

    def init_auto_backup(self, ts=True, note=None):
        """Setup a backup dir for following auto backups until next set.

        NOTE: This is not thread-safe and should only be used on a thread-specific
            Host object.

        Args:
            ts: a webscrapbook ID as timestamp. True to generate one from
                the current time. False to disable auto backup.
            note: a note text for the backup, sanitized to a valid filename

        Returns:
            str: the backup dir path
        """
        if ts is False:
            self._auto_backup_dir = None
        else:
            self._auto_backup_dir = self.get_auto_backup_dir(ts, note)

        return self._auto_backup_dir

    def auto_backup(self, file, base=None, move=False):
        """Perform an auto backup if inited.
        """
        if not self._auto_backup_dir:
            return

        self.backup(file, backup_dir=self._auto_backup_dir, base=base, move=move)
