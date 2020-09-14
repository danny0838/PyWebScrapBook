from natsort import natsorted, ns
from ..common.tree import TocTree, traverse_tree
from ..common.files import Files

# sorting folders
###############################################################################

class Sort:

    def __init__(self, scrapbook_dir):
        self._scrapbook_dir = scrapbook_dir
        self._files = Files(self._scrapbook_dir)
        self._toc = self._files.files.toc
        self._meta = self._files.files.meta
        self._toc_tree = TocTree(self._toc)

    def sort_folder(self, id_val, sort_key, sort_direction='a', recursive=False):
        ''' Sort a folder 
        
        Parameters:
            id_val (str): the id from the table of contents (toc.js) of the folder to sort.
            sort_key (str): key from metadata (meta.js) to sort on.
            sort_direction: [a,d] ascending or desending.
            recursive (bool): recursively sort child folders
        '''
        self._sort_tree_at_folder(id_val, sort_key, sort_direction, recursive)
        self._files.write_toc(self._toc)

    def _sort_tree_at_folder(self, id_val, sort_key, sort_direction, recursive):
        def sortCurrentFolder(id_val, tree):
            self._sort_folder_by_id(id_val, tree, sort_key, sort_direction)

        if not recursive:
            sortCurrentFolder(id_val, self._toc_tree)
        else:
            traverse_tree(self._toc_tree, id_val, self._toc_tree.hasChildren, sortCurrentFolder)

    def _sort_folder_by_id(self, id_val, tree, sort_key, sort_direction):
        ''' default natural sort case insensitive '''
        sort_direction = False if sort_direction == 'a' else True

        # do not sort empty folders
        if self._toc_tree.hasChildren(id_val):
            self._toc[id_val] = natsorted(self._toc[id_val], key = lambda e : self._meta[e][sort_key], alg=ns.IGNORECASE)
            if sort_direction:
                self._toc[id_val].reverse()

###############################################################################