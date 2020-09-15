from typing import List

class TreeInterface:
    def validNode(self, node):
        '''return if node is in the tree'''
        pass
    def hasChildren(self, node: str) -> bool:
        '''does a given node have children'''
        pass
    def getChildren(self, node) -> List[str]:
        '''return list of children for current node'''
        pass


class TocTree(TreeInterface):
    ''' class to navigate toc which is a linked list tree '''
    def __init__(self, toc: dict):
        self.toc = toc

    def validNode(self, node):
        # quick incomplete check
        if self.hasChildren(node):
            return True
        # slow complete check
        for children in self.getChildren(node):
            if node in children:
                return True
        return False

    def hasChildren(self, node):
        return node in self.toc
  
    def getChildren(self, node):
        if self.hasChildren(node):
            return self.toc[node]
        else:
            return []

    def getToc(self):
        return self.toc

def traverse_tree(tree: TreeInterface, start_node, nodeCheck, callback):
    '''
    in order recursive traversal
    callback runs on each node if nodeCheck is True
    '''
    def recurse(tree, node, callback):
        if nodeCheck(node):
            callback(node, tree)
    
        if not tree.hasChildren(node):
            return

        for child in tree.getChildren(node):
            recurse(tree, child, callback)
    recurse(tree, start_node, callback)