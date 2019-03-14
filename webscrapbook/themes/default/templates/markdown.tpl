% from urllib.parse import quote
% from webscrapbook import util
% qbase = quote(base)
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Page {{ path }}</title>
<link rel="stylesheet" type="text/css" href="{{ qbase }}/common.css?a=static">
</head>
<body>
<header>
<h1 id="header" class="breadcrumbs">\\
% for label, subpath, sep, is_last in util.get_breadcrumbs(path, base, sitename):
%   if not is_last:
<a href="{{ quote(subpath) }}">{{ label }}</a>{{ sep }}\\
%   else:
<a>{{ label }}</a>\\
%   end
% end
</h1>
</header>
<main>
{{ !content }}
</main>
</body>
</html>