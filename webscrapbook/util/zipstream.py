import io


class ZipStream(io.RawIOBase):
    """A class for a streaming ZIP output."""
    def __init__(self):
        self._buffer = b''
        self._size = 0

    def writable(self):
        return True

    def write(self, b):
        if self.closed:
            raise RuntimeError('ZipStream has been closed')
        self._buffer += b
        return len(b)

    def get(self):
        chunk = self._buffer
        self._buffer = b''
        self._size += len(chunk)
        return chunk

    def size(self):
        return self._size
