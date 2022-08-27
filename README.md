PyWebScrapBook is a command line toolkit and backend server for
[WebScrapBook browser extension](https://github.com/danny0838/webscrapbook).

## Features
* Host any directory(s) as website(s).
* Directory listing.
* HTZ or MAFF archive file viewing.
* Markdown file rendering.
* Create, view, edit, and/or delete files via the web interface or API.
* HTTP(S) authorization and simple ACL.
* Tools for scrapbooks management, such as cache generating and data checking, exporting, importing, and conversion.

## Usage

### Install Python

Install Python >= 3.7 from the [official site](https://www.python.org).

Add python to `PATH` environment variable so that it can be run from the command line interface (CLI).

### Install this package

Run below command from CLI to install (or upgrade to) the latest version:

    python -m pip install -U webscrapbook

After installation, `wsb`, `webscrapbook`, and `wsbview` will be available from the CLI.

### Usage overview

Run `wsb --help` for help about available commands, which looks like:

    usage: wsb [-h] [--version] [--root ROOT] COMMAND ...

    positional arguments:
      COMMAND      the sub-command to run. Get usage help with e.g. wsb config -h
        serve (s)  serve the root directory
        config (c)
                   show, generate, or edit the config
        encrypt (e)
                   generate an encrypted password
        cache (a)  update fulltext cache and/or static site pages
        check (k)  check and fix scrapbook data
        export (x)
                   export data items into archive files (*.wsba)
        import (i)
                   import data items from archive files (*.wsba)
        convert (v)
                   convert scrapbook data between different formats
        help       show detailed information about certain topics
        view       view archive file in the browser

    optional arguments:
      -h, --help   show this help message and exit
      --version    show version information and exit
      --root ROOT  root directory to manipulate (default: current working directory)

Run `wsb <command> --help` for help about `<command>`. For example, `wsb config --help` for help about `wsb config`.

### Host a scrapbook

Switch current working directory (CWD) to a directory you'd like to host.

    cd /path/to/scrapbook

> In Windows, an additional command or parameter to change drive may be required. For example, if the directory to host is `E:\path\to\scrapbook` while the current drive is `C`, an additional command `E:` (or parameter `/d`) is required besides `cd E:\path\to\scrapbook`.
>
> You can also use the shortcurt: `Shift + Right-click` on the desired folder and select `Open command window here` or `Open PowerShell window here`.

Generate config files for the directory:

    wsb config -ba

> This step can be skipped if you want PyWebScrapBook default data structure instead. See [doc wiki](https://github.com/danny0838/webscrapbook/wiki/Backend) for more details.

Run the generated `.wsb/serve.py` to start the server, or run below command from CLI:

    wsb serve

### Open archive file directly

The `wsbview` executable supports opening an archive page (HTZ or MAFF) to view in the browser.

Run `which wsbview` (or `where wsbview` in Windows) from CLI to get the path of `wsbview` executable, and set default application of MAFF/HTZ file to that executable to open them directly in the browser with double-click.

### Configuration

Run `wsb config -be` to edit configs for CWD. For documentation about configs, run `wsb help config`, or [read online](https://github.com/danny0838/PyWebScrapBook/blob/master/webscrapbook/resources/config.md).

### Further documentation

For more tips about how to configure PyWebScrapBook alongside WebScrapBook, visit [the documentation wiki for WebScrapBook](https://github.com/danny0838/webscrapbook/wiki/Backend).
