bidi_dir = 'ltr'
html_lang = 'zh'

index_title = '索引於 {path}'

data_table_header_directory = '資料夾'
data_table_header_name = '檔名'
data_table_header_last_modified = '最後修改'
data_table_header_size = '大小'

explorer_tooltip = '檢視模式 [{}]'
explorer_table = '表格檢視'
explorer_gallery = '圖示檢視'
explorer_gallery2 = '圖示檢視 (+多媒體)'

tools_tooltip = '工具 [{}]'
tools_preview_on = '啟用預覽'
tools_preview_off = '停用預覽'
tools_select_all = '全選'
tools_deselect_all = '取消全選'
tools_expand_all = '展開所有項目'
tools_filter = '篩選'
tools_filter_clear = '清除篩選'

tools_filter_prompt = '用關鍵詞篩選（字串或用「/表示式/標幟」表示正規表示式）:'

command_tooltip = '命令 [{}]'
command_mkdir = '新資料夾'
command_mkzip = '新壓縮檔'
command_mkfile = '新檔案'
command_upload = '上傳'
command_uploaddir = '上傳資料夾'
command_source = '檢視原始碼'
command_download = '下載'
command_exec = '本地執行'
command_browse = '本地檢視'
command_edit = '編輯'
command_editx = '編輯頁面'
command_move = '移動'
command_copy = '複製'
command_link = '建立超連結'
command_delete = '刪除'

command_mkdir_prompt = '建立新資料夾並命名為:'
command_mkdir_default = 'new-folder'
command_mkzip_prompt = '建立 ZIP 壓縮檔並命名為:'
command_mkzip_default = 'new-archive.zip'
command_mkfile_prompt = '建立檔案並命名為:'
command_mkfile_default = 'new-file.txt'
command_move_prompt = '移動至此路徑或資料夾:'
command_move_prompt_multi = '移動至此資料夾:'
command_copy_prompt = '複製至此路徑或資料夾:'
command_copy_prompt_multi = '複製至此資料夾:'
command_link_prompt = '建立超連結於此路徑或資料夾:'
command_link_prompt_multi = '建立超連結於此資料夾:'

label_selected = '已選取 %count% 項'

previewer_toolbar_title = """\
鍵盤快捷鍵:
• [Esc]: 關閉預覽。
• [I] 或 [Space]: 切換資訊欄。
• [Enter]: 在新分頁開啟。
• [PageUp] 或 [Alt+←] 或 [←]: 顯示上一項。
• [PageDown] 或 [Alt+→] 或 [→]: 顯示下一項。
• [Home]: 顯示第一項。
• [End]: 顯示最後一項。
• [+] 或 [Alt+↑] 或 [↑]: 放大。
• [-] 或 [Alt+↓] 或 [↓]: 縮小。
• [Ctrl+0]: 縮放至符合可視範圍。
• [Ctrl+1]: 切換縮放為圖片大小與最後縮放大小。
• [Ctrl+←] 或 [Shift+←]: 左移。
• [Ctrl+→] 或 [Shift+→]: 右移。
• [Ctrl+↑] 或 [Shift+↑]: 上移。
• [Ctrl+↓] 或 [Shift+↓]: 下移。
"""
previewer_button_previous = '上一項'
previewer_button_next = '下一項'
previewer_button_infobar = '切換資訊欄'
previewer_button_close = '關閉預覽'

edit_title = '編輯 {path}'
edit_error_no_javascript = '啟用 JavaScript 或升級瀏覽器以支援 JavaScript，此 HTML 編輯器才能正常運作。'
edit_warning_encoding = '此檔案以 {encoding} 解碼，儲存時將編碼為 UTF-8。'

markdown_title = '頁面 {path}'
maff_index_title = '頁面於 {path}'

button_save = '儲存'
button_save_tooltip = '儲存 [{}]'
button_exit = '離開'
button_exit_tooltip = '離開 [{}]'


#########################################################################
# scrapbook.cache
#########################################################################

# map.html
cache_index_toggle_all = '全部展開或收合'
cache_index_search_link_title = '搜尋'
cache_index_source_link_title = '來源連結'

