import datetime
from webscrapbook.scrapbook.common.util import get_unique_canonical_path
from webscrapbook.scrapbook.common.book import Book

from webscrapbook.scrapbook.sort import sort


class Scrapbook:
    
    def __init__(self, scrapbook_dir):
        self._book = Book(scrapbook_dir)

    def sort(self, id_val, sort_key, sort_direction, recursive):
        s = sort.Sort(self._book)
        s.sort_folder(id_val, sort_key, sort_direction, recursive)


class _Scrapbooks:
    '''
    load scrapbooks to run operations on

    global object pattern
    flyweight pattern
    '''

    def __init__(self):
        self.books = dict()
        
    def _is_book_loaded(self, scrapbook_dir):
        return scrapbook_dir in self.books

    def _get_book(self, scrapbook_dir):
        return self.books[scrapbook_dir]['book']

    def _add_book(self, scrapbook_dir):
        self.books[scrapbook_dir] = {
            'loaded': datetime.datetime.now(),
            'book': Scrapbook(scrapbook_dir)
        }

    def get_book(self, scrapbook_dir) -> Scrapbook:
        scrapbook_dir = get_unique_canonical_path(scrapbook_dir)

        if not self._is_book_loaded(scrapbook_dir):
            self._add_book(scrapbook_dir)
        
        return self._get_book(scrapbook_dir)


scrapbooks = _Scrapbooks()