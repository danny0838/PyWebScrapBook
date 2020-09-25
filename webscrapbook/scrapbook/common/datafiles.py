import os
from collections import OrderedDict
from itertools import count
from .util import (
    remove_prefix,
    remove_suffix,
    remove_lines,
    parse_json,
    Memoize,
    find_regex_file,
    write_file,
    delete_file,
    file_exists,
    get_number_suffix,
    SimpleObject,
    merge_dictionaries,
    split_dictionary
)
from .tree import Meta
from .data import DataItem

class DataFiles:

    def __init__(self, scrapbook_dir, meta: Meta):
        self._meta = meta

        self._scrapbook_dir = os.path.expanduser(scrapbook_dir)
        self._data_dir      = os.path.join(self._scrapbook_dir, 'data/')
        self._valid_scrapbook_dir()
        
        self.load_data_items()

    def _valid_scrapbook_dir(self):
        ''' 
        raises exceptions if scrapbook directory is invalid and get filepaths for necessary files
        '''
        if not os.path.isdir(self._data_dir):
            raise Exception(self._data_dir + ' is not a scrapbook directory')

    # load data items
    ###############################################################################

    def _add_data_item(self, id_val, val):
        if id_val not in self.data_items:
            self.data_items[id_val] = val
        else:
            raise Exception('Data item with id {} already exists'.format(id_val))

    def _get_data_item_ids(self):
        def valid_data_item(id_val):
            indexfile_path = self._meta.get(id_val, 'index')
            valid_condition =  all([
                    self._meta.is_valid_item(id_val),
                    indexfile_path,
                    file_exists(self._data_dir, indexfile_path)
            ])
            return valid_condition

        items = self._meta.get_ids()
        return [ i for i in items if valid_data_item(i)]


    def load_data_items(self):
        self.data_items = dict()
        data_item_ids = self._get_data_item_ids()
        for id_val in data_item_ids:
            data_item = DataItem(id_val, self._meta.get(id_val, 'index'), self._data_dir)
            self._add_data_item(id_val, data_item)



