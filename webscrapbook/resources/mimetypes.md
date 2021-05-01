## Customize MIME types

There are two ways to define custom MIME types mapping for WebScrapBook:

1. using system-wide registry
2. using user config file


## System registry

Custom MIME types mapping can be added to the filesystem registry for
WebScrapBook to use it.

### Windows

Custom MIME types mapping can be defined in Windows registry. For example,
to add `font/woff` as a MIME type of `.woff`:

* Visit the Windows registry editor (`regedit.exe`)
* Go to `HKEY_LOCAL_MACHINE\Software\Classes`
* Right click on `Classes`, select `New Key`, and fill `.woff`.
* Right click on the right hand side, select `New String`, and fill
  `Content Type`.
* Right click on `Content Type`, and modify its value to `font/woff`.

### Linux

Custom MIME types mapping can be defined in one of the following files:

* `/etc/mime.types`
* `/etc/httpd/mime.types`
* `/etc/httpd/conf/mime.types`
* `/etc/apache/mime.types`
* `/etc/apache2/mime.types`
* `/usr/local/etc/httpd/conf/mime.types`
* `/usr/local/lib/netscape/mime.types`
* `/usr/local/etc/httpd/conf/mime.types`
* `/usr/local/etc/mime.types`


## User config

Custom MIME types mapping can be defined in `~/.config/wsb/mime.types`,
which looks like:

    # A "#" at line beginning starts a comment, causing the whole line ignored
    # when run. A comment can also be used to temporarily disable a setting for
    # testing or debugging purpose.
    text/plain   txt text
    font/woff    woff
    #...
