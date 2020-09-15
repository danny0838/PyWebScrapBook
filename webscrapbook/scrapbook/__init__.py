from webscrapbook.scrapbook.sort import sort

def sort_operation(directory, id_val, sort_key, sort_direction, recursive):
    s = sort.Sort(directory)
    s.sort_folder(id_val, sort_key, sort_direction, recursive)