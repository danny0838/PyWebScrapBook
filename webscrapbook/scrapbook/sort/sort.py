from natsort import natsort_keygen, ns
from webscrapbook.scrapbook.common.tree import TocTree
from webscrapbook.scrapbook.common.treefiles import TreeFiles

# sorting folders
###############################################################################

class Sort:

    def __init__(self, scrapbook_dir):
        self._scrapbook_dir = scrapbook_dir
        self._files = TreeFiles(self._scrapbook_dir)
        self._toc = self._files.files.toc
        self._meta = self._files.files.meta
        self._toc_tree = TocTree(self._toc)

        def safe_dict_index(dict, index):
            return dict[index] if index in dict else ''

        self._sort_keys = {
            'title': lambda x: safe_dict_index(self._meta[x], 'title'),
            'create': lambda x: safe_dict_index(self._meta[x], 'create'),
            'modify': lambda x: safe_dict_index(self._meta[x], 'modify'),
            'source': lambda x: safe_dict_index(self._meta[x], 'source'),
            'comment': lambda x: safe_dict_index(self._meta[x], 'comment') if x != '20200408200623' else 'zzz',
            'id': lambda x: x
        }

    def sort_folder(self, id_val, sort_key, sort_direction='a', recursive=False):
        ''' Sort a folder 
        
        Parameters:
            id_val (str): the id from the table of contents (toc.js) of the folder to sort.
            sort_key (str): key from metadata (meta.js) to sort on.
            sort_direction: [a,d] ascending or desending.
            recursive (bool): recursively sort child folders
        '''
        self._sort_tree_at_folder(id_val, sort_key, sort_direction, recursive)
        self._files.write_toc()

    def _sort_tree_at_folder(self, id_val, sort_key, sort_direction, recursive):
        def sort_current_folder(id_val, tree):
            self._sort_folder_by_id(id_val, tree, sort_key, sort_direction)

        if not recursive:
            sort_current_folder(id_val, self._toc_tree)
        else:
            self._toc_tree.traverse_tree(id_val, self._toc_tree.has_children, sort_current_folder)

    def _sort_folder_by_id(self, id_val, tree, sort_keys, sort_direction):
        ''' default natural sort case insensitive '''
        # TODO: profile difference when sorting in place

        def sort_key_func():
            key_funcs = [self._sort_keys[key] for key in sort_keys]
            return lambda e: [func(e) for func in key_funcs]

        natsort_key = natsort_keygen(key = sort_key_func(), alg=ns.IGNORECASE)

        sort_direction = False if sort_direction == 'a' else True

        # do not sort empty folders
        if self._toc_tree.has_children(id_val):
            self._toc_tree.get_children(id_val).sort(key=natsort_key, reverse=sort_direction)


###############################################################################