import sys as _sys
import zipfile as _zipfile
from zipfile import *

__all__ = _zipfile.__all__


if _sys.version_info < (3, 8, 7):
    # Fix an issue causing zip not truncated
    class ZipFile(ZipFile):
        def _write_end_record(self):
            super()._write_end_record()
            if self.mode == "a":
                self.fp.truncate()
            self.fp.flush()
