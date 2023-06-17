"""Search for items in book(s).
"""
import functools
import html
import re
from collections import namedtuple
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

from .. import util
from .host import Host

Item = namedtuple('Item', ('book_id', 'id', 'file', 'meta', 'fulltext', 'context'))
Sort = namedtuple('Sort', ('key', 'subkey', 'order'), defaults=(None, None, 1))
Date = namedtuple('Date', ('since', 'until'))


class QueryError(Exception):
    pass


class Query:
    """Represents a search query."""
    REPR_FIELDS = ('books', 'roots', 'rules', 'sorts', 'limit', 'mc', 're', 'default')

    PARSE_TEXT_REGEX = re.compile(
        r"""
            (?P<cmd>-*[A-Za-z]+:|-+)
            (?:"(?P<qterm1>[^"]*(?:""[^"]*)*)"|(?P<term1>[^"\s]*))
            |
            (?:"(?P<qterm2>[^"]*(?:""[^"]*)*)"|(?P<term2>[^"\s]+))
        """,
        flags=re.X,
    )

    PARSE_CMD_REGEX = re.compile(r'^(-*)(.*)$')

    PARSE_DATE_REGEX = re.compile(r'^(\d{0,17})(?:-(\d{0,17}))?$')

    TIMEZONE = datetime.now(timezone.utc).astimezone().tzinfo

    ELLIPSIS = '…'

    def __init__(self, query_text):
        """Inatialize a new query.

        Raises:
            ValueError: if any input field cannot be parsed correctly
        """
        self.default = 'tcc'
        self.mc = False
        self.re = False
        self.books = {}
        self.roots = {}
        self.rules = {}
        self.sorts = []
        self.limit = 0

        self.PARSE_TEXT_REGEX.sub(self._parse_query, query_text)
        self.roots.setdefault('include', ['root'])

        self.markers = {
            'title': [
                *self.rules.get('tcc', {}).get('include', []),
                *self.rules.get('tc', {}).get('include', []),
                *self.rules.get('title', {}).get('include', []),
            ],
            'file': [
                *self.rules.get('file', {}).get('include', []),
            ],
            'comment': [
                *self.rules.get('tcc', {}).get('include', []),
                *self.rules.get('tc', {}).get('include', []),
                *self.rules.get('comment', {}).get('include', []),
            ],
            'content': [
                *self.rules.get('tcc', {}).get('include', []),
                *self.rules.get('content', {}).get('include', []),
            ],
            'source': [
                *self.rules.get('source', {}).get('include', []),
            ],
        }

    def __repr__(self):
        cls = self.__class__.__name__
        attrs = ', '.join(f'{f}={getattr(self, f)!r}' for f in self.REPR_FIELDS)
        return f'{cls}({attrs})'

    def _parse_query(self, match):
        cmd, qterm1, term1, qterm2, term2 = match.group('cmd', 'qterm1', 'term1', 'qterm2', 'term2')
        pos = True
        if cmd:
            term = qterm1.replace('""', '"') if qterm1 is not None else term1
            m = self.PARSE_CMD_REGEX.search(cmd)
            if len(m.group(1)) % 2 == 1:
                pos = False
            cmd = m.group(2)
        else:
            term = qterm2.replace('""', '"') if qterm2 is not None else term2
            cmd = ''

        if cmd:
            cmd = cmd[:-1]
        else:
            cmd = self.default

        if cmd == 'default':
            self.default = term
        elif cmd == 'mc':
            self.mc = pos
        elif cmd == 're':
            self.re = pos
        elif cmd == 'book':
            inclusion = 'include' if pos else 'exclude'
            self.books.setdefault(inclusion, []).append(term)
        elif cmd == 'root':
            inclusion = 'include' if pos else 'exclude'
            self.roots.setdefault(inclusion, []).append(term)
        elif cmd == 'sort':
            order = 1 if pos else -1
            if term in ('id', 'file'):
                self.sorts.append(Sort(key=term, order=order))
            elif term == 'content':
                self.sorts.append(Sort(key='fulltext', subkey=term, order=order))
            elif term in ('title', 'comment', 'source', 'type', 'create', 'modify'):
                self.sorts.append(Sort(key='meta', subkey=term, order=order))
            else:
                raise ValueError(f'Invalid sort: {term}')
        elif cmd == 'limit':
            try:
                self.limit = int(term, 10) if pos else 0
            except ValueError:
                raise ValueError(f'Invalid limit: {term}') from None
        elif cmd in ('id', 'type'):
            inclusion = 'include' if pos else 'exclude'
            value = self._parse_str(term, True)
            self.rules.setdefault(cmd, {}).setdefault(inclusion, []).append(value)
        elif cmd in ('file', 'tc', 'tcc', 'title', 'comment', 'content',
                     'index', 'charset', 'source', 'icon'):
            inclusion = 'include' if pos else 'exclude'
            value = self._parse_str(term)
            self.rules.setdefault(cmd, {}).setdefault(inclusion, []).append(value)
        elif cmd in ('create', 'modify'):
            inclusion = 'include' if pos else 'exclude'
            value = self._parse_date(term)
            self.rules.setdefault(cmd, {}).setdefault(inclusion, []).append(value)
        elif cmd in ('marked', 'locked', 'location'):
            inclusion = 'include' if pos else 'exclude'
            self.rules.setdefault(cmd, {}).setdefault(inclusion, True)

    def _parse_str(self, term, exact_match=False):
        flags = (0 if self.mc else re.I) | re.M
        if self.re:
            try:
                return re.compile(term, flags=flags)
            except re.error:
                raise ValueError(f'Invalid regex: {term}') from None
        else:
            key = re.escape(term)
            if exact_match:
                key = '^' + key + '$'
            return re.compile(key, flags=flags)

    @classmethod
    def _parse_date(cls, term):
        match = cls.PARSE_DATE_REGEX.search(term)
        try:
            assert match
            since = cls._parse_date_num(f'{match.group(1):0<17}') if match.group(1) else '0' * 17
            until = cls._parse_date_num(f'{match.group(2):0<17}') if match.group(2) else '9' * 17
        except Exception as exc:
            raise ValueError(f'Invalid date: {term}') from exc
        return Date(since, until)

    @classmethod
    def _parse_date_num(cls, text):
        # Set a slightly narrower upper and lower limit for year to prevent
        # an out-of-range error after applying timedelta and timezone
        # conversion as datetime only supports a year between (1, 9999).
        dt = datetime(
            year=min(max(int(text[0:4], 10), 2), 9998),
            month=min(max(int(text[4:6], 10), 1), 12),
            day=1,
            tzinfo=cls.TIMEZONE,
        )
        # Use a timedelta to prevent an out-of-range error as datetime does not
        # support something like (month=11, day=31).
        delta = timedelta(
            days=max(int(text[6:8], 10), 1) - 1,  # minus starting day 1
            hours=int(text[8:10], 10),
            minutes=int(text[10:12], 10),
            seconds=int(text[12:14], 10),
            milliseconds=int(text[14:17], 10),
        )
        dt = (dt + delta).astimezone(timezone.utc)
        return (f'{dt.year:0>4}{dt.month:0>2}{dt.day:0>2}'
                f'{dt.hour:0>2}{dt.minute:0>2}{dt.second:0>2}'
                f'{(dt.microsecond // 1000):0>3}')

    def match_item(self, item):
        for key, rule in self.rules.items():
            if not getattr(self, f'_match_{key}')(rule, item):
                return False
        return True

    @classmethod
    def _match_tc(cls, rule, item):
        value = '\n'.join([
            item.meta.get('title', ''),
            item.meta.get('comment', ''),
        ])
        return cls.match_text(rule, value)

    @classmethod
    def _match_tcc(cls, rule, item):
        value = '\n'.join([
            item.meta.get('title', ''),
            item.meta.get('comment', ''),
            item.fulltext.get('content', ''),
        ])
        return cls.match_text(rule, value)

    @classmethod
    def _match_content(cls, rule, item):
        value = item.fulltext.get('content')
        return cls.match_text(rule, value)

    @classmethod
    def _match_id(cls, rule, item):
        value = item.id
        return cls.match_text_or(rule, value)

    @classmethod
    def _match_file(cls, rule, item):
        value = item.file
        return cls.match_text(rule, value)

    @classmethod
    def _match_title(cls, rule, item):
        value = item.meta.get('title')
        return cls.match_text(rule, value)

    @classmethod
    def _match_comment(cls, rule, item):
        value = item.meta.get('comment')
        return cls.match_text(rule, value)

    @classmethod
    def _match_index(cls, rule, item):
        value = item.meta.get('index')
        return cls.match_text(rule, value)

    @classmethod
    def _match_charset(cls, rule, item):
        value = item.meta.get('charset')
        return cls.match_text(rule, value)

    @classmethod
    def _match_source(cls, rule, item):
        value = item.meta.get('source')
        return cls.match_text(rule, value)

    @classmethod
    def _match_icon(cls, rule, item):
        value = item.meta.get('icon')
        return cls.match_text(rule, value)

    @classmethod
    def _match_type(cls, rule, item):
        value = item.meta.get('type')
        return cls.match_text_or(rule, value)

    @classmethod
    def _match_create(cls, rule, item):
        value = item.meta.get('create')
        return cls.match_date_or(rule, value)

    @classmethod
    def _match_modify(cls, rule, item):
        value = item.meta.get('modify')
        return cls.match_date_or(rule, value)

    @classmethod
    def _match_marked(cls, rule, item):
        value = item.meta.get('marked')
        return cls.match_bool(rule, value)

    @classmethod
    def _match_locked(cls, rule, item):
        value = item.meta.get('locked')
        return cls.match_bool(rule, value)

    @classmethod
    def _match_location(cls, rule, item):
        value = item.meta.get('location')
        return cls.match_bool(rule, value)

    @staticmethod
    def match_bool(rule, value):
        if rule.get('exclude'):
            if value:
                return False
        if rule.get('include'):
            if not value:
                return False
        return True

    @staticmethod
    def match_text(rule, text):
        text = text or ''
        for key in rule.get('exclude', []):
            if key.search(text):
                return False
        for key in rule.get('include', []):
            if not key.search(text):
                return False
        return True

    @staticmethod
    def match_text_or(rule, text):
        text = text or ''
        for key in rule.get('exclude', []):
            if key.search(text):
                return False
        if not rule.get('include'):
            return True
        for key in rule.get('include', []):
            if key.search(text):
                return True
        return False

    @staticmethod
    def match_date_or(rule, date):
        if not date:
            return False
        for key in rule.get('exclude', []):
            if key[0] <= date <= key[1]:
                return False
        if not rule.get('include'):
            return True
        for key in rule.get('include', []):
            if key[0] <= date <= key[1]:
                return True
        return False

    def get_snippet(self, text, marker_type=None, ln=-1):
        if not text:
            return ''

        regexes = self.markers.get(marker_type, [])
        if ln >= 0:
            if marker_type == 'source':
                text, ellipsis = util.cropped(text, ln, self.ELLIPSIS)
            else:
                text, ellipsis = self._crop_at_first_hit(text, regexes, ln)
        else:
            ellipsis = ''
        return ''.join(self._gen_marked_text(text, regexes)) + self._gen_marked_text_marker(ellipsis)

    @classmethod
    def _crop_at_first_hit(cls, text, regexes, length, context_ratio=0.25):
        min_hit = inf = float('inf')
        for regex in regexes:
            m = regex.search(text)
            if not m:
                continue
            start = m.start(0)
            if start < min_hit:
                min_hit = start
        if min_hit < inf:
            start = max(int(min_hit - length * context_ratio), 0)
            text = text[start:]
        return util.cropped(text, length, cls.ELLIPSIS)

    @classmethod
    def _gen_marked_text(cls, text, regexes):
        ln = len(text)

        hits = []
        for idx, regex in enumerate(regexes):
            pos = 0
            m = regex.search(text, pos)
            while m:
                start, end = m.span(0)
                hit = (start, end, idx)
                hits.append(hit)
                pos = max(hit[1], pos + 1)
                if pos > ln:
                    break
                m = regex.search(text, pos)

        hits = sorted(hits, key=cls._gen_marked_text_sortkey)

        pos = 0
        for hit in hits:
            if hit[0] < pos:
                continue
            delta = text[pos:hit[0]]
            if delta:
                yield cls._gen_marked_text_marker(delta)
            match = text[hit[0]:hit[1]]
            if match:
                yield cls._gen_marked_text_marker(match, hit[2])
            pos = hit[1]
        delta = text[pos:]
        if delta:
            yield cls._gen_marked_text_marker(delta)

    @staticmethod
    def _gen_marked_text_sortkey(hit):
        return hit[0]

    @staticmethod
    def _gen_marked_text_marker(text, idx=False):
        if idx is False:
            return html.escape(text)

        if idx is True:
            return '<mark>' + html.escape(text) + '</mark>'

        return f'<mark class="kw{idx}">' + html.escape(text) + '</mark>'


