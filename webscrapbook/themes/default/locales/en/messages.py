bidi_dir = 'ltr'
html_lang = 'en'

index_title = 'Index of {path}'

data_table_header_directory = 'Directory'
data_table_header_name = 'Name'
data_table_header_last_modified = 'Last modified'
data_table_header_size = 'Size'

explorer_tooltip = 'View mode [{}]'
explorer_table = 'Table view'
explorer_gallery = 'Gallery view'
explorer_gallery2 = 'Gallery view (+media)'

tools_tooltip = 'Tools [{}]'
tools_preview_on = 'Enable preview'
tools_preview_off = 'Disable preview'
tools_select_all = 'Select all'
tools_deselect_all = 'Deselect all'
tools_expand_all = 'Expand all'
tools_filter = 'Filter'
tools_filter_clear = 'Clear filter'

tools_filter_prompt = 'Filter with the keyword (string or "/pattern/flags" for regex):'

command_tooltip = 'Commands [{}]'
command_mkdir = 'New folder'
command_mkzip = 'New zip'
command_mkfile = 'New file'
command_upload = 'Upload'
command_uploaddir = 'Upload folder'
command_source = 'View source'
command_download = 'Download'
command_exec = 'Run natively'
command_browse = 'Browse natively'
command_edit = 'Edit'
command_editx = 'Edit page'
command_move = 'Move'
command_copy = 'Copy'
command_link = 'Create link'
command_delete = 'Delete'

command_mkdir_prompt = 'Create a new folder with name:'
command_mkdir_default = 'new-folder'
command_mkzip_prompt = 'Create a ZIP file with name:'
command_mkzip_default = 'new-archive.zip'
command_mkfile_prompt = 'Create a file with name:'
command_mkfile_default = 'new-file.txt'
command_move_prompt = 'Move to the path or folder:'
command_move_prompt_multi = 'Move to the folder:'
command_copy_prompt = 'Copy to the path or folder:'
command_copy_prompt_multi = 'Copy to the folder:'
command_link_prompt = 'Create a link at the path or under the folder:'
command_link_prompt_multi = 'Create links under the folder:'

label_selected = '%count% selected'

previewer_toolbar_title = """\
Keybord shortcuts:
• [Esc]: close preview.
• [I] or [Space]: toggle infobar.
• [Enter]: open in new tab.
• [PageUp] or [Alt+←] or [←]: show previous entry.
• [PageDown] or [Alt+→] or [→]: show next entry.
• [Home]: show first entry.
• [End]: show last entry.
• [+] or [Alt+↑] or [↑]: zoom in.
• [-] or [Alt+↓] or [↓]: zoom out.
• [Ctrl+0]: zoom fit viewport.
• [Ctrl+1]: zoom between natural size and last zoom size.
• [Ctrl+←] or [Shift+←]: move left.
• [Ctrl+→] or [Shift+→]: move right.
• [Ctrl+↑] or [Shift+↑]: move up.
• [Ctrl+↓] or [Shift+↓]: move down.
"""
previewer_button_previous = 'Previous'
previewer_button_next = 'Next'
previewer_button_infobar = 'Toggle infobar'
previewer_button_close = 'Close preview'

edit_title = 'Edit {path}'
edit_error_no_javascript = 'Enable JavaScript or upgrade your browser to support JavaScript, so that the HTML editor can work.'
edit_warning_encoding = 'This file is decoded as {encoding}, and will be encoded as UTF-8 when saved.'

markdown_title = 'Page {path}'
maff_index_title = 'Pages of {path}'

button_save = 'SAVE'
button_save_tooltip = 'Save [{}]'
button_exit = 'EXIT'
button_exit_tooltip = 'Exit [{}]'


#########################################################################
# scrapbook.cache
#########################################################################

# map.html
cache_index_toggle_all = 'Toggle all'
cache_index_search_link_title = 'Search'
cache_index_source_link_title = 'Source link'

