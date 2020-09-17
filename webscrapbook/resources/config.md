## Basic

WebScrapBook has 3 levels of configuration:

* default: written in the source code
* user: at `~/.wsbconfig`
* book: at `<book>/.wsb/config.ini`

with the latters overwriting the formers.

A config file can be generated using the command `wsb config`. Run
`wsb config --help` for more details.

Configs are loaded only at process starting, and a config change won't affect
an already running process. For example, a running webscrapbook server needs
to be shut off and restarted to get new configs take effect.


## Configuration Format

A WebScrapBook config file is written in "ini" format, which looks like:

    # A "#" or ";" at line beginning starts a comment, causing the whole
    # line ignored when run. A comment can also be used to temporarily
    # disable a setting for testing or debugging purpose.

    # "[" and "]" define a section.
    [server]
    # A key-value pair separated by "=" or ":". Spaces around the separator
    # and the value are stripped. For example, "theme=default" is equivalent
    # to "theme  =    default  "
    theme = default

    # Use true/false, on/off, yes/no, or 1/0 for a boolean value.
    ssl_on = false

    # A section may be subsected using syntax [section "subsection"]. In such
    # case [section] also means [section ""].
    [auth "user1"]
    user = myuser1
    #...

    [auth "user2"]
    user = myuser2
    #...


## Available values


### [app] section

The [app] section defines the behavior of WebScrapBook application, which
follows WSGI specification and can be hosted by any WSGI server, such as the
built-in server or Apache mod_wsgi.


#### `name`

The name for the served website, which is used for the site title, the label of
the top level of breadcrumbs, etc.

(default: WebScrapBook)


#### `theme`

The theme name for the served website. A custom theme can be defined at
"<book>/.wsb/themes/<name>", which contains a "templates" sub-directory for
template files and a "static" sub-directory for static files. If the custom
theme has a same name as the built-in one, the application will look up for
a resource first from custom one and fallback to the default one when not
found.

(default: default)


#### `root`

The root directory to host. Absolute path or relative to the top directory (the
one that contains the ".wsb" directory).

(default: .)


#### `base`

The base URL path the app is serving at. When this app is not served at root
path, the upper app usually sets the SCRIPT_NAME environmental variable to get
things work right. If it fails to do so, this value can be set for a fix.

For example, the app is served under https://example.com/path/to/app, this
value can be set to "/path/to/app" if an expected SCRIPT_NAME is not provided.

(default: )


#### `content_security_policy`

Whether to send response with a content security policy header, which restricts
AJAX and form actions for data pages to prevent a potential attack from a
malicious script. Currently only the value "strict" is used. Set this to empty
if you really need such features, but make sure that scripts and forms in the
captured pages are all safe!

(default: strict)


#### `allowed_x_for`

Number of values to trust for "X-Forwarded-For" header(s) when this app is
run behind a reverse proxy.

For example, if the app is served behind one reverse proxy that appends
"X-Forwarded-For" header, set this value to 1 and the last value will be
taken as the client address.

(default: 0)


#### `allowed_x_proto`

Number of values to trust for "X-Forwarded-Proto" header(s) when this app is
run behind a reverse proxy.

By convention the header set by a reverse proxy is in an overwriting way.
In most cases this value can be set to 1 if a trusted reverse proxy sets it,
and 0 otherwise.

(default: 0)


#### `allowed_x_host`

Number of values to trust for "X-Forwarded-Host" header(s) when this app is
run behind a reverse proxy.

See `allowed_x_proto` for convention of usage.

(default: 0)


#### `allowed_x_port`

Number of values to trust for "X-Forwarded-Port" header(s) when this app is
run behind a reverse proxy.

See `allowed_x_proto` for convention of usage.

(default: 0)


#### `allowed_x_prefix`

Number of values to trust for "X-Forwarded-Prefix" header(s) when this app is
run behind a reverse proxy.

See `allowed_x_proto` for convention of usage.

(default: 0)


### [book] section(s)

The book section(s) define scrapbooks for the application to handle. It can be
subsected as [book "identifier"]. The primary scrapbook ([book] or [book ""])
is used by default. Additional scrapbooks can be defined and be switched into.


#### `name`

Defines the name of the scrapbook.

(default: scrapbook)


#### `top_dir`

The top directory of the scrapbook. It's a directory path under the root,
without leading or trailing slash.

(default: )


#### `data_dir`

The directory where scrapbook data should be stored in. It's a directory path
under top_dir, without leading or trailing slash, and cannot be under tree_dir
or .wsb. Use "data" if the scrapbook is migrated from legacy ScrapBook.

(default: )


#### `tree_dir`

The directory where scrapbook index tree should be stored in. It's a directory
path under top_dir, without leading or trailing slash. Use "tree" if the
scrapbook is migrated from legacy ScrapBook.

(default: .wsb/tree)


#### `index`

The path where the scrapbook index page resides. It's a URL path under top_dir,
without leading slash. Use "tree/map.html" or "tree/map.html" if the scrapbook
is migrated from legacy ScrapBook.

