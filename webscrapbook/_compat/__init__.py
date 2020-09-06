import io

def zip_stream(file, chunk_size=8192):
    """Fix non-seekable zip reading stream in Python < 3.7
    """
    if not file.seekable():
        buffer = io.BytesIO()
        while True:
            bytes = file.read(chunk_size)
            if not bytes: break
            buffer.write(bytes)
        file.close()
        file = buffer
    return file