class SearchEngine:
    def __init__(self, host, query_text, *, lock=True, context=None):
        """Inatialize a new search for the host.

        Raises:
            QueryError: if the query cannot be parsed correctly
        """
        self.host = host
        self.query_text = query_text
        try:
            self.query = Query(query_text)
        except ValueError as exc:
            raise QueryError(str(exc)) from exc
        self.lock = lock
        self.context = context or {}

    def run(self):
        """Start the search and yields result items.

        Yields:
            Item: a found item
        """
        for item in self.search():
            self._generate_context(item)
            yield item

    def search(self):
        results = self.search_books()
        if self.query.limit:
            limit = self.query.limit
            if limit > 0:
                i = 0
                for item in results:
                    i += 1
                    if i > limit:
                        break
                    yield item
            else:
                results = tuple(results)
                for i in range(0, len(results) + limit):
                    yield results[i]
            return
        yield from results

    def search_books(self):
        if self.query.books.setdefault('include', []):
            book_ids = {id: None for id in self.query.books['include'] if id in self.host.books}
        else:
            book_ids = self.host.books

        for book_id in book_ids:
            if book_id in self.query.books.setdefault('exclude', []):
                continue

            lh = self.host.books[book_id].get_tree_lock().acquire() if self.lock else nullcontext()
            with lh:
                for item in self.search_book_sorted(book_id):
                    yield item

    def search_book_sorted(self, book_id):
        results = self.search_book(book_id)
        for sort in self.query.sorts:
            keyfunc = functools.partial(self._search_book_sortkey, sort)
            results = sorted(results, key=keyfunc, reverse=sort.order == -1)
        yield from results

    def search_book(self, book_id):
        book = self.host.books[book_id]
        if book.no_tree:
            return

        book.load_meta_files()
        book.load_toc_files()
        book.load_fulltext_files()

        id_pool = {}
        for root in self.query.roots['include']:
            for id in book.get_reachable_items(root):
                id_pool[id] = True
        for root in self.query.roots.setdefault('exclude', []):
            for id in book.get_reachable_items(root):
                try:
                    del id_pool[id]
                except KeyError:
                    pass

        for id in id_pool:
            meta = book.meta.get(id)
            if meta is None:
                continue

            subfiles = book.fulltext.get(id)
            if not subfiles:
                subfiles = {'': {}}

            for file in subfiles:
                item = Item(
                    book_id=book_id,
                    id=id,
                    file=file,
                    meta=meta,
                    fulltext=subfiles[file],
                    context={},
                )
                if self.query.match_item(item):
                    yield item

    @staticmethod
    def _search_book_sortkey(sort, item):
        value = getattr(item, sort.key)
        subkey = sort.subkey
        if subkey is not None:
            value = value.get(sort.subkey, '')
        return value

    def _generate_context(self, item):
        try:
            ln = self.context['title']
            assert isinstance(ln, int)
        except (KeyError, AssertionError):
            pass
        else:
            value = item.meta.get('title', '')
            item.context['title'] = self.query.get_snippet(value, 'title', ln)

        try:
            ln = self.context['file']
            assert isinstance(ln, int)
        except (KeyError, AssertionError):
            pass
        else:
            value = item.file
            item.context['file'] = self.query.get_snippet(value, 'file', ln)

        try:
            ln = self.context['comment']
            assert isinstance(ln, int)
        except (KeyError, AssertionError):
            pass
        else:
            value = item.meta.get('comment', '')
            item.context['comment'] = self.query.get_snippet(value, 'comment', ln)

        try:
            ln = self.context['source']
            assert isinstance(ln, int)
        except (KeyError, AssertionError):
            pass
        else:
            value = item.meta.get('source', '')
            item.context['source'] = self.query.get_snippet(value, 'source', ln)

        try:
            ln = self.context['fulltext']
            assert isinstance(ln, int)
        except (KeyError, AssertionError):
            pass
        else:
            value = item.fulltext.get('content', '')
            item.context['fulltext'] = self.query.get_snippet(value, 'content', ln)


def search(host, query, *, lock=True, context=None):
    """Shorthand to perform a search at given path.

    Raises:
        QueryError: if the query cannot be parsed correctly
    """
    if isinstance(host, Host):
        pass
    elif isinstance(host, str):
        host = Host(host)
    else:
        host = Host(*host)

    engine = SearchEngine(host, query, lock=lock, context=context)
    yield from engine.run()
