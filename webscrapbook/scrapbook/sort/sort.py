from natsort import natsorted, ns
from ..common.tree import TocTree, traverse_tree
from ..common.files import writeToc, Toc, Metadata

# sorting folders
###############################################################################

def sortFolder(id_val, sort_key, sort_direction='a', recursive=False):
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
    def sortCurrentFolder(id_val):
        _sort_folder_by_id(id_val, sort_key, sort_direction)

    if not recursive:
        sortCurrentFolder(id_val)
    else:
        traverse_tree(TocTree(Toc()), id_val, TocTree(Toc()).hasChildren, sortCurrentFolder)

def _sort_folder_by_id(id, sort_key, sort_direction):
    ''' default natural sort case insensitive '''
    toc = Toc()
    metadata = Metadata()
    sort_direction = False if sort_direction == 'a' else True

    # empty dirs not at top level of toc
    if id in toc:
        toc[id] = natsorted(toc[id], key = lambda e : metadata[e][sort_key], alg=ns.IGNORECASE)
        if sort_direction:
            toc[id].reverse()

###############################################################################