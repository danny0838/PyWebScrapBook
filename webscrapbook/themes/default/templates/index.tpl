% from urllib.parse import quote, unquote
% from webscrapbook import util
% import time
% qbase = quote(base)
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Index of {{ path }}</title>
<link rel="stylesheet" type="text/css" href="{{ qbase }}/common.css?a=static">
<link rel="stylesheet" type="text/css" href="{{ qbase }}/index.css?a=static">
<script src="{{ qbase }}/common.js?a=static"></script>
<script src="{{ qbase }}/index.js?a=static"></script>
</head>
<body>
<header>
<h1 id="header" class="breadcrumbs">\\
% for label, subpath, sep, is_last in util.get_breadcrumbs(path, base, sitename, subarchivepath):
%   if not is_last:
<a href="{{ quote(subpath) }}">{{ label }}</a>{{ sep }}\\
%   else:
<a>{{ label }}</a>{{ sep }}\\
%   end
% end
</h1>
</header>
<main>
<table id="data-table" data-sitename="{{ sitename }}" data-base="{{ base }}" data-path="{{ path }}" data-subarchivepath="{{ subarchivepath or '' }}">
<thead>
  <tr><th><a hidden>Directory</a></th><th><a>Name</a></th><th class="detail"><a>Last modified</a></th><th class="detail"><a>Size</a></th></tr>
</thead>
<tbody>
<%
  for info in subentries:
    filename = info.name
    url = quote(info.name) + ('/' if info.type == 'dir' else '')
    filetype = info.type
    size = info.size
    size_text = util.format_filesize(size) if size else ''
    lm = info.last_modified
    lm_text = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(lm))
%>
  <tr class="{{ filetype }}"><td data-sort="{{ filename }}"><a class="icon {{ filetype }}" title="{{ filename }}"></a><td data-sort="{{ filename }}"><a href="{{ url }}">{{ filename }}</a></td><td class="detail" data-sort="{{ lm or '' }}">{{ lm_text }}</td><td class="detail" data-sort="{{ size or '' }}">{{ size_text }}</td></tr>
<% end %>
</tbody>
</table>
</main>
<footer>
<form id="panel" autocomplete="off" hidden>
  <select id="viewer">
    <option value="" selected>Normal View</option>
    <option value="gallery">Gallery View</option>
    <option value="list">List View</option>
    <option value="deep">Deep List</option>
  </select>
  <select id="command">
    <option value="" selected>...</option>
    <option value="source" hidden>View source</option>
    <option value="exec" hidden{{ '' if is_local else ' disabled' }}>Run natively</option>
    <option value="browse" hidden{{ '' if is_local else ' disabled' }}>Browse natively</option>
    <option value="mkdir" hidden>New folder</option>
    <option value="edit" hidden>New file</option>
    <option value="editx" hidden>Edit page</option>
    <option value="upload" hidden>Upload</option>
    <option value="move" hidden>Move</option>
    <option value="copy" hidden>Copy</option>
    <option value="delete" hidden>Delete</option>
  </select>
  <input type="file" id="upload-file-selector" multiple hidden>
</form>
</footer>
</body>
</html>