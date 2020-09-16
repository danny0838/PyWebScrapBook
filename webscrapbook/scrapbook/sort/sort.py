from natsort import natsort_keygen, ns
from webscrapbook.scrapbook.common.tree import TocTree, traverse_tree
from webscrapbook.scrapbook.common.files import Files

# sorting folders
###############################################################################

class Sort:

    def __init__(self, scrapbook_dir):
        self.__scrapbook_dir = scrapbook_dir
        self.__files = Files(self.__scrapbook_dir)
        self.__toc = self.__files.files.toc
        self.__meta = self.__files.files.meta
        self.__toc_tree = TocTree(self.__toc)

        def safe_dict_index(dict, index):
            return dict[index] if index in dict else ''

        self.__sort_keys = {
            'title': lambda x: safe_dict_index(self.__meta[x], 'title'),
            'create': lambda x: safe_dict_index(self.__meta[x], 'create'),
            'modify': lambda x: safe_dict_index(self.__meta[x], 'modify'),
            'source': lambda x: safe_dict_index(self.__meta[x], 'source'),
            'comment': lambda x: safe_dict_index(self.__meta[x], 'comment') if x != '20200408200623' else 'zzz',
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
        self.__sort_tree_at_folder(id_val, sort_key, sort_direction, recursive)
        self.__files.write_toc()

    def __sort_tree_at_folder(self, id_val, sort_key, sort_direction, recursive):
        def sortCurrentFolder(id_val, tree):
            self.__sort_folder_by_id(id_val, tree, sort_key, sort_direction)

        if not recursive:
            sortCurrentFolder(id_val, self.__toc_tree)
        else:
            traverse_tree(self.__toc_tree, id_val, self.__toc_tree.hasChildren, sortCurrentFolder)

    def __sort_folder_by_id(self, id_val, tree, sort_keys, sort_direction):
        ''' default natural sort case insensitive '''
        # TODO: profile difference when sorting in place

        def sort_key_func():
            key_funcs = [self.__sort_keys[key] for key in sort_keys]
            return lambda e: [func(e) for func in key_funcs]

        natsort_key = natsort_keygen(key = sort_key_func(), alg=ns.IGNORECASE)

        sort_direction = False if sort_direction == 'a' else True

        # do not sort empty folders
        if self.__toc_tree.hasChildren(id_val):
            self.__toc_tree.getChildren(id_val).sort(key=natsort_key, reverse=sort_direction)


###############################################################################