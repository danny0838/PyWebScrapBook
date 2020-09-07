#!/usr/bin/env python3
"""A backend toolkit for management of WebScrapBook collection.
"""
import sys
import os
from configparser import ConfigParser
from collections import OrderedDict
from copy import deepcopy
import mimetypes
import re

__all__ = ['WSB_EXTENSION_MIN_VERSION', 'WSB_USER_CONFIG', 'WSB_DIR', 'WSB_LOCAL_CONFIG', 'config']

__package_name__ = 'webscrapbook'
__version__ = '0.18.1'
__author__ = 'Danny Lin'
__author_email__ = 'danny0838@gmail.com'
__homepage__ = 'https://github.com/danny0838/PyWebScrapBook'
__license__ = 'MIT'

WSB_EXTENSION_MIN_VERSION = '0.75.6'
WSB_USER_CONFIG = os.environ.get('WSB_USER_CONFIG') or os.path.join(os.path.expanduser('~'), '.wsbconfig')
WSB_DIR = os.environ.get('WSB_DIR') or '.wsb'
WSB_LOCAL_CONFIG = os.environ.get('WSB_LOCAL_CONFIG') or 'config.ini'

mimetypes.add_type("application/rss+xml", ".rss")
mimetypes.add_type("application/atom+xml", ".atom")
mimetypes.add_type("text/markdown", ".md")
mimetypes.add_type("text/markdown", ".mkd")
mimetypes.add_type("text/markdown", ".mkdn")
mimetypes.add_type("text/markdown", ".mdwn")
mimetypes.add_type("text/markdown", ".mdown")
mimetypes.add_type("text/markdown", ".markdown")
mimetypes.add_type("application/html+zip", ".htz")
mimetypes.add_type("application/x-maff", ".maff")

# seems to be set to x-zip-compressed on Windows
mimetypes.add_type("application/zip", ".zip")


class Config():
    """Config class whose values are lazily-initialized when accessed.

    Values are loaded from config files relative to CWD. Consider calling
    load() if the script changes CWD during the runtime.
    """
    def __init__(self):
        self._conf = None
        self._data = None


    def __getitem__(self, key):
        if self._conf is None: self.load()  # lazy load
        return self._data[key]


    def __iter__(self):
        if self._conf is None: self.load()  # lazy load
        return iter(self._data)


    def getname(self, name):
        if self._conf is None: self.load()  # lazy load
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
        if self._conf is None: self.load()  # lazy load
        self._conf.write(fh)


    def dump_object(self):
        """Dump configs as an object, with type casting.
        """
        if self._conf is None: self.load()  # lazy load
        return deepcopy(self._data)


    def load(self, root='.'):
        """Loads config files related to the given root directory.

        Skip if config file doesn't exist, but raise if not loadable.

        project config > user config > default config
        """
        def load_config(file):
            if not os.path.isfile(file):
                return

            try:
                parser = ConfigParser(interpolation=None)
                parser.read(file, encoding='UTF-8')
                for section in parser.sections():
                    # Handle subsected sections formatted as [section "subsection"].
                    # Also normalize [section] and [section  ""  ] to [section ""].
                    m = re.search(r'^(\S*)(?:\s*"([^"\]]*)"\s*)?$', section)
                    if m:
                        sec, subsec = m.group(1), m.group(2) or ''
                        if sec in self.SUBSECTED:
                            newsection = f'{sec} "{subsec}"'
                            if newsection != section:
                                conf.setdefault(newsection, OrderedDict())
                                conf[newsection].update(parser[section])
                                continue

                    # conf.setdefault(...).update(...) doesn't work here as the
                    # setdefault may return the default value rather then a
                    # Section object.
                    conf.setdefault(section, OrderedDict())
                    conf[section].update(parser[section])
            except:
                print(f'Error: Unable to load config from "{file}".', file=sys.stderr)
                raise

        # default config
        self._conf = conf = ConfigParser(interpolation=None)
        conf['app'] = {}
        conf['app']['name'] = 'WebScrapBook'
        conf['app']['theme'] = 'default'
        conf['app']['root'] = '.'
        conf['app']['base'] = ''
        conf['app']['allowed_x_for'] = '0'
        conf['app']['allowed_x_proto'] = '0'
        conf['app']['allowed_x_host'] = '0'
        conf['app']['allowed_x_port'] = '0'
        conf['app']['allowed_x_prefix'] = '0'
        conf['server'] = {}
        conf['server']['port'] = '8080'
        conf['server']['host'] = 'localhost'
        conf['server']['ssl_on'] = 'false'
        conf['server']['ssl_key'] = ''
        conf['server']['ssl_cert'] = ''
        conf['server']['ssl_pw'] = ''
        conf['server']['browse'] = 'true'
        conf['browser'] = {}
        conf['browser']['command'] = ''
        conf['browser']['index'] = ''
        conf['browser']['cache_prefix'] = 'webscrapbook.'
        conf['browser']['cache_expire'] = '259200'
        conf['browser']['use_jar'] = 'false'
        conf['book ""'] = {}
        conf['book ""']['name'] = 'scrapbook'
        conf['book ""']['top_dir'] = ''
        conf['book ""']['data_dir'] = ''
        conf['book ""']['tree_dir'] = '.wsb/tree'
        conf['book ""']['index'] = '.wsb/tree/map.html'
        conf['book ""']['no_tree'] = 'false'

        # user config
        load_config(WSB_USER_CONFIG)

        # book config
        load_config(os.path.join(root, WSB_DIR, WSB_LOCAL_CONFIG))

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

    SUBSECTED = ['book', 'auth']
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
                },
            },
        }

config = Config()
