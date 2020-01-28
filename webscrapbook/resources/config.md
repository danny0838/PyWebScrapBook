## Basic

WebScrapBook has 3 levels of configuration:

* default: written in the source code
* user: at "~/.wsbconfig"
* book: at "<book>/.wsb/config.ini"

with the latters overwriting the formers.


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

The [app] section defines the behavior of WebScrapBook application, which can
be hosted by either the built-in server or by Apache WSGI module or so.


#### `name`

The name for the served website, which is used for the site title, the label of
the top level of breadcrumbs, etc.

(default: WebScrapBook)


#### `theme`

The theme name for the served website. You can define a theme at
.wsb/themes/<name>.

(default: default)


#### `root`

The root directory to host. Absolute path or relative to the current 
working directory.

(default: .)


#### `base`

The base URL path the app is serving at. When this app is not served at root
path, (e.g. https://your.site/path/to/app rather than https://your.site/),
the server usually sets the SCRIPT_NAME environmental variable to get things
work right; but sometimes the server may fail to do so, and this can be set
to /path/to/app to get things work right.

(default: )


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

The [server] section defines the behavior of the built-in HTTP server, which can
be run by "wsb serve" command or by running the serve.py shortcut generated by
"wsb config -ba".


#### `port`

A port integer ranged from 0 to 65535 to host. Pick a port >= 1024 to avoid a
conflict with system ports. Consider the default port (80 for HTTP and 443 for
HTTPS) for public hosting.

(default: 8080)


#### `host`

Host name of the server, for the server to identify itself and is used to 
launch the browser. Use "localhost" for local hosting, or a configured domain
name, IPv4, or IPv6 address. (Configuration of firewall and routers may be
needed for the server to be actually accessible from wide area network.)

(default: localhost)


#### `threads`

How many threads the server can use to process incoming connection. Assign a
positive integer; otherwise it's determined automatically according to system
CPUs.

(default: 0)


#### `ssl_on`

Set true to enable HTTPS, and false otherwise.

Other `ssl_` settings are required for HTTPS to work correctly. A simple
self-signed certificate can be generated using openssl for testing purpose or
for private usage, e.g.:

    openssl req \
      -newkey rsa:2048 -nodes -keyout domain.key \
      -x509 -days 365 -out domain.crt

and use "domain.key" for ssl_key and "domain.crt" for ssl_cert.

(default: false)


#### `ssl_key`

The SSL key file for HTTPS hosting. Use absolute path or relative to the root
directory.

(default: )


#### `ssl_cert`

The SSL certificate file for HTTPS hosting. Use absolute path or relative to
the root directory.

(default: )


#### `ssl_pw`

The password for the SSL certificate.

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
