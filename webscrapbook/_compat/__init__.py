"""Compatibility shims
"""
import io

def zip_stream(file, chunk_size=8192):
    """Fix non-seekable zip reading stream in Python < 3.7
    """
    if not file.seekable():
        buffer = io.BytesIO()
        while True:
            chunk = file.read(chunk_size)
            if not chunk: break
            buffer.write(chunk)
        file.close()
        file = buffer
    return file
