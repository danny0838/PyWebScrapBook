import os
import tempfile
import unittest
from textwrap import dedent
from unittest import mock

from webscrapbook.scrapbook import cache as wsb_cache
from webscrapbook.scrapbook import host as wsb_host
from webscrapbook.scrapbook import util as wsb_util

from . import TEMP_DIR, TestBookMixin


def setUpModule():
    # set up a temp directory for testing
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='book.util-', dir=TEMP_DIR)
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


class TestHostQuery(TestBookMixin, unittest.TestCase):
    """Try a few simple queries to make sure related resources are loaded and
    saved correctly."""
    def setUp(self):
        self.maxDiff = 8192
        self.root = tempfile.mkdtemp(dir=tmpdir)

        book = self.init_book(
            self.root,
            config=dedent(
                """\
                [book ""]
                name = book0
                top_dir = scrapbook0
                data_dir = data
                tree_dir = tree

                [book "b1"]
                name = book1
                top_dir = scrapbook1
                data_dir = data
                tree_dir = tree
                """
            ),
            meta={
                '20200101000000000': {
                    'index': '20200101000000000/index.html',
                    'title': 'Item 1',
                    'type': 'postit',
                    'create': '20200101000000000',
                    'modify': '20200101000000000',
                },
                '20200102000000000': {
                    'title': 'Item 2',
                    'type': 'bookmark',
                    'create': '20200102000000000',
                    'modify': '20200102000000000',
                    'source': 'http://example.com',
                },
            },
            toc={
                'root': [
                    '20200101000000000',
                ],
                '20200101000000000': [
                    '20200102000000000',
                ],
            },
        )

        file = os.path.join(book.data_dir, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(file))
        with open(file, 'w', encoding='UTF-8') as fh:
            fh.write("""\
<!DOCTYPE html><html><head>\
<meta charset="UTF-8">\
<meta name="viewport" content="width=device-width">\
<style>pre { white-space: pre-wrap; overflow-wrap: break-word; }</style>\
</head><body><pre>
Lorem ipsum dolor sit amet.
</pre></body></html>""")

    def test_get_item(self):
        # should not raise
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'get_item',
                'args': ['20200101000000000'],
            },
        ]).run()

    def test_get_items(self):
        # should not raise
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'get_items',
                'args': [['20200101000000000']],
            },
        ]).run()

    def test_add_item(self):
        with open(os.path.join(self.root, 'scrapbook0', 'data', '20200103000000000.html'), 'w', encoding='UTF-8') as fh:
            fh.write('Donec eget vehicula purus.')

        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'add_item',
                'args': [
                    {
                        'id': '20200103000000000',
                        'title': 'Item 3',
                        'create': '20200103000000000',
                        'modify': '20200103000000000',
                        'index': '20200103000000000.html',
                    },
                ],
            },
        ], auto_cache={'fulltext': True}).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_toc_files()
        book.load_fulltext_files()
        self.assertEqual(book.meta['20200103000000000'], {
            'title': 'Item 3',
            'create': '20200103000000000',
            'modify': '20200103000000000',
            'index': '20200103000000000.html',
        })
        self.assertEqual(book.toc['root'], [
            '20200101000000000',
            '20200103000000000',
        ])
        self.assertEqual(book.fulltext['20200103000000000'], {
            '20200103000000000.html': {
                'content': 'Donec eget vehicula purus.',
            },
        })

    def test_add_items(self):
        with open(os.path.join(self.root, 'scrapbook0', 'data', '20200103000000000.html'), 'w', encoding='UTF-8') as fh:
            fh.write('Donec eget vehicula purus.')

        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'add_items',
                'args': [[
                    {
                        'id': '20200103000000000',
                        'title': 'Item 3',
                        'create': '20200103000000000',
                        'modify': '20200103000000000',
                        'index': '20200103000000000.html',
                    },
                    {
                        'id': '20200104000000000',
                        'title': 'Item 4',
                        'create': '20200104000000000',
                        'modify': '20200104000000000',
                    },
                ]],
            },
        ], auto_cache={'fulltext': True}).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_toc_files()
        book.load_fulltext_files()
        self.assertEqual(book.meta['20200103000000000'], {
            'title': 'Item 3',
            'create': '20200103000000000',
            'modify': '20200103000000000',
            'index': '20200103000000000.html',
        })
        self.assertEqual(book.meta['20200104000000000'], {
            'title': 'Item 4',
            'create': '20200104000000000',
            'modify': '20200104000000000',
        })
        self.assertEqual(book.toc['root'], [
            '20200101000000000',
            '20200103000000000',
            '20200104000000000',
        ])
        self.assertEqual(book.fulltext['20200103000000000'], {
            '20200103000000000.html': {
                'content': 'Donec eget vehicula purus.',
            },
        })

    def test_update_item(self):
        with open(os.path.join(self.root, 'scrapbook0', 'data', '20200101000000000', 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('Phasellus eros quam.')

        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'update_item',
                'args': [
                    {
                        'id': '20200101000000000',
                        'title': 'Item 1f',
                        'modify': '20200101000000001',
                    },
                ],
                'kwargs': {'auto_modify': False},
            },
        ], auto_cache={'fulltext': True}).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_fulltext_files()
        self.assertEqual(book.meta['20200101000000000'], {
            'title': 'Item 1f',
            'type': 'postit',
            'create': '20200101000000000',
            'modify': '20200101000000001',
            'index': '20200101000000000/index.html',
        })
        self.assertEqual(book.fulltext['20200101000000000'], {
            'index.html': {
                'content': 'Phasellus eros quam.',
            },
        })

    def test_update_items(self):
        with open(os.path.join(self.root, 'scrapbook0', 'data', '20200101000000000', 'index.html'), 'w', encoding='UTF-8') as fh:
            fh.write('Phasellus eros quam.')

        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'update_items',
                'args': [[
                    {
                        'id': '20200101000000000',
                        'title': 'Item 1f',
                        'modify': '20200101000000001',
                    },
                    {
                        'id': '20200102000000000',
                        'title': 'Item 2f',
                        'modify': '20200102000000001',
                    },
                ]],
                'kwargs': {'auto_modify': False},
            },
        ], auto_cache={'fulltext': True}).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_fulltext_files()
        self.assertEqual(book.meta['20200101000000000'], {
            'title': 'Item 1f',
            'type': 'postit',
            'create': '20200101000000000',
            'modify': '20200101000000001',
            'index': '20200101000000000/index.html',
        })
        self.assertEqual(book.meta['20200102000000000'], {
            'title': 'Item 2f',
            'type': 'bookmark',
            'create': '20200102000000000',
            'modify': '20200102000000001',
            'source': 'http://example.com',
        })
        self.assertEqual(book.fulltext['20200101000000000'], {
            'index.html': {
                'content': 'Phasellus eros quam.',
            },
        })

    def test_move_item(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'move_item',
                'args': ['20200101000000000', 0, 'hidden'],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
            'hidden': [
                '20200102000000000',
            ],
        })

    def test_move_items(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'move_items',
                'args': [
                    [
                        ('root', 0),
                        ('20200101000000000', 0),
                    ],
                    'hidden',
                ],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'hidden': [
                '20200101000000000',
                '20200102000000000',
            ],
        })

    def test_link_item(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'link_item',
                'args': ['20200101000000000', 0, 'hidden'],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
            '20200101000000000': [
                '20200102000000000',
            ],
            'hidden': [
                '20200102000000000',
            ],
        })

    def test_link_items(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'link_items',
                'args': [
                    [
                        ('root', 0),
                        ('20200101000000000', 0),
                    ],
                    'hidden',
                ],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_toc_files()
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
            '20200101000000000': [
                '20200102000000000',
            ],
            'hidden': [
                '20200101000000000',
                '20200102000000000',
            ],
        })

    def test_copy_item(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'copy_item',
                'args': ['root', 0, 'root'],
                'kwargs': {'target_book_id': 'b1', 'recursively': False},
            },
        ], auto_cache={'fulltext': True}).run()
        book1 = wsb_host.Host(self.root).books['b1']
        book1.load_meta_files()
        book1.load_toc_files()
        book1.load_fulltext_files()
        self.assertEqual(book1.meta['20200101000000000'], {
            'title': 'Item 1',
            'type': 'postit',
            'create': '20200101000000000',
            'modify': '20200101000000000',
            'index': '20200101000000000/index.html',
        })
        self.assertEqual(book1.toc['root'], [
            '20200101000000000',
        ])
        self.assertEqual(book1.fulltext['20200101000000000'], {
            'index.html': {
                'content': 'Lorem ipsum dolor sit amet.',
            },
        })

    def test_copy_items(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'copy_items',
                'args': [[('root', 0)], 'root'],
                'kwargs': {'target_book_id': 'b1', 'recursively': False},
            },
        ], auto_cache={'fulltext': True}).run()
        book1 = wsb_host.Host(self.root).books['b1']
        book1.load_meta_files()
        book1.load_toc_files()
        book1.load_fulltext_files()
        self.assertEqual(book1.meta['20200101000000000'], {
            'title': 'Item 1',
            'type': 'postit',
            'create': '20200101000000000',
            'modify': '20200101000000000',
            'index': '20200101000000000/index.html',
        })
        self.assertEqual(book1.toc['root'], [
            '20200101000000000',
        ])
        self.assertEqual(book1.fulltext['20200101000000000'], {
            'index.html': {
                'content': 'Lorem ipsum dolor sit amet.',
            },
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_recycle_item(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'recycle_item',
                'args': ['20200101000000000', 0],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_toc_files()
        self.assertEqual(book.meta['20200102000000000'], {
            'title': 'Item 2',
            'type': 'bookmark',
            'create': '20200102000000000',
            'modify': '20200102000000000',
            'source': 'http://example.com',
            'parent': '20200101000000000',
            'recycled': '20230101000000000',
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
            'recycle': [
                '20200102000000000',
            ],
        })

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_recycle_items(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'recycle_items',
                'args': [
                    [
                        ('root', 0),
                        ('20200101000000000', 0),
                    ],
                ],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_toc_files()
        self.assertEqual(book.meta['20200101000000000'], {
            'title': 'Item 1',
            'type': 'postit',
            'create': '20200101000000000',
            'modify': '20200101000000000',
            'index': '20200101000000000/index.html',
            'parent': 'root',
            'recycled': '20230101000000000',
        })
        self.assertEqual(book.meta['20200102000000000'], {
            'title': 'Item 2',
            'type': 'bookmark',
            'create': '20200102000000000',
            'modify': '20200102000000000',
            'source': 'http://example.com',
            'parent': '20200101000000000',
            'recycled': '20230101000000000',
        })
        self.assertEqual(book.toc, {
            'recycle': [
                '20200101000000000',
                '20200102000000000',
            ],
        })

    def test_unrecycle_item(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'recycle_item',
                'args': ['20200101000000000', 0],
            },
        ]).run()
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'unrecycle_item',
                'args': ['recycle', 0],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_toc_files()
        self.assertEqual(book.meta['20200102000000000'], {
            'title': 'Item 2',
            'type': 'bookmark',
            'create': '20200102000000000',
            'modify': '20200102000000000',
            'source': 'http://example.com',
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
            '20200101000000000': [
                '20200102000000000',
            ],
        })

    def test_unrecycle_items(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'recycle_items',
                'args': [
                    [
                        ('root', 0),
                        ('20200101000000000', 0),
                    ],
                ],
            },
        ]).run()
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'unrecycle_items',
                'args': [
                    [
                        ('recycle', 0),
                        ('recycle', 1),
                    ],
                ],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_toc_files()
        self.assertEqual(book.meta['20200101000000000'], {
            'title': 'Item 1',
            'type': 'postit',
            'create': '20200101000000000',
            'modify': '20200101000000000',
            'index': '20200101000000000/index.html',
        })
        self.assertEqual(book.meta['20200102000000000'], {
            'title': 'Item 2',
            'type': 'bookmark',
            'create': '20200102000000000',
            'modify': '20200102000000000',
            'source': 'http://example.com',
        })
        self.assertEqual(book.toc, {
            'root': [
                '20200101000000000',
            ],
            '20200101000000000': [
                '20200102000000000',
            ],
        })

    def test_delete_item(self):
        for _ in wsb_cache.generate(self.root, fulltext=True, lock=False, backup=False):
            pass
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'delete_item',
                'args': ['root', 0],
            },
        ], auto_cache={'fulltext': True}).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_toc_files()
        book.load_fulltext_files()
        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertEqual(book.fulltext, {})

    def test_delete_items(self):
        for _ in wsb_cache.generate(self.root, fulltext=True, lock=False, backup=False):
            pass
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'delete_items',
                'args': [[('root', 0)]],
            },
        ], auto_cache={'fulltext': True}).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_toc_files()
        book.load_fulltext_files()
        self.assertEqual(book.meta, {})
        self.assertEqual(book.toc, {})
        self.assertEqual(book.fulltext, {})

    def test_sort_item(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'move_item',
                'args': ['20200101000000000', 0, 'root'],
            },
        ]).run()
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'sort_item',
                'args': ['root', 'title', True],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_toc_files()
        self.assertEqual(book.toc['root'], [
            '20200102000000000',
            '20200101000000000',
        ])

    def test_sort_items(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'move_item',
                'args': ['20200101000000000', 0, 'root'],
            },
        ]).run()
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'sort_items',
                'args': [['root'], 'title', True],
            },
        ]).run()
        book = wsb_host.Host(self.root).books['']
        book.load_toc_files()
        self.assertEqual(book.toc['root'], [
            '20200102000000000',
            '20200101000000000',
        ])

    def test_load_item_postit(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'load_item_postit',
                'args': ['20200101000000000'],
            },
        ]).run()

    @mock.patch('webscrapbook.scrapbook.book._id_now', lambda: '20230101000000000')
    def test_save_item_postit(self):
        wsb_util.HostQuery(self.root, [
            {
                'cmd': 'save_item_postit',
                'args': ['20200101000000000', 'Duis aute\nirure dolor'],
            },
        ], auto_cache={'fulltext': True}).run()
        book = wsb_host.Host(self.root).books['']
        book.load_meta_files()
        book.load_fulltext_files()
        self.assertEqual(book.meta['20200101000000000'], {
            'title': 'Duis aute',
            'type': 'postit',
            'create': '20200101000000000',
            'modify': '20230101000000000',
            'index': '20200101000000000/index.html',
        })
        self.assertEqual(book.fulltext['20200101000000000'], {
            'index.html': {'content': 'Duis aute irure dolor'},
        })


if __name__ == '__main__':
    unittest.main()
