from typing import List


class TreeFileInterface:
    def get_data(self, parameter_list):
        raise NotImplementedError

class TreeInterface:
    def valid_node(self, node):
        '''return if node is in the tree'''
        raise NotImplementedError
    def has_children(self, node: str) -> bool:
        '''does a given node have children'''
        raise NotImplementedError
    def get_children(self, node) -> List[str]:
        '''return list of children for current node'''
        raise NotImplementedError
    def traverse_tree(self, start_node, node_check, callback):
        '''traverse tree'''
        raise NotImplementedError


class Toc(TreeInterface, TreeFileInterface):
    ''' class to navigate toc which is a linked list tree '''
    def __init__(self, toc: dict):
        self.toc = toc

    def valid_node(self, node):
        # quick incomplete check
        if self.has_children(node):
            return True
        # slow complete check
        for children in self.get_children(node):
            if node in children:
                return True
        return False

    def has_children(self, node):
        return node in self.toc
  
    def get_children(self, node):
        if self.has_children(node):
            return self.toc[node]
        else:
            return []

    def traverse_tree(self, start_node, node_check, callback):
        '''
        in order recursive traversal
        callback runs on each node if nodeCheck is True
        '''
        def recurse(self, node, callback):
            if node_check(node):
                callback(node, self)
        
            if not self.hasChildren(node):
                return

            for child in self.getChildren(node):
                recurse(self, child, callback)
        recurse(self, start_node, callback)

    def get_data(self):
        return self.toc


class Meta(TreeFileInterface):
    ''' class to manipulate meta which is a normal dictionary '''
    def __init__(self, meta: dict):
        self.meta = meta

    def is_valid_item(self, id_val):
        return id_val in self.meta

    def get(self, id_val, metadata_index):
        if self.is_valid_item(id_val):
            return self.meta[id_val].get(metadata_index,'')
        else:
            raise Exception('Metadata item with id {} not found'.format(id_val))
    
    def get_items(self):
        return self.meta.items()
    
    def get_ids(self):
        return self.meta.keys()

    def get_data(self):
        return self.meta

class Fulltext(TreeFileInterface):
    ''' class to manipulate fulltext which is a normal dictionary '''
    def __init__(self, fulltext: dict):
        self.fulltext = fulltext

    def remove_item(self, id_val):
        del self.fulltext[id_val]

    def add_item_content(self, id_val, index_path, fulltext_content):
        if not self.item_exists(id_val):
            self.fulltext[id_val] = {}
        self.fulltext[id_val][index_path] = {
            'content': fulltext_content,
        }

    def item_exists(self, id_val):
        return id_val in self.fulltext    

    def get_ids(self):
        return self.fulltext.keys()

    def get_data(self):
        return self.fulltext