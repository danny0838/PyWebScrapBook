import os
import tempfile


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
