"""Miscellaneous Scrapbook book handler.
"""
from collections import defaultdict, deque
from contextlib import nullcontext

from . import cache as wsb_cache
from .host import Host


class HostQuery:
    """A utility to perform a series of query on a scrapbook host."""
    def __init__(self, host, query, auto_cache=None, *, lock=True):
        if isinstance(host, Host):
            pass
        elif isinstance(host, str):
            host = Host(host)
        else:
            host = Host(*host)

        self.host = host
        self.query = query
        self.auto_cache = auto_cache
        self.lock = lock

        self.tasks = []
        self.loads = defaultdict(set)
        self.changes = defaultdict(set)
        self.modified = defaultdict(set)
        self.results = []

    def run(self):
        for q in self.query:
            book_id = q.get('book', '')
            cmd = q.get('cmd', '')
            args = q.get('args', ())
            kwargs = q.get('kwargs', {})

            try:
                book = self.host.books[book_id]
            except KeyError:
                raise ValueError(f'Invalid book ID: {book_id!r}') from None

            if book.no_tree:
                raise ValueError(f'Unable to query on a no_tree book: {book_id!r}')

            try:
                func = getattr(book, cmd)
            except AttributeError:
                raise ValueError(f'Invalid command: {cmd!r}') from None

            task = (book_id, cmd, func, args, kwargs)
            self.tasks.append(task)

            changes = getattr(self, f'_cmd_{cmd}_changes', ())
            self.changes[book_id].update(changes)

            loads = getattr(self, f'_cmd_{cmd}_loads', changes)
            self.loads[book_id].update(loads)

            try:
                prehandler = getattr(self, f'_cmd_{cmd}_prehandler')
            except AttributeError:
                pass
            else:
                prehandler(book_id, args, kwargs)

        self.run_tasks()
        return self.results

    def run_tasks(self):
        book_ids = deque(self.changes)
        self._with_next_book(book_ids)

    def _with_next_book(self, book_ids):
        try:
            book_id = book_ids.popleft()
        except IndexError:
            book_id = None

        if book_id is None:
            self._run_tasks()
            return

        book = self.host.books[book_id]
        lh = book.get_tree_lock(persist=self.lock).acquire() if self.lock else nullcontext()
        with lh:
            if 'meta' in self.loads[book_id]:
                book.load_meta_files()

            if 'toc' in self.loads[book_id]:
                book.load_toc_files()

            if 'meta' in self.changes[book_id]:
                book_meta_orig = book.checksum(book.meta)

            if 'toc' in self.changes[book_id]:
                book_toc_orig = book.checksum(book.toc)

            self._with_next_book(book_ids)

            if 'meta' in self.changes[book_id]:
                if book.checksum(book.meta) != book_meta_orig:
                    book.save_meta_files()

            if 'toc' in self.changes[book_id]:
                if book.checksum(book.toc) != book_toc_orig:
                    book.save_toc_files()

    def _run_tasks(self):
        for book_id, cmd, func, args, kwargs in self.tasks:
            try:
                rv = func(*args, **kwargs)
            except Exception as exc:
                task_args = []
                for arg in args:
                    task_args.append(f'{arg!r}')
                for k, v in kwargs.items():
                    task_args.append(f'{k}={v!r}')
                task_args = ', '.join(task_args)
                raise RuntimeError(
                    f'Failed to query: {func.__name__}({task_args}): {exc}'
                ) from exc

            self.results.append(rv)

            try:
                posthandler = getattr(self, f'_cmd_{cmd}_posthandler')
            except (KeyError, AttributeError):
                pass
            else:
                posthandler(book_id, args, kwargs, rv)

        if self.auto_cache:
            # prevent getting an empty set, which means all items
            book_items = {
                book_id: item_ids
                for book_id, item_ids in self.modified.items()
                if item_ids
            }

            if book_items:
                gen = wsb_cache.generate(self.host, book_items,
                                         lock=False, backup=False,
                                         **self.auto_cache)
                for _ in gen:
                    pass

    _cmd_get_item_loads = {'meta', 'toc'}

    _cmd_get_items_loads = _cmd_get_item_loads

    _cmd_add_item_changes = {'meta', 'toc'}

    def _cmd_add_item_posthandler(self, book_id, args, kwargs, rv):
        self.modified[book_id].update(rv)

    _cmd_add_items_changes = _cmd_add_item_changes

    _cmd_add_items_posthandler = _cmd_add_item_posthandler

    _cmd_update_item_changes = {'meta'}

    def _cmd_update_item_posthandler(self, book_id, args, kwargs, rv):
        self.modified[book_id].update(rv)

    _cmd_update_items_changes = _cmd_update_item_changes

    _cmd_update_items_posthandler = _cmd_update_item_posthandler

    _cmd_move_item_loads = {'meta', 'toc'}

    _cmd_move_item_changes = {'toc'}

    _cmd_move_items_loads = _cmd_move_item_loads

    _cmd_move_items_changes = _cmd_move_item_changes

    _cmd_link_item_loads = {'meta', 'toc'}

    _cmd_link_item_changes = {'toc'}

    _cmd_link_items_loads = _cmd_link_item_loads

    _cmd_link_items_changes = _cmd_link_item_changes

    _cmd_copy_item_changes = {'meta', 'toc'}

    def _cmd_copy_item_prehandler(self, book_id, args, kwargs):
        target_book_id = kwargs.get('target_book_id')
        if target_book_id not in (None, book_id):
            self.loads[target_book_id].update({'meta', 'toc'})
            self.changes[target_book_id].update({'meta', 'toc'})

    def _cmd_copy_item_posthandler(self, book_id, args, kwargs, rv):
        _, target_book_id, item_ids = rv
        self.modified[target_book_id].update(item_ids)

    _cmd_copy_items_changes = _cmd_copy_item_changes

    _cmd_copy_items_prehandler = _cmd_copy_item_prehandler

    _cmd_copy_items_posthandler = _cmd_copy_item_posthandler

    _cmd_recycle_item_changes = {'meta', 'toc'}

    _cmd_recycle_items_changes = _cmd_recycle_item_changes

    _cmd_unrecycle_item_changes = {'meta', 'toc'}

    _cmd_unrecycle_items_changes = _cmd_unrecycle_item_changes

    _cmd_delete_item_changes = {'meta', 'toc'}

    def _cmd_delete_item_posthandler(self, book_id, args, kwargs, rv):
        self.modified[book_id].update(rv)

    _cmd_delete_items_changes = _cmd_delete_item_changes

    _cmd_delete_items_posthandler = _cmd_delete_item_posthandler

    _cmd_sort_item_loads = {'meta', 'toc'}

    _cmd_sort_item_changes = {'toc'}

    _cmd_sort_items_loads = _cmd_sort_item_loads

    _cmd_sort_items_changes = _cmd_sort_item_changes

    _cmd_load_item_postit_loads = {'meta'}

    _cmd_save_item_postit_changes = {'meta'}

    def _cmd_save_item_postit_posthandler(self, book_id, args, kwargs, rv):
        self.modified[book_id].update(rv)

    _cmd_add_item_subpage_loads = {'meta'}

    def _cmd_add_item_subpage_posthandler(self, book_id, args, kwargs, rv):
        self.modified[book_id].add(rv)