# search.html
cache_search_title = '%book% :: Search'
cache_search_view_in_map = 'View in map'
cache_search_start = 'go'
cache_search_help_label = 'Search syntax help'
cache_search_help_desc = """\
• By default the input keywords are searched from title, comment, or fulltext.
• Use space to separate multiple keywords. For example, “w3c organization” means items containing “w3c” and “organization”.
• Use double quotes to demark a complete phrase, a literal double quote can be escaped by doubling. For example, “"Tom ""loves"" Mary."” means items containing “Tom "loves" Mary.”
• Use minus sign to exclude a keyword. For example, “-virus” means items without “virus”.
• Use “<command>:<keyword>” to specify a special search condition. A minus sign can be prefixed for exclusion or reversion. Available commands include:
  • default: Reset the fields to search for any keyword without a commmand. The fields are separated with “,” and matching any of the fields is considered a hit. For example, “default:id,title,source,comment,content 2020” means items whose ID, title, source URL, comment, or fulltext contains “2020”. “-default:” remove fields from the current default fields, i.e., “default:title,comment -default:comment” works like “default:title”.
  • mc: each subsequent keyword matches case-sensitively. For example, “mc: CIA FBI -mc: president” means items containing “CIA” and “FBI” case-sensitively, and “president” case-insensitively.
  • re: each subsequent keyword is treated as a regular expression. For example, “re: \\bcolou?r\\b -re: 1+1=2” means items that match regular expression “\\bcolou?r\\b” and contain keyword “1+1=2”.
  • id: item whose ID equal to the keyword (or match the regular expression). Multiple values are “or”-connected. For example, “id:2020 id:2021” means items of ID “2020” or “2021”; “-id:2020” means items whose ID is not “2020”.
  • type: items whose type equal to the keyword (or match the regular expression). Multiple values are “or”-connected. Available types are “” (page), “bookmark”, “file”, “note”, etc. For example, “type: type:bookmark” means items whose type is page or bookmark.
  • title: items whose title contains the keyword.
  • content: items whose fulltext contains the keyword.
  • comment: items whose comment contains the keyword.
  • index: items whose index file path contains the keyword.
  • source: items whose source URL contains the keyword.
  • icon: items whose icon URL contains the keyword.
  • charset: items whose charset contains the keyword.
  • create: items whose create time matches the condition. Multiple values are “or”-connected. The time condition is an interval with 0-17 digits, followed by a minus sign optionally, and then followed by 0-17 digits. The two 17-digit numbers means the year (4 digits), month (01-12), day (01-31), hours (00-59), minutes (00-59), seconds (00-59), and milliseconds (000-999) in local datetime. Each omitted digit is assumed to be a “0”, except that “999...” is assumed if the end datetime is totally omitted. For example, “create:2014-2015” means since 2014 until 2015; “create:-201309” means before Sep 2013; and “create:20110825” means after Aug 25, 2011.
  • modify: items whose modify time matches the condition. Multiple values are “or”-connected. Time format is same as create.
  • marked: marked items.
  • locked: locked items.
  • location: items with geolocation information.
  • file: items whose filename contains the keyword.
  • root: items under the item of ID. Multiple values are “or”-connected.
  • book: items in the specific scrapbook (by ID). Multiple values are “or”-connected.
  • sort: sort search results using the specific condition, which can be id, title, comment, file, content, source, type, create, or modify. For example, “sort:id -sort:modify” means sorting by ID in acending order and then sorting by modify time in descending order.
  • limit: set a limit on the search result number. For example, “limit:10” means showing the first 10 results. “-limit:” means unsetting the limit."""
cache_search_result = 'Found %length% results:'
cache_search_result_named = '(%name%) Found %length% results:'
cache_search_sort_last_created = 'Last Created'
cache_search_sort_last_modified = 'Last Modified'
cache_search_sort_title = 'Sort by title'
cache_search_sort_id = 'Sort by ID'
cache_search_confirm_remote = 'Loading remote fulltext cache may require large network flow. Continue?'


#########################################################################
# WebScrapBook
#########################################################################

EditorDeleteAnnotationConfirm = 'Delete this annotation?'
