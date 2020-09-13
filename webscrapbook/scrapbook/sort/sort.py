from natsort import natsorted, ns
from ..common.tree import TocTree, traverse_tree
from ..common.files import writeToc, Toc, Metadata

# sorting folders
###############################################################################

def sort_folder(id_val, sort_key, sort_direction='a', recursive=False):
    ''' Sort a folder 
    
    Parameters:
        id_val (str): the id from the table of contents (toc.js) of the folder to sort.
        sort_key (str): key from metadata (meta.js) to sort on.
        sort_direction: [a,d] ascending or desending.
        recursive (bool): recursively sort child folders
    '''
    _sort_tree_at_folder(id_val, sort_key, sort_direction, recursive)
    writeToc(Toc())

def _sort_tree_at_folder(id_val, sort_key, sort_direction, recursive):
    def sortCurrentFolder(id_val, tree):
        _sort_folder_by_id(id_val, tree, sort_key, sort_direction)

    if not recursive:
        sortCurrentFolder(id_val, TocTree(Toc()))
    else:
        traverse_tree(TocTree(Toc()), id_val, TocTree(Toc()).hasChildren, sortCurrentFolder)

def _sort_folder_by_id(id_val, tree, sort_key, sort_direction):
    ''' default natural sort case insensitive '''
    toc = tree.getToc()
    metadata = Metadata()
    sort_direction = False if sort_direction == 'a' else True

    # do not sort empty folders
    if tree.hasChildren(id_val):
        toc[id_val] = natsorted(toc[id_val], key = lambda e : metadata[e][sort_key], alg=ns.IGNORECASE)
        if sort_direction:
            toc[id_val].reverse()

###############################################################################