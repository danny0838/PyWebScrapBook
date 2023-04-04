import os
import tempfile
from contextlib import contextmanager

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

PROG_DIR = os.path.normpath(os.path.join(ROOT_DIR, '..', 'webscrapbook'))

# The root directory for placing temp directories and files.
# None for auto-detection from the local system.
TEMP_DIR = None


def _():
    if os.name == 'nt':
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.symlink(__file__, os.path.join(tmpdir, 'temp.link'))
            except OSError:
                return False
            else:
                return True
    else:
        return None


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
