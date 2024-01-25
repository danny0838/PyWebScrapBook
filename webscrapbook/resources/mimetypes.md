## Customize MIME types

MIME type mappings for WebScrapBook are defined by:

1. the default mappings of the native Python code
2. the system-wide registry
3. the internal mappings of WebScrapBook
4. the user config file for WebScrapBook

For conflicting definitions, a conversion of file extension to MIME type is
handled in a last-win manner, while a conversion of MIME type to file 
extension(s) is handled in a first-win manner.

As an exception, the internal mappings of WebScrapBook overwrites any
conflicting mappings of the prior ones, to fix known mapping issues in native
Python and platforms.


## System registry

### Windows

MIME type mappings can be defined in Windows registry. For example, to add
`font/woff` as a MIME type of `.woff`:

* Visit the Windows registry editor (`regedit.exe`)
* Go to `HKEY_LOCAL_MACHINE\Software\Classes`
* Right click on `Classes`, select `New Key`, and fill `.woff`.
* Right click on the right hand side, select `New String`, and fill
  `Content Type`.
* Right click on `Content Type`, and modify its value to `font/woff`.

### Linux/POSIX

MIME type mappings can be defined in one of the following config files (defined
by the `mimetypes.knownfiles` of Python and may be slightly different across
versions):

* `/etc/mime.types`
* `/etc/httpd/mime.types`
* `/etc/httpd/conf/mime.types`
* `/etc/apache/mime.types`
* `/etc/apache2/mime.types`
* `/usr/local/etc/httpd/conf/mime.types`
* `/usr/local/lib/netscape/mime.types`
* `/usr/local/etc/httpd/conf/mime.types`
* `/usr/local/etc/mime.types`

These files look like:

    # A "#" at line beginning starts a comment, causing the whole line ignored
    # when run. A comment can also be used to temporarily disable a setting for
    # testing or debugging purpose.
    text/plain   txt text
    font/woff    woff
    #...


## User config

Custom MIME type mappings can be defined in `~/.config/wsb/mime.types`, with
the same syntax of the Linux/POSIX config files.
