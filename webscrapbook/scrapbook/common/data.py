from abc import ABC, abstractmethod
import os, zipfile, itertools
from webscrapbook.util import get_maff_pages, zip_timestamp
from .util import mime_from_filepath

class DataItem:

    def __init__(self, id_val, indexpath, data_dir):
        self.id = id_val
        self.index_files = [create_index_file(self.id, indexpath, data_dir)]

    def resolve_index_files_to_openable(self):
        new_index_files = [[index_file] if index_file.is_openable() 
                            else index_file.resolve_to_index_files()
                            for index_file in self.index_files]
        new_index_files = list(itertools.chain(new_index_files))
        self.index_files = new_index_files



def create_index_file(id_val, indexpath, data_dir, open_func=None, modify_func=None):
        '''
            create index file object
            optionally override open_file method (useful for index files inside of an achive)
        '''
        def get_class_for_mime(mime):
            mime_type_to_class = {
                'text/html':             IndexFileHtml,
                'application/xhtml+xml': IndexFileHtml,
                'application/html+zip':  IndexFileHtz,
                'application/x-maff':    IndexFileMaff,
            }

            if mime_type_to_class[mime]:
                return mime_type_to_class[mime]
            elif mime.startswith('text/'):
                return IndexFileText
            else:
                return IndexFileUnknown

        mime = mime_from_filepath(indexpath)
        index_file = get_class_for_mime(mime)(id_val, indexpath, data_dir, mime)
        # method overrides
        if open_func:
            index_file.open_file = open_func
        if modify_func:
            index_file.get_modify_time = modify_func
        return index_file


class IndexFile(ABC):

    def __init__(self, id_val, indexpath, data_dir, mime):
        self._id = id_val
        self._indexpath = indexpath
        self._data_dir = data_dir
        self._mime = mime
        pass

    def get_modify_time(self):
        file = os.path.join(self._data_dir, self._indexpath)
        try:
            return os.stat(file).st_mtime
        except OSError:
            return None

    def get_index_paths(self):
        return [os.path.basename(self._indexpath)]

    def is_openable(self):
        return True

    def open_file(self):
        file = os.path.join(self._data_dir, self._indexpath)
        try:
            return open(file, 'rb')
        except OSError:
            # @TODO: show error message for exist but unreadable file?
            return None


class IndexFileHtml(IndexFile):
    pass

class IndexFileText(IndexFile):
    # fulltextable but not known mime type
    pass

class IndexFileUnknown(IndexFile):
    # unknown mimetype and cannot be fulltexted
    pass


class IndexFileArchive(IndexFile):
    
    
    def is_openable(self):
        return False
    

    def resolve_to_index_files(self):
        def get_modify_time_zip_index_file(path):
            with zipfile.ZipFile(os.path.join(self._data_dir, self._indexpath)) as zh:
                try:
                    info = zh.getinfo(path)
                    return zip_timestamp(info)
                except KeyError:
                    return None
        
        def get_open_zip_index_file(index_path):
            def open_zip_index_file():
                with zipfile.ZipFile(os.path.join(self._data_dir, self._indexpath)) as zh:
                    try:
                        return zh.open(index_path)
                    except KeyError:
                        return None
            return open_zip_index_file
        
        index_files = []
        index_paths = self.get_index_paths()
        for index_path in index_paths:
            open_func = get_open_zip_index_file(index_path)
            modify_time = get_modify_time_zip_index_file(index_path)
            modify_func = lambda : modify_time
            index_file = create_index_file(index_path, self._data_dir, open_func, modify_func)
            index_files.append(index_file)
        return index_files

class IndexFileHtz(IndexFileArchive):
    def get_index_paths(self):
        return ['index.html']

class IndexFileMaff(IndexFileArchive):
    def get_index_paths(self):
        pages = get_maff_pages(os.path.join(self._data_dir, self._indexpath))
        return [p.indexfilename for p in pages]