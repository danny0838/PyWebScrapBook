import json

# string functions
###############################################################################

def remove_prefix(text, prefix):
  if text.startswith(prefix):
        return text[len(prefix):]
  return text

def remove_suffix(text, suffix):
  if text.endswith(suffix):
        return text[:-1 * len(suffix)]
  return text

def remove_lines(s, count):
  s = s.split('\n', count)[-1]
  return s

def parse_json(filename, preprocessing):
  data = {}
  with open(filename) as file:
    json_string = preprocessing(file.read())
    try:
      data = json.loads(json_string)
    except:
      # TODO: add failure handling
      pass
  return data

###############################################################################

class Memoize:
# decorator function
    def __init__(self, fn):
        self.fn = fn
        self.memo = {}

    def __call__(self, *args):
        if args not in self.memo:
            self.memo[args] = self.fn(*args)
        return self.memo[args]