bidi_dir = 'ltr'
html_lang = 'zh-Hans-CN'

index_title = '索引于 {path}'

data_table_header_directory = '文件夹'
data_table_header_name = '文件名'
data_table_header_last_modified = '最后修改'
data_table_header_size = '大小'

explorer_tooltip = '检视模式 [{}]'
explorer_table = '表格检视'
explorer_gallery = '图示检视'
explorer_gallery2 = '图示检视 (+多媒体)'

tools_tooltip = '工具 [{}]'
tools_preview_on = '启用预览'
tools_preview_off = '停用预览'
tools_select_all = '全选'
tools_deselect_all = '取消全选'
tools_expand_all = '展开所有项目'
tools_filter = '筛选'
tools_filter_clear = '清除筛选'

tools_filter_prompt = '用关键词筛选（字符串或用“/表达式/标帜”表示正则表达式）:'

command_tooltip = '命令 [{}]'
command_mkdir = '新文件夹'
command_mkzip = '新压缩文件'
command_mkfile = '新文件'
command_upload = '上传'
command_uploaddir = '上传文件夹'
command_source = '检视源代码'
command_download = '下载'
command_exec = '本地执行'
command_browse = '本地检视'
command_edit = '编辑'
command_editx = '编辑页面'
command_move = '移动'
command_copy = '复制'
command_link = '建立链接'
command_delete = '删除'

command_mkdir_prompt = '创建新文件夹并命名为:'
command_mkdir_default = 'new-folder'
command_mkzip_prompt = '创建 ZIP 压缩文件并命名为:'
command_mkzip_default = 'new-archive.zip'
command_mkfile_prompt = '创建文件并命名为:'
command_mkfile_default = 'new-file.txt'
command_move_prompt = '移动至此路径或文件夹:'
command_move_prompt_multi = '移动至此文件夹:'
command_copy_prompt = '复制至此路径或文件夹:'
command_copy_prompt_multi = '复制至此文件夹:'
command_link_prompt = '建立链接于此路径或文件夹:'
command_link_prompt_multi = '建立链接于此文件夹:'

label_selected = '已选择 %count% 项'

previewer_toolbar_title = """\
键盘快捷键:
• [Esc]: 关闭预览。
• [I] 或 [Space]: 切换信息栏。
• [Enter]: 在新分页开启。
• [PageUp] 或 [Alt+←] 或 [←]: 显示上一项。
• [PageDown] 或 [Alt+→] 或 [→]: 显示下一项。
• [Home]: 显示第一项。
• [End]: 显示最后一项。
• [+] 或 [Alt+↑] 或 [↑]: 放大。
• [-] 或 [Alt+↓] 或 [↓]: 缩小。
• [Ctrl+0]: 缩放至符合可视范围。
• [Ctrl+1]: 切换缩放为图片大小与最后缩放大小。
• [Ctrl+←] 或 [Shift+←]: 左移。
• [Ctrl+→] 或 [Shift+→]: 右移。
• [Ctrl+↑] 或 [Shift+↑]: 上移。
• [Ctrl+↓] 或 [Shift+↓]: 下移。
"""
previewer_button_previous = '上一项'
previewer_button_next = '下一项'
previewer_button_infobar = '切换信息栏'
previewer_button_close = '关闭预览'

edit_title = '编辑 {path}'
edit_error_no_javascript = '启用 JavaScript 或升级浏览器以支援 JavaScript，此 HTML 编辑器才能正常运作。'
edit_warning_encoding = '此文件以 {encoding} 解码，保存时将编码为 UTF-8。'

markdown_title = '页面 {path}'
maff_index_title = '页面于 {path}'

