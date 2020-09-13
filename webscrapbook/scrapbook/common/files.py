import os, json
from collections import OrderedDict
from .util import (
    remove_prefix,
    remove_suffix,
    remove_lines,
    parse_json,
    Memoize
)

FILE_COMMENT = "/** \n * Feel free to edit this file, but keep data code valid JSON format.\n */\n"
TOC_PREFIX   = "scrapbook.toc("
META_PREFIX  = "scrapbook.meta("
TOC_SUFFIX   = ")"
META_SUFFIX  = TOC_SUFFIX

@Memoize
def _toc_filepath():
    # TODO: get filepath
    return './tree/toc.js'

@Memoize
def _meta_filepath():
    # TODO: get filepath
    return './tree/meta.js'

def writeToc(toc: dict):
    def backupToc():
    # TODO: improve backup
        try:
            os.rename(_toc_filepath(), _toc_filepath() + '.bak')
        except:
            raise Exception('Could not backup ' + _toc_filepath() + ' before writing')

    def writeNewToc(toc):
        def toc_preprocessing(toc):
            return FILE_COMMENT + TOC_PREFIX + json.dumps(toc) + TOC_SUFFIX
        with open(_toc_filepath(), "w") as file:
            file.write(
                toc_preprocessing(json.dumps(toc))
            )
  
    backupToc()
    writeNewToc(toc)


# Toc and Metadata
###############################################################################
# Singleton classes to get toc.js and meta.js contents
# to get table of contents or metadata: Toc(), Metadata()

def _json_preprocessing(comment_lines, prefix, suffix):
    return lambda string: remove_suffix(
                            remove_prefix(
                                remove_lines(string, comment_lines), prefix), suffix)

class Toc(OrderedDict):
  @staticmethod
  def loadToc():
    return parse_json(_toc_filepath(),
                        _json_preprocessing(3, TOC_PREFIX, TOC_SUFFIX))

  _instance = None
  def __new__(cls):
      if cls._instance is None:
          cls._instance = OrderedDict(cls.loadToc())
      return cls._instance


class Metadata(OrderedDict):
  @staticmethod
  def loadMetadata():
    return parse_json(_meta_filepath(),
                        _json_preprocessing(3, META_PREFIX, META_SUFFIX))

  _instance = None
  def __new__(cls):
      if cls._instance is None:
          cls._instance = OrderedDict(cls.loadMetadata())
      return cls._instance