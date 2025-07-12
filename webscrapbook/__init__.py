"""Shared constants and configs.
"""
__version__ = '2.6.1'
__all__ = ['WSB_EXTENSION_MIN_VERSION', 'WSB_USER_DIR', 'WSB_USER_CONFIG', 'WSB_DIR', 'WSB_CONFIG', 'config']

import os
import re
from collections import OrderedDict
from configparser import ConfigParser
from copy import deepcopy

WSB_EXTENSION_MIN_VERSION = '2.20.0'
WSB_USER_DIR = os.environ.get('WSB_USER_DIR') or '.config/wsb'
WSB_USER_CONFIG = os.environ.get('WSB_USER_CONFIG') or '.wsbconfig'
WSB_DIR = os.environ.get('WSB_DIR') or '.wsb'
WSB_CONFIG = os.environ.get('WSB_CONFIG') or 'config.ini'


class Config():
    """Config class whose values are lazily-initialized when accessed.

    Values are loaded from config files relative to CWD. Consider calling
    load() if the script changes CWD during the runtime.
    """
    DEFAULT = {
        'app': {
            'name': 'WebScrapBook',
            'theme': 'default',
            'locale': '',
            'root': '.',
            'index': '',
            'backup_dir': '.wsb/backup',
            'content_security_policy': 'strict',
            'allowed_x_for': '0',
            'allowed_x_proto': '0',
            'allowed_x_host': '0',
            'allowed_x_port': '0',
            'allowed_x_prefix': '0',
        },
        'server': {
            'port': '8080',
            'host': 'localhost',
            'ssl_on': 'false',
            'ssl_key': '',
            'ssl_cert': '',
            'ssl_pw': '',
            'browse': 'false',
        },
        'browser': {
            'command': '',
            'cache_prefix': 'webscrapbook.',
            'cache_expire': '259200',
            'use_jar': 'false',
        },
        'book ""': {
            'name': 'scrapbook',
            'top_dir': '',
            'data_dir': '',
            'tree_dir': '.wsb/tree',
            'index': '.wsb/tree/map.html',
            'no_tree': 'false',
            'new_at_top': 'false',
            'inclusive_frames': 'true',
            'static_index': 'false',
            'rss_root': '',
            'rss_item_count': '50',
        },
    }
    TYPES = {
        'app': {
            'allowed_x_for': 'getint',
            'allowed_x_proto': 'getint',
            'allowed_x_host': 'getint',
            'allowed_x_port': 'getint',
            'allowed_x_prefix': 'getint',
        },
        'server': {
            'port': 'getint',
            'ssl_on': 'getboolean',
            'browse': 'getboolean',
        },
        'browser': {
            'cache_expire': 'getint',
            'use_jar': 'getboolean',
        },
        'book': {
            None: {
                'no_tree': 'getboolean',
                'new_at_top': 'getboolean',
                'inclusive_frames': 'getboolean',
                'static_index': 'getboolean',
                'rss_item_count': 'getint',
            },
        },
    }
    SUBSECTED = ['book', 'auth']

    def __init__(self):
        self._conf = None
        self._data = None

    def __getitem__(self, key):
        if self._conf is None: self.load()  # lazy load  # noqa: E701
        return self._data[key]

    def __iter__(self):
        if self._conf is None: self.load()  # lazy load  # noqa: E701
        return iter(self._data)

    @staticmethod
    def user_config_dir():
        return os.path.normpath(os.path.join(os.path.expanduser('~'), WSB_USER_DIR))

    @staticmethod
    def user_config():
        return os.path.normpath(os.path.join(os.path.expanduser('~'), WSB_USER_CONFIG))

    def getname(self, name):
        if self._conf is None: self.load()  # lazy load  # noqa: E701
        parts = name.split('.')
        if len(parts) == 3:
            sec, subsec, key = parts
            try:
                return self._conf[f'{sec} "{subsec}"'][key]
            except KeyError:
                pass
        elif len(parts) == 2:
            sec, key = parts
            try:
                return self._conf[sec][key]
            except KeyError:
                pass
        return None

    def dump(self, fh):
        if self._conf is None: self.load()  # lazy load  # noqa: E701
        self._conf.write(fh)

    def dump_object(self):
        """Dump configs as an object, with type casting.
        """
        if self._conf is None: self.load()  # lazy load  # noqa: E701
        return deepcopy(self._data)

    def load(self, root='.'):
        """Loads config files related to the given root directory.

        Skip if config file doesn't exist, but raise if not loadable.

        project config > user config > default config
        """
        # default config
        self._conf = conf = ConfigParser(interpolation=None)
        conf.read_dict(self.DEFAULT)

        # user config
        self._load_config(os.path.join(self.user_config_dir(), WSB_CONFIG), conf)
        self._load_config(self.user_config(), conf)

        # book config
        self._load_config(os.path.join(root, WSB_DIR, WSB_CONFIG), conf)

        # map subsections
        self._data = OrderedDict()
        for section in conf.sections():
            sectionobj = OrderedDict()
            m = re.search(r'^(\S*)(?:\s*"([^"\]]*)"\s*)?$', section)
            if m:
                sec, subsec = m.group(1), m.group(2) or ''
                if sec in self.SUBSECTED:
                    self._data.setdefault(sec, OrderedDict())[subsec] = sectionobj
                    for key in conf[section]:
                        try:
                            sectionobj[key] = getattr(conf[section], self.TYPES[sec][None][key])(key)
                        except KeyError:
                            sectionobj[key] = conf[section][key]
                    continue
            self._data[section] = sectionobj
            for key in conf[section]:
                try:
                    sectionobj[key] = getattr(conf[section], self.TYPES[section][key])(key)
                except KeyError:
                    sectionobj[key] = conf[section][key]

    @classmethod
    def _load_config(cls, file, conf):
        if not os.path.isfile(file):
            return

        parser = ConfigParser(interpolation=None)
        try:
            parser.read(file, encoding='UTF-8')
        except Exception as exc:
            raise RuntimeError(f'Unable to load config from {file!r}') from exc

        for section in parser.sections():
            # Handle subsected sections formatted as [section "subsection"].
            # Also normalize [section] and [section  ""  ] to [section ""].
            m = re.search(r'^(\S*)(?:\s*"([^"\]]*)"\s*)?$', section)
            if m:
                sec, subsec = m.group(1), m.group(2) or ''
                if sec in cls.SUBSECTED:
                    newsection = f'{sec} "{subsec}"'
                    conf.setdefault(newsection, cls.DEFAULT.get(f'{sec} ""', OrderedDict()))
                    conf[newsection].update(parser[section])
                    continue

            # conf.setdefault(...).update(...) doesn't work here as the
            # setdefault may return the default value rather then a
            # Section object.
            conf.setdefault(section, OrderedDict())
            conf[section].update(parser[section])


config = Config()
