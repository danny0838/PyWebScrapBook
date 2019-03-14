% from urllib.parse import quote
% qbase = quote(base)
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Edit {{ path }}</title>
<link rel="stylesheet" type="text/css" href="{{ qbase }}/common.css?a=static">
<link rel="stylesheet" type="text/css" href="{{ qbase }}/edit.css?a=static">
<script src="{{ qbase }}/common.js?a=static"></script>
<script src="{{ qbase }}/edit.js?a=static"></script>
</head>
<body>
<div id="pinned">
<noscript>
<div class="error">Enable JavaScript or upgrade your browser to support JavaScript, so that the HTML editor can work.</div>
</noscript>
% if not is_utf8:
<div class="warning">This file is decoded as ISO-8859-1, and will be encoded as UTF-8 when saved.</div>
% end
</div>
<textarea id="editor">{{ body }}</textarea>
<div id="toolbar">
  <div>
    <input id="btn-save" type="button" value="SAVE" autocomplete="off">
    <input id="btn-exit" type="button" value="EXIT" autocomplete="off">
  </div>
</div>
</body>
</html>
