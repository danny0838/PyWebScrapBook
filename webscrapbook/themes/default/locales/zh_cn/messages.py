bidi_dir = 'ltr'


#########################################################################
# scrapbook.cache
#########################################################################

# map.html
cache_index_toggle_all = '全部展开或收合'
cache_index_search_link_title = '搜索'
cache_index_source_link_title = '来源链接'

# search.html
cache_search_title = '%book% :: 搜索'
cache_search_view_in_map = '在索引页中检视'
cache_search_start = '查'
cache_search_help_label = '搜索语法说明'
cache_search_help_desc = """\
• 输入的关键词会在标题、内文、评注中查找。
• 可用半形空白分隔要检索的多个关键词。例如“w3c organization”表示搜索含有“w3c”及“organization”的项目 。
• 可用半形双引号检索完整关键词，若关键词包含半形双引号，可用连续两个半形双引号表示。例如“"Tom ""loves"" Mary."”表示搜索含有“Tom "loves" Mary.”的项目。
• 可用负号排除关键词。例如“-virus”表示搜索不含“virus”的项目。
• 可用“<命令>:<关键词>”指定特殊的检索条件，命令前可加负号表示排除或反向。可用命令如下：
  • mc：之后的关键词皆比对大小写。加负号则反之。例如“mc: CIA FBI -mc: president”表示搜索含有区分大小写的“CIA”、“FBI”及不分大小写的“president”的项目。
  • re：之后的关键词皆视为正则表达式。加负号则反之。例如“re: \\bcolou?r\\b -re: 1+1=2”表示搜索匹配正则表达式“\\bcolou?r\\b”且含有关键词“1+1=2”的项目。
  • id：搜索 ID 等同关键词（或与正则表达式匹配）的项目。多次指定时以“或”连接。例如“id:2020 id:2021”表示搜索 ID 为“2020”或“2021”的项目；“-id:2020”表示搜索 ID 不为“2020”的项目。
  • type：搜索类型等同关键词（或与正则表达式匹配）的项目。多次指定时以“或”连接。可用的类型有“”（网页）、“bookmark”（书签）、“file”（档案）、“note”（笔记）等等。例如“type: type:bookmark”表示搜索类型为网页或书签的项目。
  • title：搜索标题含有关键词的项目。
  • content：搜索全文含有关键词的项目。
  • comment：搜索评注含有关键词的项目。
  • tcc：搜索标题、全文或评注含有关键词的项目。
  • file：搜索档名含有关键词的项目。
  • root：搜索此 ID 项目下的子项目。多次指定时以“或”连接。
  • book：搜索指定剪贴簿（依名称）中的项目。多次指定时以“或”连接。
  • source：搜索原始网址含有关键词的项目。
  • icon：搜索图示网址含有关键词的项目。
  • create：搜索建立时间符合条件的项目。时间格式为 0-17 位数字，后面接负号（可略），再接 0-17 位数字。省略的部分自动补 0，但后面的时间全省略时补 9（即无限大）。例如“create:2014-2015”表示 20140000000000000 到 20150000000000000，“create:-201309”表示 00000000000000000 到 20130900000000000，“create:20110825”表示 20110825000000000 到 99999999999999999。
  • modify：搜索修改时间符合条件的项目。时间格式同 create。
  • marked：搜索强调标示的项目。
  • locked：搜索锁定的项目。
  • sort：将搜索结果按指定方式排序，负号表示倒序。可填入 id、title、comment、content、source、type、create、modify。例如“sort:id -sort:modify”表示先按 ID 递增排序再按修改时间递减排序。"""
cache_search_result = '找到 %length% 笔结果：'
cache_search_result_named = '(%name%) 找到 %length% 笔结果：'
cache_search_sort_last_created = '最后创建'
cache_search_sort_last_modified = '最后修改'
cache_search_sort_title = '标题排序'
cache_search_sort_id = 'ID 排序'
