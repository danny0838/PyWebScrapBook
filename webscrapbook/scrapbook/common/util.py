import os, json, glob

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

def remove_lines(text, count):
    text = text.split('\n', count)[-1]
    return text

def parse_json(filename, preprocessing):
    data = {}
    with open(filename) as file:
        json_string = preprocessing(file.read())
        try:
            data = json.loads(json_string)
        except:
            # TODO: better handling
            raise Exception("Failed to parse json file " + filename)
    return data

###############################################################################


# filesystem functions
###############################################################################

def find_file(path, glob_val):
    ''' given a filepath, glob return a list of matching files 
    
        Parameters:
            path (str): path to directory containing file
            glob_val (str): a glob to match a filename
    '''
    file = os.path.join(path + glob_val)
    possible_files = glob.glob(file)
    return possible_files


# misc
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

class SimpleObject(object):
    ''' used to create a simple namespace object to dynamically add attributes to '''
    pass