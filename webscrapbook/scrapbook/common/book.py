from webscrapbook.scrapbook.common.treefiles import TreeFiles

class Book:

    def __init__(self, scrapbook_dir):
        self.scrapbook_dir = scrapbook_dir
        self.treefiles = TreeFiles(self.scrapbook_dir)