button_save = '保存'
button_save_tooltip = '保存 [{}]'
button_exit = '离开'
button_exit_tooltip = '离开 [{}]'


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
• 默认输入的关键词会在标题、评注、全文中查找。
• 可用半形空白分隔要检索的多个关键词。例如“w3c organization”表示搜索含有“w3c”及“organization”的项目 。
• 可用半形双引号检索完整关键词，若关键词包含半形双引号，可用连续两个半形双引号表示。例如“"Tom ""loves"" Mary."”表示搜索含有“Tom "loves" Mary.”的项目。
• 可用负号排除关键词。例如“-virus”表示搜索不含“virus”的项目。
• 可用“<命令>:<关键词>”指定特殊的检索条件，命令前可加负号表示排除或反向。可用命令如下：
  • default：重设所有未指定命令的关键词要查找的栏位，栏位名称以「,」分隔，匹配任一栏位皆视为找到。例如「default:id,title,source,comment,content 2020」表示搜索 ID、标题、原始网址、评注、或全文含有「2020」的项目。加负号表示移除已设置的栏位，例如「default:title,comment -default:comment」相当于「default:title」。
  • mc：之后的关键词皆比对大小写。加负号则反之。例如“mc: CIA FBI -mc: president”表示搜索含有区分大小写的“CIA”、“FBI”及不分大小写的“president”的项目。
  • re：之后的关键词皆视为正则表达式。加负号则反之。例如“re: \\bcolou?r\\b -re: 1+1=2”表示搜索匹配正则表达式“\\bcolou?r\\b”且含有关键词“1+1=2”的项目。
  • id：搜索 ID 等同关键词（或与正则表达式匹配）的项目。多次指定时以“或”连接。例如“id:2020 id:2021”表示搜索 ID 为“2020”或“2021”的项目；“-id:2020”表示搜索 ID 不为“2020”的项目。
  • type：搜索类型等同关键词（或与正则表达式匹配）的项目。多次指定时以“或”连接。可用的类型有“”（网页）、“bookmark”（书签）、“file”（文件）、“note”（笔记）等等。例如“type: type:bookmark”表示搜索类型为网页或书签的项目。
  • title：搜索标题含有关键词的项目。
  • content：搜索全文含有关键词的项目。
  • comment：搜索评注含有关键词的项目。
  • index：搜索索引文件含有关键词的项目。
  • source：搜索原始网址含有关键词的项目。
  • icon：搜索图示网址含有关键词的项目。
  • charset：搜索字元集含有关键词的项目。
  • create：搜索建立时间匹配条件的项目。多次指定时以“或”连接。时间格式为 0-17 位数字，后面接负号（可略），再接 0-17 位数字，表示时间范围的起始与结束。两个 17 位数字表示本地时间的年（4 位数）、月（01-12）、日（01-31）、时（00-59）、分（00-59）、秒（00-59）、毫秒（000-999），省略的部分视为补 0，唯结束时间全省略时视为“999...”。例如“create:2014-2015”表示 2014 年到 2015 年，“create:-201309”表示 2013 年九月以前，“create:20110825”表示 2011 年八月 25 日以后。
  • modify：搜索修改时间匹配条件的项目。多次指定时以“或”连接。时间格式同 create。
  • marked：搜索强调标示的项目。
  • locked：搜索锁定的项目。
  • location：搜索含有地理位置信息的项目。
  • file：搜索文件名含有关键词的项目。
  • root：搜索此 ID 项目下的子项目。多次指定时以“或”连接。
  • book：搜索指定剪贴簿（依 ID）中的项目。多次指定时以“或”连接。
  • sort：将搜索结果按指定方式排序，负号表示倒序。可填入 id、title、comment、file、content、source、type、create、modify。例如“sort:id -sort:modify”表示先按 ID 递增排序再按修改时间递减排序。
  • limit：设置搜索结果笔数限制。例如“limit:10”表示只呈现前 10 笔搜索结果。“-limit:”表示移除之前设置的限制。"""
cache_search_result = '找到 %length% 笔结果：'
cache_search_result_named = '(%name%) 找到 %length% 笔结果：'
cache_search_sort_last_created = '最后创建'
cache_search_sort_last_modified = '最后修改'
cache_search_sort_title = '标题排序'
cache_search_sort_id = 'ID 排序'
cache_search_confirm_remote = '加载远程全文缓存可能使用较大的网络流量。要继续吗？'


#########################################################################
# WebScrapBook
#########################################################################

EditorDeleteAnnotationConfirm = '删除这个批注吗？'
