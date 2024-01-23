import os
import re
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from webscrapbook.scrapbook import search

from . import TEMP_DIR, TestBookMixin


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='search-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)

    # mock out user config
    global mockings
    mockings = (
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.devnull),
        mock.patch('webscrapbook.WSB_USER_DIR', os.devnull),
        mock.patch('webscrapbook.WSB_USER_CONFIG', os.devnull),
    )
    for mocking in mockings:
        mocking.start()


def tearDownModule():
    """Cleanup the temp directory."""
    _tmpdir.cleanup()

    # stop mock
    for mocking in mockings:
        mocking.stop()


class TestQuery(unittest.TestCase):
    def test_syntax_space(self):
        query = search.Query('foo bar baz')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('foo', re.I | re.M),
                    re.compile('bar', re.I | re.M),
                    re.compile('baz', re.I | re.M),
                ],
            },
        })

        query = search.Query('中文　字串')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('中文', re.I | re.M),
                    re.compile('字串', re.I | re.M),
                ],
            },
        })

        query = search.Query('tab\tseparated\twords')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('tab', re.I | re.M),
                    re.compile('separated', re.I | re.M),
                    re.compile('words', re.I | re.M),
                ],
            },
        })

    def test_syntax_negative(self):
        query = search.Query('-one --two ---three ----four')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('two', re.I | re.M),
                    re.compile('four', re.I | re.M),
                ],
                'exclude': [
                    re.compile('one', re.I | re.M),
                    re.compile('three', re.I | re.M),
                ],
            },
        })

        query = search.Query('hypen-sep-words -neg-hyper-sep-words')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile(re.escape('hypen-sep-words'), re.I | re.M),
                ],
                'exclude': [
                    re.compile(re.escape('neg-hyper-sep-words'), re.I | re.M),
                ],
            },
        })

    def test_syntax_quote(self):
        query = search.Query('" foo bar "')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile(re.escape(' foo bar '), re.I | re.M),
                ],
            },
        })

        query = search.Query('"　中文　字串　"')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('　中文　字串　', re.I | re.M),
                ],
            },
        })

        query = search.Query('"double ""double quotes"" escape"')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile(re.escape('double "double quotes" escape'), re.I | re.M),
                ],
            },
        })

        query = search.Query('hyphen-sep1"foo bar"hyphen-sep2')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile(re.escape('hyphen-sep1'), re.I | re.M),
                    re.compile(re.escape('foo bar'), re.I | re.M),
                    re.compile(re.escape('hyphen-sep2'), re.I | re.M),
                ],
            },
        })

        query = search.Query('-hyphen-sep1"foo bar"-hyphen-sep2')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile(re.escape('foo bar'), re.I | re.M),
                ],
                'exclude': [
                    re.compile(re.escape('hyphen-sep1'), re.I | re.M),
                    re.compile(re.escape('hyphen-sep2'), re.I | re.M),
                ],
            },
        })

        query = search.Query('foo""bar')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('foo', re.I | re.M),
                    re.compile('', re.I | re.M),
                    re.compile('bar', re.I | re.M),
                ],
            },
        })

        query = search.Query('foo"')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('foo', re.I | re.M),
                ],
            },
        })

    def test_syntax_cmd_unknown(self):
        query = search.Query('wtf:')
        self.assertEqual(query.rules, {})

        query = search.Query('-wtf:')
        self.assertEqual(query.rules, {})

    def test_syntax_cmd_default(self):
        query = search.Query('default:tc')
        self.assertEqual(query.default, 'tc')

        query = search.Query('-default:tc')
        self.assertEqual(query.default, 'tc')

        query = search.Query('default:tc foo default:tcc bar')
        self.assertEqual(query.rules, {
            'tc': {
                'include': [
                    re.compile('foo', re.I | re.M),
                ],
            },
            'tcc': {
                'include': [
                    re.compile('bar', re.I | re.M),
                ],
            },
        })

    def test_syntax_cmd_mc(self):
        query = search.Query('mc:')
        self.assertEqual(query.mc, True)

        query = search.Query('-mc:')
        self.assertEqual(query.mc, False)

        query = search.Query('mc: abc "def" -mc: ghi "jkl"')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('abc', re.M),
                    re.compile('def', re.M),
                    re.compile('ghi', re.I | re.M),
                    re.compile('jkl', re.I | re.M),
                ],
            },
        })

        query = search.Query('mc:abc mc:"def" -mc:ghi -mc:"jkl"')
        self.assertEqual(query.rules, {})

    def test_syntax_cmd_re(self):
        query = search.Query('re:')
        self.assertEqual(query.re, True)

        query = search.Query('-re:')
        self.assertEqual(query.re, False)

        query = search.Query('re: (?:a|b) "^.*.+?$" -re: (?:a|b) "^.*.+?$"')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile(r'(?:a|b)', re.I | re.M),
                    re.compile(r'^.*.+?$', re.I | re.M),
                    re.compile(re.escape(r'(?:a|b)'), re.I | re.M),
                    re.compile(re.escape(r'^.*.+?$'), re.I | re.M),
                ],
            },
        })

        query = search.Query('re:(?:a|b) re:"^.*.+?$" -re:(?:a|b) -re:"^.*.+?$"')
        self.assertEqual(query.rules, {})

    def test_syntax_cmd_book(self):
        query = search.Query('book: book:b2 book:"spaced bookname"')
        self.assertEqual(query.books, {
            'include': [
                '',
                'b2',
                'spaced bookname',
            ],
        })

        query = search.Query('-book: -book:b2 -book:"spaced bookname"')
        self.assertEqual(query.books, {
            'exclude': [
                '',
                'b2',
                'spaced bookname',
            ],
        })

        # no regex
        query = search.Query('re: book:"book*2"')
        self.assertEqual(query.books, {
            'include': [
                'book*2',
            ],
        })

    def test_syntax_cmd_root(self):
        # include 'root' if not set
        query = search.Query('')
        self.assertEqual(query.roots, {
            'include': [
                'root',
            ],
        })

        query = search.Query('root:20000101000000000 root:"20000202000000000"')
        self.assertEqual(query.roots, {
            'include': [
                '20000101000000000',
                '20000202000000000',
            ],
        })

        query = search.Query('-root:20000101000000000 -root:"20000202000000000"')
        self.assertEqual(query.roots, {
            'include': [
                'root',
            ],
            'exclude': [
                '20000101000000000',
                '20000202000000000',
            ],
        })

        # no regex
        query = search.Query('re: root:200001010000.000')
        self.assertEqual(query.roots, {
            'include': [
                '200001010000.000',
            ],
        })

    def test_syntax_cmd_id(self):
        query = search.Query('id:20200101000000 id:"20200202000000"')
        self.assertEqual(query.rules, {
            'id': {
                'include': [
                    re.compile('^20200101000000$', re.I | re.M),
                    re.compile('^20200202000000$', re.I | re.M),
                ],
            },
        })

        query = search.Query('re: id:20200101000.* id:"20200202000.*"')
        self.assertEqual(query.rules, {
            'id': {
                'include': [
                    re.compile('20200101000.*', re.I | re.M),
                    re.compile('20200202000.*', re.I | re.M),
                ],
            },
        })

        query = search.Query('-id:20200101000000 -id:"20200202000000"')
        self.assertEqual(query.rules, {
            'id': {
                'exclude': [
                    re.compile('^20200101000000$', re.I | re.M),
                    re.compile('^20200202000000$', re.I | re.M),
                ],
            },
        })

        query = search.Query('re: -id:20200101000.* -id:"20200202000.*"')
        self.assertEqual(query.rules, {
            'id': {
                'exclude': [
                    re.compile('20200101000.*', re.I | re.M),
                    re.compile('20200202000.*', re.I | re.M),
                ],
            },
        })

    def test_syntax_cmd_type(self):
        query = search.Query('type: type:site type:bookmark type:file type:note type:postit type:unknown')
        self.assertEqual(query.rules, {
            'type': {
                'include': [
                    re.compile('^$', re.I | re.M),
                    re.compile('^site$', re.I | re.M),
                    re.compile('^bookmark$', re.I | re.M),
                    re.compile('^file$', re.I | re.M),
                    re.compile('^note$', re.I | re.M),
                    re.compile('^postit$', re.I | re.M),
                    re.compile('^unknown$', re.I | re.M),
                ],
            },
        })

        query = search.Query('re: type:"my.*type"')
        self.assertEqual(query.rules, {
            'type': {
                'include': [
                    re.compile('my.*type', re.I | re.M),
                ],
            },
        })

        query = search.Query('-type: -type:site -type:bookmark -type:file -type:note -type:postit -type:unknown')
        self.assertEqual(query.rules, {
            'type': {
                'exclude': [
                    re.compile('^$', re.I | re.M),
                    re.compile('^site$', re.I | re.M),
                    re.compile('^bookmark$', re.I | re.M),
                    re.compile('^file$', re.I | re.M),
                    re.compile('^note$', re.I | re.M),
                    re.compile('^postit$', re.I | re.M),
                    re.compile('^unknown$', re.I | re.M),
                ],
            },
        })

        query = search.Query('re: -type:"my.*type"')
        self.assertEqual(query.rules, {
            'type': {
                'exclude': [
                    re.compile('my.*type', re.I | re.M),
                ],
            },
        })

    def test_syntax_cmd_tcc(self):
        query = search.Query('tcc:abc tcc:"def" -tcc:ghi -tcc:"jkl"')
        self.assertEqual(query.rules, {
            'tcc': {
                'include': [
                    re.compile('abc', re.I | re.M),
                    re.compile('def', re.I | re.M),
                ],
                'exclude': [
                    re.compile('ghi', re.I | re.M),
                    re.compile('jkl', re.I | re.M),
                ],
            },
        })

        with self.assertRaises(ValueError):
            query = search.Query('re: tcc:???')

    def test_syntax_cmd_text(self):
        fields = ('file', 'tc', 'title', 'comment', 'content',
                  'index', 'charset', 'source', 'icon')
        for field in fields:
            with self.subTest(field=field):
                query = search.Query(f'{field}:abc other1 {field}:"def" other2 -{field}:ghi other3 -{field}:"jkl"')
                self.assertEqual(query.rules, {
                    field: {
                        'include': [
                            re.compile('abc', re.I | re.M),
                            re.compile('def', re.I | re.M),
                        ],
                        'exclude': [
                            re.compile('ghi', re.I | re.M),
                            re.compile('jkl', re.I | re.M),
                        ],
                    },
                    'tcc': {
                        'include': [
                            re.compile('other1', re.I | re.M),
                            re.compile('other2', re.I | re.M),
                            re.compile('other3', re.I | re.M),
                        ],
                    },
                })

                with self.assertRaises(ValueError):
                    query = search.Query(f're: {field}:???')

    def test_syntax_cmd_bool(self):
        fields = ('marked', 'locked', 'location')
        for field in fields:
            with self.subTest(field=field):
                query = search.Query(f'{field}:')
                self.assertEqual(query.rules, {
                    field: {
                        'include': True,
                    },
                })

                query = search.Query(f'{field}:foo')
                self.assertEqual(query.rules, {
                    field: {
                        'include': True,
                    },
                })

                query = search.Query(f'-{field}:')
                self.assertEqual(query.rules, {
                    field: {
                        'exclude': True,
                    },
                })

                query = search.Query(f'-{field}:foo')
                self.assertEqual(query.rules, {
                    field: {
                        'exclude': True,
                    },
                })

    @staticmethod
    def _dt_to_ts(dt):
        return (f'{dt.year:0>4}{dt.month:0>2}{dt.day:0>2}'
                f'{dt.hour:0>2}{dt.minute:0>2}{dt.second:0>2}'
                f'{(dt.microsecond // 1000):0>3}')

    def test_syntax_cmd_date(self):
        fields = ('create', 'modify')
        for field in fields:
            with self.subTest(field=field):
                query = search.Query(f'{field}:20200102030405000')
                ts = self._dt_to_ts(datetime(2020, 1, 2, 3, 4, 5).astimezone(timezone.utc))
                self.assertEqual(query.rules, {
                    field: {
                        'include': [
                            (ts, '99999999999999999'),
                        ],
                    },
                })

                with self.assertRaises(ValueError):
                    query = search.Query(f'{field}:20200101020304.000')

                with self.assertRaises(ValueError):
                    query = search.Query(f'{field}:abc')

                with self.assertRaises(ValueError):
                    query = search.Query(f'{field}:3e5')

    def test_parse_date(self):
        ts = self._dt_to_ts(datetime(2020, 1, 1).astimezone(timezone.utc))
        ts2 = self._dt_to_ts(datetime(2021, 1, 1).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date('20200101000000000-20210101000000000'),
            (ts, ts2),
        )
        self.assertEqual(
            search.Query._parse_date('20200101-20210101'),
            (ts, ts2),
        )
        self.assertEqual(
            search.Query._parse_date('2020-2021'),
            (ts, ts2),
        )

        ts = self._dt_to_ts(datetime(2020, 1, 2, 3, 4, 5).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date('20200102030405000'),
            (ts, '99999999999999999'),
        )

        self.assertEqual(
            search.Query._parse_date('20200102030405000-'),
            (ts, '99999999999999999'),
        )

        self.assertEqual(
            search.Query._parse_date('-20200102030405000'),
            ('00000000000000000', ts),
        )

        self.assertEqual(
            search.Query._parse_date(''),
            ('00000000000000000', '99999999999999999'),
        )

        ts = self._dt_to_ts(datetime(2000, 1, 1).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date('2'),
            (ts, '99999999999999999'),
        )

        ts = self._dt_to_ts(datetime(1980, 1, 1).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date('198'),
            (ts, '99999999999999999'),
        )

        ts = self._dt_to_ts(datetime(2020, 1, 1).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date('2020'),
            (ts, '99999999999999999'),
        )

        ts = self._dt_to_ts(datetime(2020, 3, 4).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date('20200304'),
            (ts, '99999999999999999'),
        )

    def test_parse_date_num(self):
        # normal case
        ts = self._dt_to_ts(datetime(2020, 12, 31, 0, 0, 0).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20201231000000000'),
            ts,
        )

        # treat month 0 as 1
        ts = self._dt_to_ts(datetime(2020, 1, 31, 0, 0, 0).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20200031000000000'),
            ts,
        )

        # fix excess month
        ts = self._dt_to_ts(datetime(2021, 3, 31, 0, 0, 0).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20201531000000000'),
            ts,
        )

        # treat day 0 as 1
        ts = self._dt_to_ts(datetime(2020, 12, 1, 0, 0, 0).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20201200000000000'),
            ts,
        )

        # fix excess day
        ts = self._dt_to_ts(datetime(2021, 1, 1, 0, 0, 0).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20201232000000000'),
            ts,
        )

        # fix excess hours
        ts = self._dt_to_ts(datetime(2021, 1, 1, 1, 0, 0).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20201231250000000'),
            ts,
        )

        # fix excess minutes
        ts = self._dt_to_ts(datetime(2020, 12, 31, 1, 39, 0).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20201231009900000'),
            ts,
        )

        # fix excess seconds
        ts = self._dt_to_ts(datetime(2020, 12, 31, 0, 1, 39).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20201231000099000'),
            ts,
        )

        # check milliseconds handling
        ts = self._dt_to_ts(datetime(2020, 12, 31, 0, 0, 0, 999000).astimezone(timezone.utc))
        self.assertEqual(
            search.Query._parse_date_num('20201231000000999'),
            ts,
        )

        # round to nearest if too large
        self.assertEqual(
            search.Query._parse_date_num('99999999999999999'),
            '99991231235959999',
        )

        # round to nearest if too large (after adding days)
        self.assertEqual(
            search.Query._parse_date_num('99991299000000000'),
            '99991231235959999',
        )

        # round to nearest if too small
        self.assertEqual(
            search.Query._parse_date_num('00000000000000000'),
            '00010101000000000',
        )

    def test_syntax_cmd_sort(self):
        for field in ('id', 'file'):
            with self.subTest(field=field):
                query = search.Query(f'sort:{field}')
                self.assertEqual(query.sorts, [
                    (field, None, 1)
                ])

                query = search.Query(f'-sort:{field}')
                self.assertEqual(query.sorts, [
                    (field, None, -1)
                ])

        for field in ('content',):
            with self.subTest(field=field):
                query = search.Query(f'sort:{field}')
                self.assertEqual(query.sorts, [
                    ('fulltext', field, 1)
                ])

                query = search.Query(f'-sort:{field}')
                self.assertEqual(query.sorts, [
                    ('fulltext', field, -1)
                ])

        for field in ('title', 'comment', 'source', 'type', 'create', 'modify'):
            with self.subTest(field=field):
                query = search.Query(f'sort:{field}')
                self.assertEqual(query.sorts, [
                    ('meta', field, 1)
                ])

                query = search.Query(f'-sort:{field}')
                self.assertEqual(query.sorts, [
                    ('meta', field, -1)
                ])

        with self.assertRaises(ValueError):
            query = search.Query('sort:')

        with self.assertRaises(ValueError):
            query = search.Query('sort:unknown')

    def test_syntax_cmd_limit(self):
        query = search.Query('limit:5')
        self.assertEqual(query.limit, 5)

        query = search.Query('limit:0')
        self.assertEqual(query.limit, 0)

        with self.assertRaises(ValueError):
            query = search.Query('limit:')

        with self.assertRaises(ValueError):
            query = search.Query('limit:-1')

        with self.assertRaises(ValueError):
            query = search.Query('limit:abc')

        with self.assertRaises(ValueError):
            query = search.Query('limit:3e6')

        query = search.Query('-limit:')
        self.assertEqual(query.limit, -1)

        query = search.Query('-limit:5')
        self.assertEqual(query.limit, -1)

        query = search.Query('limit:5 -limit:')
        self.assertEqual(query.limit, -1)

    def test_match_item(self):
        item = search.Item(
            book_id='',
            id='20200101000000000',
            file='index.html',
            meta={},
            fulltext={},
            context={},
        )

        for cmd in ('tcc', 'tc', 'title', 'comment', 'content', 'id', 'type', 'source'):
            with self.subTest(cmd=cmd):
                query = search.Query(f'{cmd}:foo {cmd}:bar -{cmd}:baz')
                with mock.patch(f'webscrapbook.scrapbook.search.Query._match_{cmd}') as mocked:
                    query.match_item(item)
                mocked.assert_called_once_with(query.rules[cmd], item)

        for cmd in ('create', 'modify'):
            with self.subTest(cmd=cmd):
                query = search.Query(f'{cmd}:202001-202002 {cmd}:2021-2022 -{cmd}:202106-202107')
                with mock.patch(f'webscrapbook.scrapbook.search.Query._match_{cmd}') as mocked:
                    query.match_item(item)
                mocked.assert_called_once_with(query.rules[cmd], item)

    def test_match_item_tcc(self):
        rule = {}

        item = search.Item(
            book_id='',
            id='20200101000000000',
            file='index.html',
            meta={
                'title': 'mytitle',
                'comment': 'mycomment',
            },
            fulltext={
                'content': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
            },
            context={},
        )
        text = '\n'.join((item.meta.get('title', ''), item.meta.get('comment', ''), item.fulltext.get('content', '')))
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text') as mocked:
            search.Query._match_tcc(rule, item)
        mocked.assert_called_once_with(rule, text)

        del item.meta['title']
        del item.meta['comment']
        del item.fulltext['content']
        text = '\n'.join((item.meta.get('title', ''), item.meta.get('comment', ''), item.fulltext.get('content', '')))
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text') as mocked:
            search.Query._match_tcc(rule, item)
        mocked.assert_called_once_with(rule, text)

    def test_match_item_tc(self):
        rule = {}

        item = search.Item(
            book_id='',
            id='20200101000000000',
            file='',
            meta={
                'title': 'mytitle',
                'comment': 'mycomment',
            },
            fulltext={},
            context={},
        )
        text = '\n'.join((item.meta.get('title', ''), item.meta.get('comment', '')))
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text') as mocked:
            search.Query._match_tc(rule, item)
        mocked.assert_called_once_with(rule, text)

        del item.meta['title']
        del item.meta['comment']
        text = '\n'.join((item.meta.get('title', ''), item.meta.get('comment', '')))
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text') as mocked:
            search.Query._match_tc(rule, item)
        mocked.assert_called_once_with(rule, text)

    def test_match_item_content(self):
        rule = {}

        item = search.Item(
            book_id='',
            id='20200101000000000',
            file='index.html',
            meta={},
            fulltext={
                'content': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
            },
            context={},
        )
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text') as mocked:
            search.Query._match_content(rule, item)
        mocked.assert_called_once_with(rule, 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.')

        del item.fulltext['content']
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text') as mocked:
            search.Query._match_content(rule, item)
        mocked.assert_called_once_with(rule, None)

    def test_match_item_id(self):
        rule = {}

        item = search.Item(
            book_id='',
            id='20200101000000000',
            file='',
            meta={},
            fulltext={},
            context={},
        )
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text_or') as mocked:
            search.Query._match_id(rule, item)
        mocked.assert_called_once_with(rule, '20200101000000000')

    def test_match_item_type(self):
        rule = {}

        item = search.Item(
            book_id='',
            id='20200101000000000',
            file='',
            meta={
                'type': '',
            },
            fulltext={},
            context={},
        )
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text_or') as mocked:
            search.Query._match_type(rule, item)
        mocked.assert_called_once_with(rule, '')

        del item.meta['type']
        with mock.patch('webscrapbook.scrapbook.search.Query.match_text_or') as mocked:
            search.Query._match_type(rule, item)
        mocked.assert_called_once_with(rule, None)

    def test_match_item_meta_text(self):
        for cmd in ('title', 'comment', 'source', 'index'):
            with self.subTest(cmd=cmd):
                rule = {}

                item = search.Item(
                    book_id='',
                    id='20200101000000000',
                    file='',
                    meta={
                        cmd: 'my_cmd_value',
                    },
                    fulltext={},
                    context={},
                )
                with mock.patch('webscrapbook.scrapbook.search.Query.match_text') as mocked:
                    getattr(search.Query, f'_match_{cmd}')(rule, item)
                mocked.assert_called_once_with(rule, 'my_cmd_value')

                del item.meta[cmd]
                with mock.patch('webscrapbook.scrapbook.search.Query.match_text') as mocked:
                    getattr(search.Query, f'_match_{cmd}')(rule, item)
                mocked.assert_called_once_with(rule, None)

    def test_match_item_meta_date(self):
        for cmd in ('create', 'modify'):
            with self.subTest(cmd=cmd):
                rule = {}

                item = search.Item(
                    book_id='',
                    id='20200101000000000',
                    file='',
                    meta={
                        cmd: '20200101000000000',
                    },
                    fulltext={},
                    context={},
                )
                with mock.patch('webscrapbook.scrapbook.search.Query.match_date_or') as mocked:
                    getattr(search.Query, f'_match_{cmd}')(rule, item)
                mocked.assert_called_once_with(rule, '20200101000000000')

                del item.meta[cmd]
                with mock.patch('webscrapbook.scrapbook.search.Query.match_date_or') as mocked:
                    getattr(search.Query, f'_match_{cmd}')(rule, item)
                mocked.assert_called_once_with(rule, None)

    def test_match_item_meta_bool(self):
        for cmd in ('marked', 'locked'):
            with self.subTest(cmd=cmd):
                rule = {}

                item = search.Item(
                    book_id='',
                    id='20200101000000000',
                    file='',
                    meta={
                        cmd: True,
                    },
                    fulltext={},
                    context={},
                )
                with mock.patch('webscrapbook.scrapbook.search.Query.match_bool') as mocked:
                    getattr(search.Query, f'_match_{cmd}')(rule, item)
                mocked.assert_called_once_with(rule, True)

                del item.meta[cmd]
                with mock.patch('webscrapbook.scrapbook.search.Query.match_bool') as mocked:
                    getattr(search.Query, f'_match_{cmd}')(rule, item)
                mocked.assert_called_once_with(rule, None)

        for cmd in ('location',):
            with self.subTest(cmd=cmd):
                rule = {}

                item = search.Item(
                    book_id='',
                    id='20200101000000000',
                    file='',
                    meta={
                        'location': {
                            'latitude': 20,
                            'longitude': 120,
                            'accuracy': 2000,
                        },
                    },
                    fulltext={},
                    context={},
                )
                with mock.patch('webscrapbook.scrapbook.search.Query.match_bool') as mocked:
                    getattr(search.Query, f'_match_{cmd}')(rule, item)
                mocked.assert_called_once_with(rule, item.meta['location'])

                del item.meta[cmd]
                with mock.patch('webscrapbook.scrapbook.search.Query.match_bool') as mocked:
                    getattr(search.Query, f'_match_{cmd}')(rule, item)
                mocked.assert_called_once_with(rule, None)

    def test_match_text(self):
        rule = {
            'include': [
                re.compile('foo', re.I | re.M),
                re.compile('bar', re.I | re.M),
            ],
            'exclude': [
                re.compile('baz', re.I | re.M),
                re.compile('xyzzy', re.I | re.M),
            ],
        }
        self.assertFalse(search.Query.match_text(rule, None))
        self.assertFalse(search.Query.match_text(rule, ''))
        self.assertFalse(search.Query.match_text(rule, 'foo'))
        self.assertFalse(search.Query.match_text(rule, 'bar'))
        self.assertTrue(search.Query.match_text(rule, 'foo bar'))
        self.assertFalse(search.Query.match_text(rule, 'foo bar baz'))
        self.assertFalse(search.Query.match_text(rule, 'foo bar xyzzy'))
        self.assertFalse(search.Query.match_text(rule, 'foo bar baz xyzzy'))

    def test_match_text_or(self):
        rule = {
            'include': [
                re.compile('foo', re.I | re.M),
                re.compile('bar', re.I | re.M),
            ],
            'exclude': [
                re.compile('baz', re.I | re.M),
                re.compile('xyzzy', re.I | re.M),
            ],
        }
        self.assertFalse(search.Query.match_text_or(rule, None))
        self.assertFalse(search.Query.match_text_or(rule, ''))
        self.assertTrue(search.Query.match_text_or(rule, 'foo'))
        self.assertTrue(search.Query.match_text_or(rule, 'bar'))
        self.assertTrue(search.Query.match_text_or(rule, 'foo bar'))
        self.assertFalse(search.Query.match_text_or(rule, 'foo bar baz'))
        self.assertFalse(search.Query.match_text_or(rule, 'foo bar xyzzy'))
        self.assertFalse(search.Query.match_text_or(rule, 'foo bar baz xyzzy'))

        # include anything if not set
        rule = {
            'include': [],
            'exclude': [
                re.compile('baz', re.I | re.M),
                re.compile('xyzzy', re.I | re.M),
            ],
        }
        self.assertTrue(search.Query.match_text_or(rule, None))
        self.assertTrue(search.Query.match_text_or(rule, ''))
        self.assertTrue(search.Query.match_text_or(rule, 'foo'))
        self.assertTrue(search.Query.match_text_or(rule, 'bar'))
        self.assertTrue(search.Query.match_text_or(rule, 'foo bar'))
        self.assertFalse(search.Query.match_text_or(rule, 'foo bar baz'))
        self.assertFalse(search.Query.match_text_or(rule, 'foo bar xyzzy'))
        self.assertFalse(search.Query.match_text_or(rule, 'foo bar baz xyzzy'))

    def test_match_bool(self):
        rule = {'include': True}
        self.assertFalse(search.Query.match_bool(rule, None))
        self.assertFalse(search.Query.match_bool(rule, False))
        self.assertFalse(search.Query.match_bool(rule, ''))
        self.assertTrue(search.Query.match_bool(rule, True))
        self.assertTrue(search.Query.match_bool(rule, {'latitude': 20, 'longitude': 120}))

        rule = {'exclude': True}
        self.assertTrue(search.Query.match_bool(rule, None))
        self.assertTrue(search.Query.match_bool(rule, False))
        self.assertTrue(search.Query.match_bool(rule, ''))
        self.assertFalse(search.Query.match_bool(rule, True))
        self.assertFalse(search.Query.match_bool(rule, {'latitude': 20, 'longitude': 120}))

        rule = {'include': True, 'exclude': True}
        self.assertFalse(search.Query.match_bool(rule, None))
        self.assertFalse(search.Query.match_bool(rule, False))
        self.assertFalse(search.Query.match_bool(rule, ''))
        self.assertFalse(search.Query.match_bool(rule, True))
        self.assertFalse(search.Query.match_bool(rule, {'latitude': 20, 'longitude': 120}))

    def test_match_date_or(self):
        rule = {
            'include': [
                ('20200101000000000', '20210101000000000'),
                ('20220101000000000', '20230101000000000'),
            ],
            'exclude': [
                ('20200301000000000', '20200501000000000'),
                ('20200601000000000', '20200801000000000'),
            ],
        }
        self.assertFalse(search.Query.match_date_or(rule, None))
        self.assertFalse(search.Query.match_date_or(rule, '20210201000000000'))
        self.assertTrue(search.Query.match_date_or(rule, '20200201000000000'))
        self.assertTrue(search.Query.match_date_or(rule, '20220201000000000'))
        self.assertFalse(search.Query.match_date_or(rule, '20200310000000000'))
        self.assertFalse(search.Query.match_date_or(rule, '20200610000000000'))

        # include anything if not set
        # exclude if date is missing (None)
        rule = {
            'exclude': [
                ('20200301000000000', '20200501000000000'),
                ('20200601000000000', '20200801000000000'),
            ],
        }
        self.assertFalse(search.Query.match_date_or(rule, None))
        self.assertTrue(search.Query.match_date_or(rule, '20210201000000000'))
        self.assertTrue(search.Query.match_date_or(rule, '20200201000000000'))
        self.assertTrue(search.Query.match_date_or(rule, '20220201000000000'))
        self.assertFalse(search.Query.match_date_or(rule, '20200310000000000'))
        self.assertFalse(search.Query.match_date_or(rule, '20200610000000000'))

    _test_get_snippet_field_cmds = {
        'title': ['title', 'tcc', 'tc'],
        'file': ['file'],
        'comment': ['comment', 'tcc', 'tc'],
        'content': ['content', 'tcc'],
        'source': ['source'],
    }

    def test_get_snippet_mark(self):
        for field, cmds in self._test_get_snippet_field_cmds.items():
            for cmd in cmds:
                with self.subTest(field=field, cmd=cmd):
                    # single regex
                    input = """Sed ac volutpat leo. Sed sapien diam, finibus vel leo a, lacinia laoreet turpis."""
                    expected = """<mark class="kw0">Sed</mark> ac volutpat leo. <mark class="kw0">Sed</mark> sapien diam, finibus vel leo a, lacinia laoreet turpis."""  # noqa: E501
                    query = search.Query(f'{cmd}:sed')
                    self.assertEqual(
                        query.get_snippet(input, field),
                        expected,
                    )

                    # multiple regexes
                    input = """Sed ac volutpat leo. Sed sapien diam, finibus vel leo a, lacinia laoreet turpis."""
                    expected = """<mark class="kw0">Sed</mark> ac <mark class="kw1">volutpat</mark> leo. <mark class="kw0">Sed</mark> sapien diam, finibus vel leo a, lacinia laoreet turpis."""  # noqa: E501
                    query = search.Query(f'{cmd}:sed {cmd}:volutpat')
                    self.assertEqual(
                        query.get_snippet(input, field),
                        expected,
                    )

                    # first win if overlap
                    input = """Donec nec varius sem, vel commodo erat. Sed arcu dui, placerat ut pulvinar nec, tempus et urna. Sed semper eleifend eros sed tempor."""  # noqa: E501
                    expected = """Donec nec varius <mark class="kw1">se</mark>m, vel commodo erat. <mark class="kw0">Sed</mark> arcu dui, placerat ut pulvinar nec, tempus et urna. <mark class="kw0">Sed</mark> <mark class="kw1">se</mark>mper eleifend eros <mark class="kw0">sed</mark> tempor."""  # noqa: E501
                    query = search.Query(f'{cmd}:sed {cmd}:se')
                    self.assertEqual(
                        query.get_snippet(input, field),
                        expected,
                    )

                    input = """Donec nec varius sem, vel commodo erat. Sed arcu dui, placerat ut pulvinar nec, tempus et urna. Sed semper eleifend eros sed tempor."""  # noqa: E501
                    expected = """Donec nec varius <mark class="kw0">se</mark>m, vel commodo erat. <mark class="kw0">Se</mark>d arcu dui, placerat ut pulvinar nec, tempus et urna. <mark class="kw0">Se</mark>d <mark class="kw0">se</mark>mper eleifend eros <mark class="kw0">se</mark>d tempor."""  # noqa: E501
                    query = search.Query(f'{cmd}:se {cmd}:sed')
                    self.assertEqual(
                        query.get_snippet(input, field),
                        expected,
                    )

                    # do not mark an empty match
                    input = """Donec nec varius sem, vel commodo erat."""
                    expected = """Donec nec varius sem, vel commodo erat."""
                    query = search.Query(f'{cmd}:""')
                    self.assertEqual(
                        query.get_snippet(input, field),
                        expected,
                    )

                    # do not mark an excluded keyword
                    input = """Donec nec varius sem, vel commodo erat."""
                    expected = """Donec nec varius sem, vel commodo erat."""
                    query = search.Query(f'-{cmd}:vel')
                    self.assertEqual(
                        query.get_snippet(input, field),
                        expected,
                    )

                    # escape HTML
                    input = """Curabitur <b>suscipit</b> ultrices pharetra.<br>Nullam <em>maximus</em> tellus sem, ac <u>tempus</u> massa eleifend & vitae."""
                    expected = """Curabitur &lt;b&gt;suscipit&lt;/b&gt; ultrices pharetra.&lt;br&gt;<mark class="kw0">Nullam</mark> &lt;em&gt;maximus&lt;/em&gt; tellus sem, ac &lt;u&gt;tempus&lt;/u&gt; massa eleifend &amp; vitae."""  # noqa: E501
                    query = search.Query(f'{field}:nullam')
                    self.assertEqual(
                        query.get_snippet(input, field),
                        expected,
                    )

    def test_get_snippet_crop(self):
        for field, cmds in self._test_get_snippet_field_cmds.items():
            for cmd in cmds:
                with self.subTest(field=field, cmd=cmd):
                    # basic crop
                    input = """Praesent sagittis vitae enim sed luctus."""
                    expected = """Praesent sagittis vitae enim sed luctus."""
                    query = search.Query('')
                    self.assertEqual(
                        query.get_snippet(input, field, 40),
                        expected,
                    )

                    input = """Praesent sagittis vitae enim sed luctus."""
                    expected = """Praesent sagittis vitae enim sed luctu…"""
                    query = search.Query('')
                    self.assertEqual(
                        query.get_snippet(input, field, 39),
                        expected,
                    )

                    input = """Praesent sagittis vitae enim sed luctus."""
                    expected = """…"""
                    query = search.Query('')
                    self.assertEqual(
                        query.get_snippet(input, field, 0),
                        expected,
                    )

                    # no crop if length is negative or undefined
                    input = """Praesent sagittis vitae enim sed luctus."""
                    expected = """Praesent sagittis vitae enim sed luctus."""
                    query = search.Query('')
                    self.assertEqual(
                        query.get_snippet(input, field, -1),
                        expected,
                    )
                    self.assertEqual(
                        query.get_snippet(input, field),
                        expected,
                    )

                    # crop near the keyword
                    # "source" always crop from start
                    input = """Praesent sagittis vitae enim sed luctus. Duis egestas molestie leo, a hendrerit nulla ultrices eget."""
                    if field == 'source':
                        expected = """Praesent sagittis vitae enim …"""
                    else:
                        expected = """egestas <mark class="kw0">molestie</mark> leo, a hendr…"""
                    query = search.Query(f'{field}:molestie')
                    self.assertEqual(
                        query.get_snippet(input, field, 30),
                        expected,
                    )

                    # tail ellipsis shouln't be marked
                    input = """Praesent sagittis vitae enim sed luctus. … Duis egestas molestie leo, a hendrerit nulla ultrices eget."""
                    if field == 'source':
                        expected = """Praesent sagittis vitae enim …"""
                    else:
                        expected = """luctus. <mark class="kw0">…</mark> Duis egestas molest…"""
                    query = search.Query(f'{field}:…')
                    self.assertEqual(
                        query.get_snippet(input, field, 30),
                        expected,
                    )


class TestSearch(TestBookMixin, unittest.TestCase):
    def setUp(self):
        self.maxDiff = 8192
        self.root = tempfile.mkdtemp(dir=tmpdir)

    def get_search_results(self, query_text):
        """Return the results of a regular search as a list."""
        items = list(search.search(self.root, query_text))
        return items

    def test_search_query_error(self):
        with self.assertRaises(search.QueryError):
            self.get_search_results('re: ???')

    def test_search_book(self):
        self.init_host(self.root, config="""\
[book ""]

[book "book1"]

[book "book2"]

[book "book3"]
no_tree = true
""")

        # search in all books if not set
        with mock.patch('webscrapbook.scrapbook.search.SearchEngine.search_book_sorted') as mocked:
            self.get_search_results('')
        self.assertListEqual(mocked.mock_calls, [
            mock.call(''),
            mock.ANY,  # mock.call().__iter__(), or <tuple_iterator> in Python 3.7
            mock.call('book1'),
            mock.ANY,
            mock.call('book2'),
            mock.ANY,
            mock.call('book3'),
            mock.ANY,
        ])

        # search in the provided books in order
        with mock.patch('webscrapbook.scrapbook.search.SearchEngine.search_book_sorted') as mocked:
            self.get_search_results('book: book:book2')
        self.assertListEqual(mocked.mock_calls, [
            mock.call(''),
            mock.ANY,
            mock.call('book2'),
            mock.ANY,
        ])

        with mock.patch('webscrapbook.scrapbook.search.SearchEngine.search_book_sorted') as mocked:
            self.get_search_results('book:book2 book:')
        self.assertListEqual(mocked.mock_calls, [
            mock.call('book2'),
            mock.ANY,
            mock.call(''),
            mock.ANY,
        ])

        # no duplicate
        with mock.patch('webscrapbook.scrapbook.search.SearchEngine.search_book_sorted') as mocked:
            self.get_search_results('book: book: book: book:book2  book:book2')
        self.assertListEqual(mocked.mock_calls, [
            mock.call(''),
            mock.ANY,
            mock.call('book2'),
            mock.ANY,
        ])

    def test_search_root(self):
        self.init_book(
            self.root,
            meta={
                '20200101000000000': {},
                '20200101010000000': {},
                '20200101020000000': {},
                '20200102000000000': {},
                '20200102010000000': {},
                '20200103000000000': {},
                '20200104000000000': {},
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200102000000000',
                    '20200103000000000',
                ],
                '20200101000000000': [
                    '20200101010000000',
                    '20200101020000000',
                ],
                '20200102000000000': [
                    '20200102010000000',
                ],
                'recycled': [
                    '20200104000000000',
                ],
            },
        )

        self.assertListEqual(self.get_search_results(''), [
            search.Item(
                book_id='',
                id='20200101000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101020000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200103000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

        self.assertListEqual(self.get_search_results('root:20200101000000000'), [
            search.Item(
                book_id='',
                id='20200101000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101020000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

        self.assertListEqual(self.get_search_results('root:20200102000000000'), [
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

        self.assertListEqual(self.get_search_results('root:recycled'), [
            search.Item(
                book_id='',
                id='20200104000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

        self.assertListEqual(self.get_search_results('root:20200101000000000 root:20200102000000000'), [
            search.Item(
                book_id='',
                id='20200101000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101020000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

        self.assertListEqual(self.get_search_results('root:20200102000000000 root:20200101000000000'), [
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101020000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

        self.assertListEqual(self.get_search_results('-root:20200101000000000'), [
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102010000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200103000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

    def test_search_sort_id(self):
        self.init_book(
            self.root,
            meta={
                '20200101000000000': {},
                '20200102000000000': {},
                '20200103000000000': {},
                '20200104000000000': {},
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200103000000000',
                    '20200102000000000',
                    '20200104000000000',
                ],
            },
        )

        self.assertListEqual(self.get_search_results('sort:id'), [
            search.Item(
                book_id='',
                id='20200101000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200103000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200104000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

        self.assertListEqual(self.get_search_results('-sort:id'), [
            search.Item(
                book_id='',
                id='20200104000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200103000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200101000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

    def test_search_limit(self):
        self.init_book(
            self.root,
            meta={
                '20200101000000000': {},
                '20200102000000000': {},
                '20200103000000000': {},
                '20200104000000000': {},
            },
            toc={
                'root': [
                    '20200101000000000',
                    '20200102000000000',
                    '20200103000000000',
                    '20200104000000000',
                ],
            },
        )

        # positive: show first n results
        self.assertListEqual(self.get_search_results('limit:2'), [
            search.Item(
                book_id='',
                id='20200101000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])

        # negative: all results
        self.assertListEqual(self.get_search_results('limit:3 -limit:'), [
            search.Item(
                book_id='',
                id='20200101000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200102000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200103000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
            search.Item(
                book_id='',
                id='20200104000000000',
                file='',
                meta={},
                fulltext={},
                context={},
            ),
        ])


if __name__ == '__main__':
    unittest.main()
