bidi_dir = 'ltr'


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
• Input keywords search from title, content, or comment.
• Use space to separate multiple keywords. For example, “w3c organization” means items containing “w3c” and “organization”.
• Use double quotes to demark a complete phrase, a literal double quote can be escaped by doubling. For example, “"Tom ""loves"" Mary."” means items containing “Tom "loves" Mary.”
• Use minus sign to exclude a keyword. For example, “-virus” means items without “virus”.
• Use “<command>:<keyword>” to specify a special search condition. A minus sign can be prefixed for exclusion or reversion. Available commands include:
  • mc: each subsequent keyword matches case-sensitively. For example, “mc: CIA FBI -mc: president” means items containing “CIA” and “FBI” case-sensitively, and “president” case-insensitively.
  • re: each subsequent keyword is treated as a regular expression. For example, “re: \\bcolou?r\\b -re: 1+1=2” means items that match regular expression “\\bcolou?r\\b” and contain keyword “1+1=2”.
  • id: item whose ID equal to the keyword (or match the regular expression). Multiple values are “or”-connected. For example, “id:2020 id:2021” means items of ID “2020” or “2021”; “-id:2020” means items whose ID is not “2020”.
  • type: items whose type equal to the keyword (or match the regular expression). Multiple values are “or”-connected. Available types are “” (page), “bookmark”, “file”, “note”, etc. For example, “type: type:bookmark” means items whose type is page or bookmark.
  • title: items whose title contains the keyword.
  • content: items whose fulltext contains the keyword.
  • comment: items whose comment contains the keyword.
  • tcc: items whose title, fulltext, or comment contains the keyword.
  • index: items whose index file path contains the keyword.
  • source: items whose source URL contains the keyword.
  • icon: items whose icon URL contains the keyword.
  • create: items whose create time matches the condition. The time condition is an interval with 0-17 digits, followed by a minus sign optionally, and then followed by 0-17 digits. The two 17-digit numbers means the year (4 digits), month (01-12), day (01-31), hours (00-59), minutes (00-59), seconds (00-59), and milliseconds (000-999) in local datetime. Each omitted digit is assumed to be a “0”, except that “999...” is assumed if the end datetime is totally omitted. For example, “create:2014-2015” means since 2014 until 2015; “create:-201309” means before Sep 2013; and “create:20110825” means after Aug 25, 2011.
  • modify: items whose modify time matches the condition. Time format is same as create.
  • marked: marked items.
  • locked: locked items.
  • file: items whose filename contains the keyword.
  • root: items under the item of ID. Multiple values are “or”-connected.
  • book: items in the specific scrapbook (by name). Multiple values are “or”-connected.
  • sort: sort search results using the specific condition, which can be id, title, comment, content, source, type, create, or modify. For example, “sort:id -sort:modify” means sorting by ID in acending order and then sorting by modify time in descending order."""
cache_search_result = 'Found %length% results:'
cache_search_result_named = '(%name%) Found %length% results:'
cache_search_sort_last_created = 'Last Created'
cache_search_sort_last_modified = 'Last Modified'
cache_search_sort_title = 'Sort by title'
cache_search_sort_id = 'Sort by ID'
