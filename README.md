PyWebScrapBook is a command line toolkit and backend server for
[WebScrapBook browser extension](https://github.com/danny0838/webscrapbook).

## Features
* Host any directory as a website.
* HTZ or MAFF archive file viewing.
* Markdown file rendering.
* Directory listing.
* Create, view, edit, and/or delete files  via the web page or API.
* HTTP(S) authorization.

## Usage

### Install Python

Install Python >= 3.5 from the [official site](https://www.python.org).

Add python to PATH so that it can be run from the command line interface (CLI).

### Install this package

Run below command from CLI to install:

    python -m pip install webscrapbook

After installation, `wsb` or `webscrapbook` will be available from the CLI.

### Host a scrapbook

Switch current working directory (CWD) to a directory you'd like to host.

    cd /path/to/scrapbook

Generate config files for the directory:

    wsb config -ba

Run `.wsb/serve.py` to start the server, or run below command from CLI:

    wsb serve

### Further documentation

Run below command for further help:

    wsb --help
