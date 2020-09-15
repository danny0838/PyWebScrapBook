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

    def sort_folder(self, id_val, sort_key, sort_direction='a', recursive=False):
        ''' Sort a folder 
        
        Parameters:
            id_val (str): the id from the table of contents (toc.js) of the folder to sort.
            sort_key (str): key from metadata (meta.js) to sort on.
            sort_direction: [a,d] ascending or desending.
            recursive (bool): recursively sort child folders
        '''
        self.__sort_tree_at_folder(id_val, sort_key, sort_direction, recursive)
        self.__files.write_toc(self.__toc)

    def __sort_tree_at_folder(self, id_val, sort_key, sort_direction, recursive):
        def sortCurrentFolder(id_val, tree):
            self.__sort_folder_by_id(id_val, tree, sort_key, sort_direction)

        if not recursive:
            sortCurrentFolder(id_val, self.__toc_tree)
        else:
            traverse_tree(self.__toc_tree, id_val, self.__toc_tree.hasChildren, sortCurrentFolder)

    def __sort_folder_by_id(self, id_val, tree, sort_key, sort_direction):
        ''' default natural sort case insensitive '''
        # TODO: profile difference when sorting in place
        natsort_key = natsort_keygen(key = lambda e : self.__meta[e][sort_key], alg=ns.IGNORECASE)

        sort_direction = False if sort_direction == 'a' else True

        # do not sort empty folders
        if self.__toc_tree.hasChildren(id_val):
            self.__toc_tree.getChildren(id_val).sort(key=natsort_key, reverse=sort_direction)


###############################################################################