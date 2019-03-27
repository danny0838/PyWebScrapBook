#!/usr/bin/env python3
"""A backend toolkit for management of WebScrapBook collection.
"""
import sys
import os
from configparser import ConfigParser
from collections import OrderedDict
import mimetypes
import re

__all__ = ['WSB_USER_CONFIG', 'WSB_DIR', 'WSB_LOCAL_CONFIG', 'config']

__package_name__ = 'webscrapbook'
__version__ = '0.2.1'
__author__ = 'Danny Lin'
__author_email__ = 'danny0838@gmail.com'
__homepage__ = 'https://github.com/danny0838/PyWebScrapBook'
__license__ = 'MIT'

WSB_USER_CONFIG = os.path.join(os.path.expanduser('~'), '.wsbconfig')
WSB_DIR = '.wsb'
WSB_LOCAL_CONFIG = 'config.ini'

mimetypes.add_type("text/markdown", ".md")
mimetypes.add_type("text/markdown", ".markdown")
mimetypes.add_type("application/html+zip", ".htz")
mimetypes.add_type("application/x-maff", ".maff")


class Config():
    """Config class whose values are lazily-initialized when accessed.

    Values are loaded from config files relative to CWD. Consider calling
    load() if the script changes CWD during the runtime.
    """
    def __init__(self):
        self._conf = None


    def __getitem__(self, key):
        if self._conf is None: self.load()  # lazy load
        return self._conf[key]


    @property
    def book(self):
        if self._conf is None: self.load()  # lazy load
        return self._book


    @property
    def auth(self):
        if self._conf is None: self.load()  # lazy load
        return self._auth


    def dump(self, fh):
        if self._conf is None: self.load()  # lazy load
        self._conf.write(fh)


    def dump_object(self):
        """Dump configs as an object, with type casting.
        """
        if self._conf is None: self.load()  # lazy load

        data = OrderedDict()
        for section in self._conf.sections():
            # remove [section "subsection"]
            if re.search(r'\s+"[^"]*"$', section):
                continue

            data[section] = OrderedDict()
            for key in self._conf[section]:
                data[section][key] = self._conf[section][key]

        # type casting
        data['server']['port'] = self._conf['server'].getint('port')
        data['server']['ssl_on'] = self._conf['server'].getboolean('ssl_on')
        data['auth'] = self._auth
        data['browser']['launch'] = self._conf['browser'].getboolean('launch')
        data['browser']['new'] = self._conf['browser'].getint('new')
        data['browser']['top'] = self._conf['browser'].getboolean('top')
        data['book'] = self._book

        return data


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
                    if section not in conf:
                        conf[section] = {}
                    for key in parser[section]:
                        conf[section][key] = parser[section][key]
            except:
                print('Error: Unable to load config from "{}".'.format(file), file=sys.stderr)
                raise


        def parse_subsection(name):
            """Hanble subsection formatted as [section "subsection"].

            Also map [section] to [section ""].
            """
            data = OrderedDict()
            for section in conf:
                m = re.search(r'^' + name + r'(?:\s*"([^"\]]*)")?$', section)
                if not m: continue
                c = data.setdefault(m.group(1) or '', OrderedDict())
                for key in conf[section]:
                    c[key] = conf[section][key]
            return data


        # default config
        self._conf = conf = ConfigParser(interpolation=None)
        conf['app'] = {}
        conf['app']['name'] = 'WebScrapBook'
        conf['app']['theme'] = 'default'
        conf['app']['root'] = '.'
        conf['app']['base'] = ''
        conf['server'] = {}
        conf['server']['port'] = '8080'
        conf['server']['bind'] = '127.0.0.1'
        conf['server']['host'] = 'localhost'
        conf['server']['threads'] = '0'
        conf['server']['ssl_on'] = 'false'
        conf['server']['ssl_key'] = ''
        conf['server']['ssl_cert'] = ''
        conf['server']['ssl_pw'] = ''
        conf['server']['browse'] = 'true'
        conf['browser'] = {}
        conf['browser']['command'] = ''
        conf['browser']['new'] = '0'
        conf['browser']['top'] = 'false'
        conf['browser']['index'] = ''
        conf['book'] = {}
        conf['book']['name'] = 'scrapbook'
        conf['book']['top_dir'] = ''
        conf['book']['data_dir'] = ''
        conf['book']['tree_dir'] = '.wsb/tree'
        conf['book']['index'] = '.wsb/tree/map.html'

        # user config
        load_config(WSB_USER_CONFIG)

        # book config
        load_config(os.path.join(root, WSB_DIR, WSB_LOCAL_CONFIG))

        # handle subsections
        self._book = parse_subsection('book')
        self._auth = parse_subsection('auth')

config = Config()