# search.html
cache_search_title = '%book% :: 搜尋'
cache_search_view_in_map = '在索引頁中檢視'
cache_search_start = '查'
cache_search_help_label = '搜尋語法說明'
cache_search_help_desc = """\
• 預設輸入的關鍵詞會在標題、評註、全文中查找。
• 可用半形空白分隔要檢索的多個關鍵詞。例如「w3c organization」表示搜尋含有「w3c」及「organization」的項目 。
• 可用半形雙引號檢索完整關鍵詞，若關鍵詞包含半形雙引號，可用連續兩個半形雙引號表示。例如「"Tom ""loves"" Mary."」表示搜尋含有「Tom "loves" Mary.」的項目。
• 可用負號排除關鍵詞。例如「-virus」表示搜尋不含「virus」的項目。
• 可用「<命令>:<關鍵詞>」指定特殊的檢索條件，命令前可加負號表示排除或反向。可用命令如下：
  • default：重設所有未指定命令的關鍵詞要查找的欄位，欄位名稱以「,」分隔，匹配任一欄位皆視為找到。例如「default:id,title,source,comment,content 2020」表示搜尋 ID、標題、原始網址、評註、或全文含有「2020」的項目。加負號表示移除已設定的欄位，例如「default:title,comment -default:comment」相當於「default:title」。
  • mc：之後的關鍵詞皆比對大小寫。加負號則反之。例如「mc: CIA FBI -mc: president」表示搜尋含有區分大小寫的「CIA」、「FBI」及不分大小寫的「president」的項目。
  • re：之後的關鍵詞皆視為正規表示式。加負號則反之。例如「re: \\bcolou?r\\b -re: 1+1=2」表示搜尋匹配正規表示式「\\bcolou?r\\b」且含有關鍵詞「1+1=2」的項目。
  • id：搜尋 ID 等同關鍵詞（或與正規表示式匹配）的項目。多次指定時以「或」連接。例如「id:2020 id:2021」表示搜尋 ID 為「2020」或「2021」的項目；「-id:2020」表示搜尋 ID 不為「2020」的項目。
  • type：搜尋類型等同關鍵詞（或與正規表示式匹配）的項目。多次指定時以「或」連接。可用的類型有「」（網頁）、「bookmark」（書籤）、「file」（檔案）、「note」（筆記）等等。例如「type: type:bookmark」表示搜尋類型為網頁或書籤的項目。
  • title：搜尋標題含有關鍵詞的項目。
  • content：搜尋全文含有關鍵詞的項目。
  • comment：搜尋評註含有關鍵詞的項目。
  • index：搜尋索引檔含有關鍵詞的項目。
  • source：搜尋原始網址含有關鍵詞的項目。
  • icon：搜尋圖示網址含有關鍵詞的項目。
  • charset：搜尋字集含有關鍵詞的項目。
  • create：搜尋建立時間符合條件的項目。多次指定時以「或」連接。時間格式為 0-17 位數字，後面接負號（可略），再接 0-17 位數字，表示時間範圍的起始與結束。兩個 17 位數字表示本地時間的年（4 位數）、月（01-12）、日（01-31）、時（00-59）、分（00-59）、秒（00-59）、毫秒（000-999），省略的部分視為 0，唯結束時間全省略時視為「999...」。例如「create:2014-2015」表示 2014 年到 2015 年，「create:-201309」表示 2013 年九月以前，「create:20110825」表示 2011 年八月 25 日以後。
  • modify：搜尋修改時間符合條件的項目。多次指定時以「或」連接。時間格式同 create。
  • marked：搜尋強調標示的項目。
  • locked：搜尋鎖定的項目。
  • location：搜尋含有地理位置資訊的項目。
  • file：搜尋檔名含有關鍵詞的項目。
  • root：搜尋此 ID 項目下的子項目。多次指定時以「或」連接。
  • book：搜尋指定剪貼簿（依 ID）中的項目。多次指定時以「或」連接。
  • sort：將搜尋結果按指定方式排序，負號表示倒序。可填入 id、title、comment、file、content、source、type、create、modify。例如「sort:id -sort:modify」表示先按 ID 遞增排序再按修改時間遞減排序。
  • limit：設定搜尋結果筆數限制。例如「limit:10」表示只呈現前 10 筆搜尋結果。「-limit:」表示移除之前設定的限制。"""
cache_search_result = '找到 %length% 筆結果：'
cache_search_result_named = '(%name%) 找到 %length% 筆結果：'
cache_search_sort_last_created = '最後建立'
cache_search_sort_last_modified = '最後修改'
cache_search_sort_title = '標題排序'
cache_search_sort_id = 'ID 排序'
cache_search_confirm_remote = '載入遠端全文快取可能使用較大的網路流量。要繼續嗎？'


#########################################################################
# WebScrapBook
#########################################################################

EditorDeleteAnnotationConfirm = '刪除這個批註嗎？'
