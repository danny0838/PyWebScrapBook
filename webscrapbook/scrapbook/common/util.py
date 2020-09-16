import os, json, glob, re
from math import ceil
from collections import OrderedDict
from itertools import islice

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

def remove_lines(file, count):
    for _ in range(count):
        file.readline()

def parse_json(filepath, preprocessing):
    data = {}
    with open(filepath, encoding='UTF-8') as file:
        json_string = preprocessing(file)
        try:
            data = json.loads(json_string, object_pairs_hook=OrderedDict)
        except:
            # TODO: better handling
            raise Exception("Failed to parse json file " + filepath)
    return data

def get_number_suffix(text):
    ''' return the number at the end of a string if no number found return empty string '''
    return re.findall('([0-9]*$)', text)[0]

###############################################################################


# filesystem functions
###############################################################################

def add_directory_to_filename(directory, filename):
    return os.path.join(directory, filename)

def get_filename_no_ext(filepath):
    return os.path.splitext(os.path.basename(filepath))[0]

def find_file(directory, file_regex):
    ''' given a directory, regex return a list of matching files 
    
        Parameters:
            directory (str): directory containing files
            file_regex (str): a regex to match a filename
    '''
    files = os.listdir(directory)
    possible_files = [ add_directory_to_filename(directory, file) for file in files if re.match(file_regex, file)]
    return possible_files

def find_regex_file(directory, regex, no_match_message):
    ''' find all files matching regex '''
    possible_files = find_file(directory, regex)
    if not possible_files:
        raise Exception(no_match_message)
    else:
        return possible_files

def file_exists(directory, filename):
    return os.path.isfile(add_directory_to_filename(directory, filename))

def write_file(directory, filename, contents):
    with open(add_directory_to_filename(directory, filename), "w", encoding='UTF-8') as file:
        file.write(contents)

def delete_file(directory, filename):
    os.remove(add_directory_to_filename(directory, filename))

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

def merge_dictionaries(dictionaries):
    '''
        Merge top level keys of a list of dictionaries.
        Later dictionaries in the list will overwrite keys of earlier dictionaries.
        This merge is not recursive.
    '''
    dictionary = dict()
    for d in dictionaries:
        dictionary = { **dictionary , **d }
    return dictionary

def split_dictionary(dictionary, max_size):
    '''
        Split a single dictionary into many smaller sized dictionaries
        preserving key order.

        Parameters:
            max_size (int): max number of top level keys in any given split dictionary
    '''
    def slice_dictionary(dictionary, start, end):
        return OrderedDict(islice(dictionary.items(), start, end))

    num_splits = ceil(len(dictionary) / max_size)
    sliced = [ slice_dictionary(dictionary, max_size*i, max_size*(i+1)) for i in range(num_splits)]
    return sliced
