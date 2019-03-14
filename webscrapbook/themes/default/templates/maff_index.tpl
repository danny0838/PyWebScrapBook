% import os
% from urllib.parse import quote
% qbase = quote(base)
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pages of {{ path }}</title>
<link rel="stylesheet" type="text/css" href="{{ qbase }}/common.css?a=static">
</head>
<body>
<h1 id="header">Pages of {{ path }}</h1>
<ul>
<%
  root = os.path.basename(path)
  for page in pages:
    url = quote(root + '!/' + page.indexfilename)
    label = page.indexfilename.partition('/')[0]
    title = page.title or ''
%>
<li><a href="{{ url }}" title="{{ title }}">{{ label }}</a></li>
<% end %>
</ul>
</body>
</html>