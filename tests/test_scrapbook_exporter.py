import json
import os
import tempfile
import unittest
import zipfile
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from unittest import mock

from webscrapbook import WSB_DIR, util
from webscrapbook.scrapbook import exporter as wsb_exporter

from . import TEMP_DIR


def setUpModule():
    """Set up a temp directory for testing."""
    global _tmpdir, tmpdir
    _tmpdir = tempfile.TemporaryDirectory(prefix='exporter-', dir=TEMP_DIR)
    tmpdir = os.path.realpath(_tmpdir.name)

    # mock out user config
    global mockings
    mockings = [
        mock.patch('webscrapbook.scrapbook.host.WSB_USER_DIR', os.path.join(tmpdir, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_DIR', os.path.join(tmpdir, 'wsb')),
        mock.patch('webscrapbook.WSB_USER_CONFIG', tmpdir),
    ]
    for mocking in mockings:
        mocking.start()


def tearDownModule():
    """Cleanup the temp directory."""
    _tmpdir.cleanup()

    # stop mock
    for mocking in mockings:
        mocking.stop()


class TestExporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def setUp(self):
        """Set up a general temp test folder
        """
        self.test_root = tempfile.mkdtemp(dir=tmpdir)
        self.test_input = os.path.join(self.test_root, 'input')
        self.test_input_wsb = os.path.join(self.test_input, WSB_DIR)
        self.test_input_config = os.path.join(self.test_input_wsb, 'config.ini')
        self.test_input_tree = os.path.join(self.test_input_wsb, 'tree')
        self.test_input_meta = os.path.join(self.test_input_tree, 'meta.js')
        self.test_input_toc = os.path.join(self.test_input_tree, 'toc.js')
        self.test_output = os.path.join(self.test_root, 'output')

        os.makedirs(self.test_input_tree, exist_ok=True)
        os.makedirs(self.test_output, exist_ok=True)

    def test_basic01(self):
        """Test exporting a common */index.html
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder",
    "title": "item0",
    "index": "20200101000000000/index.html",
    "create": "20200102000000000",
    "modify": "20200103000000000",
    "source": "http://example.com",
    "icon": "favicon.bmp"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        index_file = os.path.join(self.test_input, '20200101000000000', 'index.html')
        os.makedirs(os.path.dirname(index_file))
        with open(index_file, 'w', encoding='UTF-8') as fh:
            fh.write('ABC123')

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        with os.scandir(self.test_output) as entries:
            files = sorted(entries, key=lambda x: x.path)

        # files are exported in depth-first order
        with zipfile.ZipFile(files[0]) as zh:
            with zh.open('meta.json') as fh:
                data = json.load(fh)
            with zh.open('export.json') as fh:
                export_info = json.load(fh)
            with zh.open('data/20200101000000000/index.html') as fh:
                index_data = fh.read().decode('UTF-8')

        self.assertEqual(data, {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
            'index': '20200101000000000/index.html',
            'create': '20200102000000000',
            'modify': '20200103000000000',
            'source': 'http://example.com',
            'icon': 'favicon.bmp',
        })

        self.assertEqual(export_info['version'], 1)
        self.assertAlmostEqual(util.id_to_datetime(export_info['id']).timestamp(), datetime.now(timezone.utc).timestamp(), delta=3)
        self.assertEqual(export_info['timestamp'], export_info['id'])
        self.assertEqual(export_info['timezone'], datetime.now().astimezone().utcoffset().total_seconds())
        self.assertEqual(export_info['path'], [{'id': 'root', 'title': ''}])

        self.assertEqual(index_data, 'ABC123')

    def test_basic02(self):
        """Test exporting a common *.htz
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder",
    "title": "item0",
    "index": "20200101000000000.htz",
    "create": "20200102000000000",
    "modify": "20200103000000000",
    "source": "http://example.com",
    "icon": ".wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ]
})""")
        index_file = os.path.join(self.test_input, '20200101000000000.htz')
        with zipfile.ZipFile(index_file, 'w') as zh:
            zh.writestr('index.html', 'ABC123')
        favicon_file = os.path.join(self.test_input_tree, 'favicon', 'dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp')
        os.makedirs(os.path.dirname(favicon_file))
        with open(favicon_file, 'wb') as fh:
            fh.write(b64decode('Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA'))

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        with os.scandir(self.test_output) as entries:
            files = sorted(entries, key=lambda x: x.path)

        # files are exported in depth-first order
        with zipfile.ZipFile(files[0]) as zh:
            with zh.open('meta.json') as fh:
                data = json.load(fh)
            with zh.open('export.json') as fh:
                export_info = json.load(fh)
            with zh.open('data/20200101000000000.htz') as fh:
                with zipfile.ZipFile(fh) as zh2:
                    with zh2.open('index.html') as fh2:
                        index_data = fh2.read().decode('UTF-8')
            with zh.open('favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp') as fh:
                favicon_data = fh.read()

        self.assertEqual(data, {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
            'index': '20200101000000000.htz',
            'create': '20200102000000000',
            'modify': '20200103000000000',
            'source': 'http://example.com',
            'icon': '.wsb/tree/favicon/dbc82be549e49d6db9a5719086722a4f1c5079cd.bmp',
        })

        self.assertEqual(export_info['version'], 1)
        self.assertAlmostEqual(util.id_to_datetime(export_info['id']).timestamp(), datetime.now(timezone.utc).timestamp(), delta=3)
        self.assertEqual(export_info['timestamp'], export_info['id'])
        self.assertEqual(export_info['timezone'], datetime.now().astimezone().utcoffset().total_seconds())
        self.assertEqual(export_info['path'], [{'id': 'root', 'title': ''}])

        self.assertEqual(index_data, 'ABC123')
        self.assertEqual(b64encode(favicon_data), b'Qk08AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABACAAAAAAAAYAAAASCwAAEgsAAAAAAAAAAAAAAP8AAAAA')

    def test_toc01(self):
        """Export all if item_ids not set

        - Include hidden (at last).
        - Exclude recycle.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder",
    "title": "item0"
  },
  "20200101000000001": {
    "type": "folder",
    "title": "item1"
  },
  "20200101000000002": {
    "type": "folder",
    "title": "item2"
  },
  "20200101000000003": {
    "type": "folder",
    "title": "item3"
  },
  "20200101000000004": {
    "type": "folder",
    "title": "item4"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "hidden": [
    "20200101000000003"
  ],
  "root": [
    "20200101000000000",
    "20200101000000001"
  ],
  "20200101000000000": [
    "20200101000000002"
  ],
  "recycle": [
    "20200101000000004"
  ]
})""")

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        with os.scandir(self.test_output) as entries:
            files = sorted(entries, key=lambda x: x.path)
        metas = []
        export_infos = []
        for file in files:
            with zipfile.ZipFile(file) as zh:
                with zh.open('meta.json') as fh:
                    metas.append(json.load(fh))
                with zh.open('export.json') as fh:
                    export_infos.append(json.load(fh))

        self.assertEqual(len(files), 4)
        self.assertEqual(len({e['id'] for e in export_infos}), 4)

        # files are exported in depth-first order
        self.assertEqual(metas[0], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[0]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[1], {
            'id': '20200101000000002',
            'type': 'folder',
            'title': 'item2',
        })
        self.assertEqual(export_infos[1]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000000', 'title': 'item0'},
        ])

        self.assertEqual(metas[2], {
            'id': '20200101000000001',
            'type': 'folder',
            'title': 'item1',
        })
        self.assertEqual(export_infos[2]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[3], {
            'id': '20200101000000003',
            'type': 'folder',
            'title': 'item3',
        })
        self.assertEqual(export_infos[3]['path'], [
            {'id': 'hidden', 'title': ''},
        ])

    def test_toc02(self):
        """Export only those specified by item_ids

        - Never include recycle.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder",
    "title": "item0"
  },
  "20200101000000001": {
    "type": "folder",
    "title": "item1"
  },
  "20200101000000002": {
    "type": "folder",
    "title": "item2"
  },
  "20200101000000003": {
    "type": "folder",
    "title": "item3"
  },
  "20200101000000004": {
    "type": "folder",
    "title": "item4"
  },
  "20200101000000005": {
    "type": "folder",
    "title": "item5"
  },
  "20200101000000006": {
    "type": "folder",
    "title": "item6"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "hidden": [
    "20200101000000003",
    "20200101000000004"
  ],
  "root": [
    "20200101000000000",
    "20200101000000001"
  ],
  "20200101000000000": [
    "20200101000000002"
  ],
  "recycle": [
    "20200101000000005",
    "20200101000000006"
  ]
})""")

        for _info in wsb_exporter.run(
            self.test_input, self.test_output,
            item_ids=['20200101000000000', '20200101000000003', '20200101000000005'],
        ):
            pass

        with os.scandir(self.test_output) as entries:
            files = sorted(entries, key=lambda x: x.path)
        metas = []
        export_infos = []
        for file in files:
            with zipfile.ZipFile(file) as zh:
                with zh.open('meta.json') as fh:
                    metas.append(json.load(fh))
                with zh.open('export.json') as fh:
                    export_infos.append(json.load(fh))

        self.assertEqual(len(files), 2)

        # files are exported in depth-first order
        self.assertEqual(metas[0], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[0]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[1], {
            'id': '20200101000000003',
            'type': 'folder',
            'title': 'item3',
        })
        self.assertEqual(export_infos[1]['path'], [
            {'id': 'hidden', 'title': ''},
        ])

    def test_toc03(self):
        """Export descendants if recursive"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder",
    "title": "item0"
  },
  "20200101000000001": {
    "type": "folder",
    "title": "item1"
  },
  "20200101000000002": {
    "type": "folder",
    "title": "item2"
  },
  "20200101000000003": {
    "type": "folder",
    "title": "item3"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000000001"
  ],
  "20200101000000000": [
    "20200101000000002"
  ],
  "20200101000000002": [
    "20200101000000003"
  ]
})""")

        for _info in wsb_exporter.run(
            self.test_input, self.test_output,
            item_ids=['20200101000000000'], recursive=True,
        ):
            pass

        with os.scandir(self.test_output) as entries:
            files = sorted(entries, key=lambda x: x.path)
        metas = []
        export_infos = []
        for file in files:
            with zipfile.ZipFile(file) as zh:
                with zh.open('meta.json') as fh:
                    metas.append(json.load(fh))
                with zh.open('export.json') as fh:
                    export_infos.append(json.load(fh))

        self.assertEqual(len(files), 3)

        # files are exported in depth-first order
        self.assertEqual(metas[0], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[0]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[1], {
            'id': '20200101000000002',
            'type': 'folder',
            'title': 'item2',
        })
        self.assertEqual(export_infos[1]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000000', 'title': 'item0'},
        ])

        self.assertEqual(metas[2], {
            'id': '20200101000000003',
            'type': 'folder',
            'title': 'item3',
        })
        self.assertEqual(export_infos[2]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000000', 'title': 'item0'},
            {'id': '20200101000000002', 'title': 'item2'},
        ])

    def test_toc04(self):
        """Export all occurrences

        - Occurrences of the same item should share same export id.
        """
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder",
    "title": "item0"
  },
  "20200101000000001": {
    "type": "folder",
    "title": "item1"
  },
  "20200101000000002": {
    "type": "folder",
    "title": "item2"
  },
  "20200101000000003": {
    "type": "folder",
    "title": "item3"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000000000",
    "20200101000000001",
    "20200101000000002"
  ],
  "20200101000000001": [
    "20200101000000000"
  ],
  "20200101000000002": [
    "20200101000000003"
  ],
  "20200101000000003": [
    "20200101000000000"
  ]
})""")

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        with os.scandir(self.test_output) as entries:
            files = sorted(entries, key=lambda x: x.path)
        metas = []
        export_infos = []
        for file in files:
            with zipfile.ZipFile(file) as zh:
                with zh.open('meta.json') as fh:
                    metas.append(json.load(fh))
                with zh.open('export.json') as fh:
                    export_infos.append(json.load(fh))

        self.assertEqual(len(files), 7)

        # files are exported in depth-first order
        self.assertEqual(metas[0], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[0]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[1], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[1]['path'], [
            {'id': 'root', 'title': ''},
        ])
        self.assertEqual(export_infos[1]['id'], export_infos[0]['id'])

        self.assertEqual(metas[2], {
            'id': '20200101000000001',
            'type': 'folder',
            'title': 'item1',
        })
        self.assertEqual(export_infos[2]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[3], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[3]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000001', 'title': 'item1'},
        ])
        self.assertEqual(export_infos[3]['id'], export_infos[0]['id'])

        self.assertEqual(metas[4], {
            'id': '20200101000000002',
            'type': 'folder',
            'title': 'item2',
        })
        self.assertEqual(export_infos[4]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[5], {
            'id': '20200101000000003',
            'type': 'folder',
            'title': 'item3',
        })
        self.assertEqual(export_infos[5]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000002', 'title': 'item2'},
        ])

        self.assertEqual(metas[6], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[6]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000002', 'title': 'item2'},
            {'id': '20200101000000003', 'title': 'item3'},
        ])
        self.assertEqual(export_infos[6]['id'], export_infos[0]['id'])

    def test_toc05(self):
        """Export first occurrence if singleton"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder",
    "title": "item0"
  },
  "20200101000000001": {
    "type": "folder",
    "title": "item1"
  },
  "20200101000000002": {
    "type": "folder",
    "title": "item2"
  },
  "20200101000000003": {
    "type": "folder",
    "title": "item3"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000",
    "20200101000000000",
    "20200101000000001",
    "20200101000000002"
  ],
  "20200101000000001": [
    "20200101000000000"
  ],
  "20200101000000002": [
    "20200101000000003"
  ],
  "20200101000000003": [
    "20200101000000000"
  ]
})""")

        for _info in wsb_exporter.run(self.test_input, self.test_output, singleton=True):
            pass

        with os.scandir(self.test_output) as entries:
            files = sorted(entries, key=lambda x: x.path)
        metas = []
        export_infos = []
        for file in files:
            with zipfile.ZipFile(file) as zh:
                with zh.open('meta.json') as fh:
                    metas.append(json.load(fh))
                with zh.open('export.json') as fh:
                    export_infos.append(json.load(fh))

        self.assertEqual(len(files), 4)

        # files are exported in depth-first order
        self.assertEqual(metas[0], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[0]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[1], {
            'id': '20200101000000001',
            'type': 'folder',
            'title': 'item1',
        })
        self.assertEqual(export_infos[1]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[2], {
            'id': '20200101000000002',
            'type': 'folder',
            'title': 'item2',
        })
        self.assertEqual(export_infos[2]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[3], {
            'id': '20200101000000003',
            'type': 'folder',
            'title': 'item3',
        })
        self.assertEqual(export_infos[3]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000002', 'title': 'item2'},
        ])

    def test_toc06(self):
        """Export circular item but no children"""
        with open(self.test_input_meta, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.meta({
  "20200101000000000": {
    "type": "folder",
    "title": "item0"
  },
  "20200101000000001": {
    "type": "folder",
    "title": "item1"
  }
})""")
        with open(self.test_input_toc, 'w', encoding='UTF-8') as fh:
            fh.write("""\
scrapbook.toc({
  "root": [
    "20200101000000000"
  ],
  "20200101000000000": [
    "20200101000000001"
  ],
  "20200101000000001": [
    "20200101000000000"
  ]
})""")

        for _info in wsb_exporter.run(self.test_input, self.test_output):
            pass

        with os.scandir(self.test_output) as entries:
            files = sorted(entries, key=lambda x: x.path)
        metas = []
        export_infos = []
        for file in files:
            with zipfile.ZipFile(file) as zh:
                with zh.open('meta.json') as fh:
                    metas.append(json.load(fh))
                with zh.open('export.json') as fh:
                    export_infos.append(json.load(fh))

        self.assertEqual(len(files), 3)

        # files are exported in depth-first order
        self.assertEqual(metas[0], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[0]['path'], [
            {'id': 'root', 'title': ''},
        ])

        self.assertEqual(metas[1], {
            'id': '20200101000000001',
            'type': 'folder',
            'title': 'item1',
        })
        self.assertEqual(export_infos[1]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000000', 'title': 'item0'},
        ])

        self.assertEqual(metas[2], {
            'id': '20200101000000000',
            'type': 'folder',
            'title': 'item0',
        })
        self.assertEqual(export_infos[2]['path'], [
            {'id': 'root', 'title': ''},
            {'id': '20200101000000000', 'title': 'item0'},
            {'id': '20200101000000001', 'title': 'item1'},
        ])
        self.assertEqual(export_infos[2]['id'], export_infos[0]['id'])


if __name__ == '__main__':
    unittest.main()
