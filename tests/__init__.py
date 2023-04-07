import glob
import os
import tempfile
from contextlib import contextmanager

import webscrapbook

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

PROG_DIR = os.path.abspath(os.path.dirname(webscrapbook.__file__))

# The root directory for placing temp directories and files.
# None for auto-detection from the local system.
TEMP_DIR = None

DUMMY_BYTES = 'Lorem ipsum dolor sit amet 崽芺穵縡葥螑扤一鈜珽凈竻氻衶乇'.encode('UTF-8')
DUMMY_BYTES1 = 'Duis aute irure dolor 傜帙伔鮈鳭魻邘一崷絊珖旽忉俉屮'.encode('UTF-8')
DUMMY_BYTES2 = 'Quisque quis maximus dui. 毌狴极脞洝爣滒鉡邔扥垵犽炂妺庉瘃丌秅僔跬。'.encode('UTF-8')
DUMMY_BYTES3 = ('Proin porta ante tortor, dapibus venenatis sem volutpat vel. '
                '梊佫朸縟蛵錂邗一堥婃戙咇屳昴乇，滉揘兀杶秖楱呯氕屮佷綧柊仂芺。').encode('UTF-8')
DUMMY_BYTES4 = ('Proin porta ante tortor, dapibus venenatis sem volutpat vel.'
                'Donec imperdiet rutrum tellus, nec scelerisque turpis finibus id.'
                'In suscipit imperdiet eros ac interdum. Nullam porttitor vestibulum ultrices.'
                '梊佫朸縟蛵錂邗一堥婃戙咇屳昴乇，滉揘兀杶秖楱呯氕屮佷綧柊仂芺。'
                '稂侄仵諤溠糑匟一菆崌浯玠肊洼乇，嵊裋屮迕勀戣岤仜亍玤滫峗尐沴。'
                '烺一柶粘崵溡乇碤澯旡，捰乜玸惃愓溙乇榞旡宄。').encode('UTF-8')


# lazy global attributes
def __getattr__(name):
    if name == 'SYMLINK_SUPPORTED':
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.symlink(__file__, os.path.join(tmpdir, 'temp.link'))
            except OSError:
                value = False
            else:
                value = True

        globals()['SYMLINK_SUPPORTED'] = value
        return value

    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


@contextmanager
def test_file_cleanup(*paths):
    """Call os.remove() afterwards for given paths.

    - Mainly to prevent tree cleanup issue for junctions in Python 3.7
    """
    try:
        yield
    finally:
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass


def glob_files(path):
    """Get a set of files and directories under the path (inclusive).

    - Note that the path itself in the glob result will be appended an os.sep,
      and shuould usually be matched with os.path.join(path, '')
    - Hidden ('.'-leading) files are not included unless include_hidden=True,
      which is supported since Python 3.11, is provided to glob.

    Returns:
        set: files and directories under the path (inclusive)
    """
    return {*glob.iglob(os.path.join(glob.escape(path), '**'), recursive=True)}
