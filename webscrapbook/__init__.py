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
__version__ = '0.11.0'
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
        self._subsections = OrderedDict()


    def __getitem__(self, key):
        if self._conf is None: self.load()  # lazy load
        return self._conf[key]


    @property
    def subsections(self):
        if self._conf is None: self.load()  # lazy load
        return self._subsections


    def get(self, name):
        if self._conf is None: self.load()  # lazy load
        parts = name.split('.')
        if len(parts) == 3:
            sec, subsec, key = parts
            try:
                return self.subsections[sec][subsec][key]
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

        data = OrderedDict()
        for section in self._conf.sections():
            # remove [section "subsection"]
            if re.search(r'\s*"[^"]*"\s*$', section):
                continue

            data[section] = OrderedDict(self._conf[section])

        for sec, section in self.subsections.items():
            for subsec, subsection in section.items():
                data.setdefault(sec, OrderedDict())[subsec] = OrderedDict(subsection)

        # type casting
        data['server']['port'] = self._conf['server'].getint('port')
        data['server']['threads'] = self._conf['server'].getint('threads')
        data['server']['ssl_on'] = self._conf['server'].getboolean('ssl_on')
        data['server']['browse'] = self._conf['server'].getboolean('browse')
        data['browser']['cache_expire'] = self._conf['browser'].getint('cache_expire')
        data['browser']['use_jar'] = self._conf['browser'].getboolean('use_jar')
        for ss in data['book']:
            data['book'][ss]['no_tree'] = self._conf['book "{}"'.format(ss)].getboolean('no_tree')

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
                    # Handle subsected sections formatted as [section "subsection"].
                    # Also normalize [section] and [section  ""  ] to [section ""].
                    m = re.search(r'^(\S*)(?:\s*"([^"\]]*)"\s*)?$', section)
                    if m:
                        sec, subsec = m.group(1), m.group(2) or ''
                        if sec in self.SUBSECTED:
                            newsection = '{} "{}"'.format(sec, subsec)
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
                print('Error: Unable to load config from "{}".'.format(file), file=sys.stderr)
                raise

        # default config
        self._conf = conf = ConfigParser(interpolation=None)
        conf['app'] = {}
        conf['app']['name'] = 'WebScrapBook'
        conf['app']['theme'] = 'default'
        conf['app']['root'] = '.'
        conf['app']['base'] = ''
        conf['server'] = {}
        conf['server']['port'] = '8080'
        conf['server']['host'] = 'localhost'
        conf['server']['threads'] = '0'
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
        for section in conf:
            m = re.search(r'^(\S*)(?:\s*"([^"\]]*)"\s*)?$', section)
            if m:
                sec, subsec = m.group(1), m.group(2) or ''
                if sec in self.SUBSECTED:
                    self._subsections.setdefault(sec, OrderedDict())[subsec] = conf[section]

    SUBSECTED = ['book', 'auth']

config = Config()