(default: .wsb/tree/index.html)


#### `no_tree`

Set true to disable virtual tree and index of the book.

(default: false)


### [auth] section(s)

The [auth] section(s) define authorization rules. It can be subsected as
[auth "identifier"]. Authorization requirement is activated when at least one
[auth] section exists. Each section defines a rule, and the user must fullfill
at least one to be allowed to access.

An encrypted password can be generated via the "encrypt" sub-command, For
example:

    webscrapbook encrypt -m sha1 -s mysalt

You'll then be promopted to input a password, and then you can use the output
for pw, "mysalt" for pw_salt, and "sha1" for pw_type.

To specify permission for an anonymous user, create an [auth] section with
empty user and a password matching an empty string (e.g. "plain" pw_type, empty
pw, and empty pw_salt.)

NOTE: Use HTTPS protocol as possible when password authorization is activated,
as input user name and password are unencrypted during HTTP transmission.


#### `user`

The user's name.

(default: )


#### `pw`

The user's password, in encrypted form.

(default: )


#### `pw_salt`

A "salt" string which is added during encryption for better security.

(default: )


#### `pw_type`

The encryption method for password. Supported methods are: plain, md5, sha1,
sha224, sha256, sha384, sha512, sha3_224, sha3_256, sha3_384, and sha3_512.

(default: sha1)


#### `permission`

The permission for those who fullfills this authorization condition.
* "all": unrestricted access.
* "read": read-only. APIs for data modification are disabled. Note that
  essential server information is still exposed. Recommended for read-only
  WebScrapBook browser extension access.
* "view": web browsing only. Most APIs are disabled and access via
  WebScrapBook browser extension is not allowed. Recommended for general public
  access.

(default: all)


### [server] section

The [server] section defines the behavior of the built-in HTTP server, which
can be run by "wsb serve" command or by running the "serve.py" shortcut
generated by "wsb config -ba".

Note that the built-in server is designed only for local hosting, or remote
hosting for personal or few people usage. As for world wide web hosting, a more
specialized server is generally required.


#### `port`

A port integer ranged from 0 to 65535 to host. Pick a port >= 1024 to avoid a
conflict with system ports. Consider the default port (80 for HTTP and 443 for
HTTPS) for public hosting.

(default: 8080)


#### `host`

Host identity of the server, as a domain name, IPv4, or IPv6 address. The
server will only react to connections targeting a matching value. As a rule of
thumb, use "localhost" for local hosting, "0.0.0.0" or "::" for world wide web
hosting, and another value for specific subnet hosting.

Configuration of firewall and router(s) may be needed for the server to be
actually accessible from wide area network.

(default: localhost)


#### `ssl_on`

Set true to enable HTTPS, and false otherwise.

Set `ssl_key` and `ssl_cert` to define the certificate for SSL.

A simple self-signed certificate can be generated using OpenSSL for testing
purpose or for private usage, e.g.:

    openssl req \
      -newkey rsa:2048 -nodes -keyout domain.key \
      -x509 -days 365 -out domain.crt

and use "domain.key" for ssl_key and "domain.crt" for ssl_cert.

An "adhoc" certificate can be used by setting `ssl_on` with empty `ssl_key` and
`ssl_cert`, and a temporary certificate will be auto-generated every time when
the server starts. However, this feature requires extra dependency, which can
be installed via `pip install webscrapbook[adhoc_ssl]`.

(default: false)


#### `ssl_key`

The SSL key file for HTTPS hosting. Use absolute path or relative to the root
directory.

(default: )


#### `ssl_cert`

The SSL certificate file for HTTPS hosting. Use absolute path or relative to
the root directory.

(default: )


#### `browse`

Set true to launch the browser when the server starts, and false otherwise.

(default: true)


### [browser] section

The [browser] section defines the desired browser to launch when needed. The
browser is launched when, for example, the server starts.


#### `command`

The browser path with CLI arguments to launch. Use "%s" to represent the URL
and append "&" at end to launch browser in the background, which is generally
preferred to avoid interruption. Empty to use system default browser.

Example:

    # Launch a Chrome incognito window
    command = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --incognito %s &

    # Launch a Firefox private window
    command = "C:\Program Files\Mozilla Firefox\firefox.exe" -private-window %s &

(default: )


#### `index`

The index page to visit when the browser is launched. This is a URL path under
the root path the application is served, without leading slash.

(default: )


#### `cache_prefix`

The prefix for caches for viewing archive files under the system temporary
directory. Assign a unique string if the default one conflicts with another
application.

(default: webscrapbook.)


#### `cache_expire`

The duration in seconds for cache files for viewing archive files to be purged.

(default: 259200 (3 days))


#### `use_jar`

Whether to use JAR protocol for viewing archive files. JAR protocol, supported
by Firefox (Gecko) based browsers, allows accessing ZIP content files directly
without extracting them in prior.

(default: false)
