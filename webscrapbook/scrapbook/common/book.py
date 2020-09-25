from webscrapbook.scrapbook.common.treefiles import TreeFiles
from webscrapbook.scrapbook.common.datafiles import DataFiles


class Book:

    def __init__(self, scrapbook_dir):
        self.scrapbook_dir = scrapbook_dir
        self.treefiles = TreeFiles(self.scrapbook_dir)
        self.datafiles = DataFiles(self.scrapbook_dir, self.treefiles.files.meta.data)
