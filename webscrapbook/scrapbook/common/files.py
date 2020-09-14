import os, json
from collections import OrderedDict
from .util import (
    remove_prefix,
    remove_suffix,
    remove_lines,
    parse_json,
    Memoize,
    find_file,
    SimpleObject
)


class Files:

    # Constants
    TOC_GLOB  = str("toc*.js")
    META_GLOB = str("meta*.js")

    FILE_COMMENT = "/** \n * Feel free to edit this file, but keep data code valid JSON format.\n */\n"
    
    TOC_PREFIX   = "scrapbook.toc("
    META_PREFIX  = "scrapbook.meta("
    
    TOC_SUFFIX   = ")"
    META_SUFFIX  = TOC_SUFFIX


    def __init__(self, scrapbook_dir):
        self._scrapbook_dir = scrapbook_dir
        self._tree_dir      = os.path.join(self._scrapbook_dir, 'tree/')
        self._toc_file  = ''
        self._meta_file = ''
        self._valid_scrapbook_dir()

        self.files = SimpleObject()
        self.files.toc  = self._load_toc()
        self.files.meta = self._load_meta()

    def _valid_scrapbook_dir(self):
        ''' 
        raises exceptions if scrapbook directory is invalid and get filepaths for necessary files
        '''
        try:
            os.path.isdir(self._tree_dir)
        except:
            raise Exception('Current working directory is not a scrapbook directory')


        def find_glob_file(directory, glob, no_match_message, many_match_message):
            ''' find a find with a glob which must be unique '''
            possible_files = find_file(directory, glob)
            if not possible_files:
                raise Exception(no_match_message)
            elif len(possible_files) > 1:
                raise Exception(many_match_message)
            else:
                return possible_files[0]

        def find_toc():
            self._toc_file = find_glob_file(self._tree_dir, self.TOC_GLOB,
                                'No toc file found in scrapbook directory matching the glob: ' + self.TOC_GLOB + self._tree_dir,
                                'Multiple toc files found in scrapbook directory matching the glob: ' + self.TOC_GLOB)
        def find_meta():
            self._meta_file = find_glob_file(self._tree_dir, self.META_GLOB,
                                'No toc file found in scrapbook directory matching the glob: ' + self.META_GLOB,
                                'Multiple toc files found in scrapbook directory matching the glob: ' + self.META_GLOB)
        find_toc()
        find_meta()


    def write_toc(self, toc: dict):
        def backup_toc():
        # TODO: improve backup
            try:
                os.rename(self._toc_file, self._toc_file + '.bak')
            except:
                raise Exception('Could not backup ' + self._toc_file + ' before writing')

        def write_new_toc(toc):
            def toc_preprocessing(toc):
                return self.FILE_COMMENT + self.TOC_PREFIX + json.dumps(toc) + self.TOC_SUFFIX
            with open(self._toc_file, "w") as file:
                file.write(
                    toc_preprocessing(json.dumps(toc))
                )
        backup_toc()
        write_new_toc(toc)


    # Parse and load files
    ###############################################################################

    @staticmethod
    def _json_preprocessing(comment_lines, prefix, suffix):
        return lambda string: remove_suffix(
                                remove_prefix(
                                    remove_lines(string, comment_lines), prefix), suffix)
    def _load_toc(self):
        return parse_json(self._toc_file,
                        self._json_preprocessing(3, self.TOC_PREFIX, self.TOC_SUFFIX))
    def _load_meta(self):
        return parse_json(self._meta_file,
                        self._json_preprocessing(3, self.META_PREFIX, self.META_SUFFIX))
