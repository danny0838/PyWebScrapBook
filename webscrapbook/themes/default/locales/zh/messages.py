bidi_dir = 'ltr'


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
• 輸入的關鍵詞會在標題、內文、評註中查找。
• 可用半形空白分隔要檢索的多個關鍵詞。例如「w3c organization」表示搜尋含有「w3c」及「organization」的項目 。
• 可用半形雙引號檢索完整關鍵詞，若關鍵詞包含半形雙引號，可用連續兩個半形雙引號表示。例如「"Tom ""loves"" Mary."」表示搜尋含有「Tom "loves" Mary.」的項目。
• 可用負號排除關鍵詞。例如「-virus」表示搜尋不含「virus」的項目。
• 可用「<命令>:<關鍵詞>」指定特殊的檢索條件，命令前可加負號表示排除或反向。可用命令如下：
  • mc：之後的關鍵詞皆比對大小寫。加負號則反之。例如「mc: CIA FBI -mc: president」表示搜尋含有區分大小寫的「CIA」、「FBI」及不分大小寫的「president」的項目。
  • re：之後的關鍵詞皆視為正規表示式。加負號則反之。例如「re: \\bcolou?r\\b -re: 1+1=2」表示搜尋匹配正規表示式「\\bcolou?r\\b」且含有關鍵詞「1+1=2」的項目。
  • id：搜尋 ID 等同關鍵詞（或與正規表示式匹配）的項目。多次指定時以「或」連接。例如「id:2020 id:2021」表示搜尋 ID 為「2020」或「2021」的項目；「-id:2020」表示搜尋 ID 不為「2020」的項目。
  • type：搜尋類型等同關鍵詞（或與正規表示式匹配）的項目。多次指定時以「或」連接。可用的類型有「」（網頁）、「bookmark」（書籤）、「file」（檔案）、「note」（筆記）等等。例如「type: type:bookmark」表示搜尋類型為網頁或書籤的項目。
  • title：搜尋標題含有關鍵詞的項目。
  • content：搜尋全文含有關鍵詞的項目。
  • comment：搜尋評註含有關鍵詞的項目。
  • tc：搜尋標題或評註含有關鍵詞的項目。
  • tcc：搜尋標題、全文或評註含有關鍵詞的項目。
  • index：搜尋索引檔含有關鍵詞的項目。
  • source：搜尋原始網址含有關鍵詞的項目。
  • icon：搜尋圖示網址含有關鍵詞的項目。
  • charset：搜尋字集含有關鍵詞的項目。
  • create：搜尋建立時間符合條件的項目。時間格式為 0-17 位數字，後面接負號（可略），再接 0-17 位數字，表示時間範圍的起始與結束。兩個 17 位數字表示本地時間的年（4 位數）、月（01-12）、日（01-31）、時（00-59）、分（00-59）、秒（00-59）、毫秒（000-999），省略的部分視為 0，唯結束時間全省略時視為「999...」。例如「create:2014-2015」表示 2014 年到 2015 年，「create:-201309」表示 2013 年九月以前，「create:20110825」表示 2011 年八月 25 日以後。
  • modify：搜尋修改時間符合條件的項目。時間格式同 create。
  • marked：搜尋強調標示的項目。
  • locked：搜尋鎖定的項目。
  • location：搜尋含有地理位置資訊的項目。
  • file：搜尋檔名含有關鍵詞的項目。
  • root：搜尋此 ID 項目下的子項目。多次指定時以「或」連接。
  • book：搜尋指定剪貼簿（依名稱）中的項目。多次指定時以「或」連接。
  • sort：將搜尋結果按指定方式排序，負號表示倒序。可填入 id、title、comment、file、content、source、type、create、modify。例如「sort:id -sort:modify」表示先按 ID 遞增排序再按修改時間遞減排序。
  • limit：設定搜尋結果筆數限制。例如「limit:10」表示只呈現前 10 筆搜尋結果，「limit:-20」表示不呈現最後 20 筆搜尋結果，「limit:0」或「-limit:」表示移除之前設定的限制。"""
cache_search_result = '找到 %length% 筆結果：'
cache_search_result_named = '(%name%) 找到 %length% 筆結果：'
cache_search_sort_last_created = '最後建立'
cache_search_sort_last_modified = '最後修改'
cache_search_sort_title = '標題排序'
cache_search_sort_id = 'ID 排序'


#########################################################################
# WebScrapBook
#########################################################################

EditorDeleteAnnotationConfirm = '刪除這個批註嗎？'
