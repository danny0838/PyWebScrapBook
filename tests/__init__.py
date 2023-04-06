import glob
import os
import tempfile
from contextlib import contextmanager

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

PROG_DIR = os.path.normpath(os.path.join(ROOT_DIR, '..', 'webscrapbook'))

# The root directory for placing temp directories and files.
# None for auto-detection from the local system.
TEMP_DIR = None


def _():
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.symlink(__file__, os.path.join(tmpdir, 'temp.link'))
        except OSError:
            return False
        else:
            return True


SYMLINK_SUPPORTED = _()


@contextmanager
def test_file_cleanup(*paths):
    """Call os.remove() afterwards for given paths.

    - Mainly to prevent tree cleanup issue for junctions in Python 3.7
    """
    try:
        yield
    finally:
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass


def glob_files(path):
    """Get a set of files and directories under the path (inclusive).

    - Note that the path itself in the glob result will be appended an os.sep,
      and shuould usually be matched with os.path.join(path, '')
    - Hidden ('.'-leading) files are not included unless include_hidden=True,
      which is supported since Python 3.11, is provided to glob.

    Returns:
        set: files and directories under the path (inclusive)
    """
    return {*glob.iglob(os.path.join(glob.escape(path), '**'), recursive=True)}
