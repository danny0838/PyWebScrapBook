# Changelog
* This project generally follows [semantic versioning](https://semver.org/). For a version `x.y.z`, `x` means a major (backward incompatible) change, `y` means a minor (backward compatible) change, and `z` means a patch (bug fix). Few versions may not strictly follow this rule due to historical reasons, though.
* Versions before 1.0 are in initial development. APIs are not stable for these versions, even a `y` version can involve a breaking change, and only partial notable changes are summarized in this document. See full commit history in the source repository for details.
* Client requirement in this document refers to the version of [`WebScrapBook`](https://github.com/danny0838/webscrapbook) browser extension.

## [2.3.2] - 2024-03-13
* Fixed bad CSS rewriting for a bad URL token or a URL with escaped newlines or certain escaped control chars when converting an item to single_file format.

## [2.3.1] - 2024-03-10
* Fixed bad CSS rewriting when converting an item to single_file format.

## [2.3.0] - 2024-01-31
* Improved MIME types handling:
  * Fixed bad MIME to file extention conversion in some platforms.
  * The user config is now allowed to overwrite the patch rules of WebScrapBook.
* Reworked internal constants `WSB_USER_DIR` and `WSB_USER_CONFIG` to be the subpath under the user home directory and can be overwritten by the environment variables.
* Miscellaneous code optimization.

## [2.2.0] - 2024-01-24
* Fixed bad handling of ID-datetime conversion for some rare cases.
* Added support for salted hash when caching authorization information for better security.

## [2.1.0] - 2024-01-19
* Added support of opening an archive file using the `wsb` executable.
* When viewing archive files, no more deduplicate the provided paths and use the original case for them.
* Deprecated the `webscrapbook` and `wsbview` executables: use `wsb` instead.
* Fixed bad encoding for the indexer and some CLI utilities in some cases.
* Fixed timestamp handling issues, which may crash the server, for the default theme.

## [2.0.1] - 2023-06-17
* Bumped client requirement to >= 2.0.1.
* Added CLI and web API for scrapbook querying and searching.
* Added support of `book.*.new_at_top` config.
* Reworked `cache` API: added `book.*.inclusive_frames`, `book.*.static_index`, `book.*.rss_root`, and `book.*.rss_item_count` configs and `--rss` option in place of the `--inclusive-frames`, `--rss-root`, and `--rss-item-count` options.
* Reworked `cache` and `convert items` CLI utilities to support specifying items for each book.
* Reworked `export` and `import` with new version 2 archive file format, which supports better tree reconstruction for multi-referenced items, and fixed many issues.
* Reworked `encrypt` and authorization related configs to support stronger password protection.
* Reworked internal API for several modules.
* Miscellaneous bug fixes, documentation improvement, and optimization and refactoring of the source code and the unittest suite.

## [1.16.0] - 2023-06-04
* Fixed some potential errors for the unittest suite.
* Fixed inconsistent MIME type for `*.swf` files on some platforms.
* No more adjust the timestamp of the imported files automatically.

## [1.15.0] - 2023-05-31
* Updated dependency to `Flask >= 2.0.0` and `Werkzeug >= 2.0.1`.
* Fixed some compatibility issues for Werkzeug >= 2.3.

## [1.14.1] - 2023-05-22
* Fixed a potential error for the converter when the output directory doesn't exist.

## [1.14.0] - 2023-05-21
* Info files in an exported archive file are now compressed.
* Miscellaneous optimization and refactoring of the source code and the unittest suite.

## [1.13.2] - 2023-05-17
* Fixed an issue that importing an archive file with '*/index.html' as index gets a bad cached icon path.

## [1.13.1] - 2023-05-10
* Fixed an issue that importing archive files of a multi-referenced item using "new" mode gets duplicated items.
* Improved the documentation about the `export`/`import` command.

## [1.13.0] - 2023-05-08
* Fixed an issue that `*/index.html` are always added after `*.htz`, `*.maff`, `*.html` in the same directory when adding unindexed files by the checker.
* Fixed an issue that a support folder may be incorrectly handled on a case sensitive filesystem when checking for unindexed files.
* Fixed an issue that the icon property may be incorrect when importing an item into a different book.
* Miscellaneous optimization and refactoring of the source code.

## [1.12.2] - 2023-05-07
* Fixed an issue that an error message is shown when caching an empty web page.
* Fixed an issue that an exported archive with a bad version is not rejected on import.

## [1.12.1] - 2023-05-05
* Fixed a potential issue of bad directory moving.
* Miscellaneous optimization and refactoring of the source code and the unittest suite.

## [1.12.0] - 2023-04-29
* Improved handling of boolean options for CLI.
* Improved the output of some CLI commands.
* Static site pages now are generated using the config locale if not otherwise specified.
* JavaScript files now use `text/javascript` as MIME type.
* Fixed a potential backup error in certain rare cases.
* Fixed the output format for server sent events when an unexpected error occurred.
* Fixed and improved some documentation.
* Miscellaneous optimization and refactoring of the source code and the unittest suite.

## [1.11.0] - 2023-04-10
* Fixed and updated the search page:
  * Fixed outdated browser support information.
  * `create:` and `modify:` conditions are now "or"-connected.
  * `book:` conditions are now matched by book ID.
  * Search results are now shown in the order of provided `book:` conditions.
  * A bad input for `sort:` and `limit:` is now forbidden.
* Fixed bad response for a user without read permission when visiting with an unknown action.

## [1.10.1] - 2023-04-08
* Fixed a packaging error causing a missing subpackage.

## [1.10.0] - 2023-04-08
* Fixed a web interface issue that moved or copied files are misplaced if the target directory has a subdirectory with same name.
* Fixed an issue that downoloading a collection in a ZIP may get a bad filename.
* Fixed an issue that a file or directory can be unrestrictedly created at a subpath of a file in a ZIP.
* Fixed an issue that a directory can be unrestrictedly moved to a path under self and causes a further error in some cases.
* Fixed an issue that permissions are not preserved when copying a directory into a ZIP.
* Fixed an issue that metadata are not preserved when modifying a file in a ZIP.
* A directory entry is now generated at the target if there is no explicit directory entry when creating a directory in a ZIP.
* Locale now defaults to "en" if not defined, to prevent an issue of using a deprecated API.
* Fixed a packaging issue causing unusable test files be included in a source distribution.
* Improved packinging configs and scripts.
* Miscellaneous API error fix, documentation improvement, and code optimization and refactoring.

## [1.9.0] - 2023-03-26
* Suppoort streaming when downloading multiple files/directories as a ZIP.
* Miscellaneous documentation improvements and code optimization.

## [1.8.3] - 2023-03-08
* Fixed remote detection of `[::1]` for the generated search page.
* Fixed some incomplete localizations.

## [1.8.2] - 2023-02-21
* Fixed script error when checking an HTML file containing a `link` tag without `rel` attribute when running the indexer.

## [1.8.1] - 2023-01-20
* Fixed an issue that the `.wsb` directory under the `top_dir` of a scrapbook is not ignored when running the checker.
* Fixed script error when a bad HTML file is encountered when running the indexer.

## [1.8.0] - 2023-01-14
* Added localication for Spanish (es).
* Adjusted filename tidying strategy:
  * Spaces, tabs, and linefeeds are now collapsed into a space.
  * "<", and ">" are now translated into "_".
  * "%"s are no more encoded when forcing ASCII.
  * Fix bad handling for a filename like " .ext".
  * Windows preserved filenames like "CON" and "NUL.txt" are now renamed.

## [1.7.0] - 2022-12-11
* Dropped support for Python 3.6.
* Locale now searches for all given directories before checking for the next fallback language.
* Fixed a script error when the default locale cannot be determined by the system.
* Miscellaneous code optimization.
* Fixed several potential errors.
* Fixed several random errors for tests.

## [1.6.1] - 2022-08-28
* Updated classifiers and some documentation for the package.
* Fixed some packaging issues that may cause obsolete files be included.
* Some filename and coding style changes to meet the general conventions.

## [1.6.0] - 2022-03-19
* No more allow a theme name to contain invalid filename characters.
* Fixed an issue that some control chars in a filename are not correctly handled.
* Fixed an issue that ZIP comment may be missing after a modification of its content.
* Miscellaneous internal API changes and code optimization.

## [1.5.0] - 2022-03-14
* Changes of Backend server API:
  * `delete` at root path now deletes all entries in a ZIP.
  * No more allow creating a folder if a file with the same path exists in a ZIP, and vise versa.
  * Fixed an issue that a path like "/", "foo//bar", "foo/./bar", "foo/../bar", etc., is sometimes not tidied before further processing.
* Improved the default theme of the web interface:
  * No more allow creating a file or ZIP if anything exists at the target.
  * No more list invalid entries in a ZIP.
  * Commands now use canonical path in the error message.
* Miscellaneous internal API changes and code optimization.

## [1.4.2] - 2022-03-12
* Improved documentation about converters.
* Improved some test code to prevent occasional false failures.

## [1.4.1] - 2022-03-08
* Added a missing i18n entry for the default theme of the web interface.

## [1.4.0] - 2022-03-07
* Changes of Backend server API:
  * `info` action now returns "dir" type for an implicit ZIP directory.
  * `move` or `copy` actions now accepts a directory as the target.
* Improved the default theme of the web interface:
  * Added support of i18n.
  * Added support of selection and commands in all view modes.
  * Added a hint for current selection count.
  * Added support of responsive media sizing for gallery view mode.
  * No more open link in new tab for the gallery view mode.
  * Preview is now an individual mode and can be combined with any other view mode.
  * Clicking a directory link now jumps into the directory when preview is enabled.
  * The previewed media now always fits in the viewport.
  * The current view mode is now remembered when jumps into another directory.
  * Added support of moving/copying/linking a single entry at a folder.
  * No more allow creating a link at an existing path.
  * No more force special view for an `*.htd` directory when there's any query or hash in the URL.
  * Added accesskey for common selectors and buttons.
  * Miscellaneous data scheme changes, UI improvements, bug fixes, and code optimization.

## [1.3.2] - 2022-03-02
* Fixed some issues of the previewer of the default theme of the web interface:
  * Fixed possible code conflict after the previewer mode has been toggled repeatedly.
  * Fixed layout error for rtl direction.

## [1.3.1] - 2022-02-28
* Fixed token error during uploading through the default theme of the web interface when not hosted at root path.

## [1.3.0] - 2022-02-28
* Improved the default theme of the web interface:
  * Added `upload folder` command.
  * Added support of uploading files and directories through drag-and-drop.
  * Command selector is now disabled when a command is running.
  * Moving a media in preview mode now shows a tooltip.
  * Fixed zooming error for some SVG images in preview mode.

## [1.2.0] - 2022-02-27
* Added MIME type support for WebP and WebM files.
* Fixed incorrect API messages.
* Improved the default theme of the web interface:
  * Added a tools selector for operations like selecting, expanding, filtering, etc.
  * Added new `Preview mode` in place of `List view`.
  * Added new `Gallery mode (+media)`, and `Gally mode` now shows images without preloading media.
  * Added support for more file types.
  * Fixed path error in certain cases for commands.
  * Improved the error messages for commands.

## [1.1.0] - 2021-12-10
* Dropped support of config `app.base`.
* Fixed an issue that the mimetype of `.js` becomes `application/x-javascript` in some environment.
* Fixed several errors of unit tests.

## [1.0.0] - 2021-12-07
* Bumped version to 1.0.*.

## [0.48.0] - 2021-11-13
* Updated converted CSS for `wsb convert migrate`.

## [0.47.0] - 2021-11-09
* Load item icons lazily for generated static site files.

## [0.46.0] - 2021-11-04
* Expose `backup_dir` config to the client if it's web accessible.
* `backup` and `unbackup` actions now return the target directory name.

## [0.45.0] - 2021-10-25
* Added support of HTZ, MAFF, and single HTML formats for the `migrate` converter.

## [0.44.2] - 2021-09-21
* Fixed a compatibility issue for saved tree data with old browsers not supporting ES2019.

## [0.44.1] - 2021-05-16
* Fulltext cache no more include text content in `<textarea>` or `<template>` tags.
* Fixed potential bad handling of `<frame>` tags for converters.

## [0.44.0] - 2021-05-08
* Added support of `single_file` format for `items` converter.
* Added support of more common MIME types.
* Fixed translation of certain common MIME types to a fixed file extension.
* Fixed several get_meta_refresh errors in Python 3.6.
* Fixed several test errors.

## [0.43.0] - 2021-05-04
* Added support of custom MIME types mapping using `~/.config/wsb/mime.types`.
* Added `wsb help mimetypes` for documentation about customizing MIME types mapping.
* Added support of some common MIME types.
* Reworked handling of some HTTP headers and HTML attributes to conform with the spec better.
* Fixed an issue that meta charset be ignored when parsing a meta refresh.
* `items` converter now preserves file metadata for the generated HTZ or MAFF files.
* Fixed incorrect icon path after a conversion of the `items` converter.
* `wsb2sb` converter no more changes the linefeed format for output files.
* Fixed potential bad handling of XHTML files for the `wsb2sb` converter.
* Fixed incorrect rewriting of content in special tags like `<template>`, `<xmp>`, etc., for `migrate` and `items` converters.

## [0.42.0] - 2021-05-01
* Added support of migrating several older WebScrapBook data for the `migrate` converter. The behavior can be switched with `--convert-*` options.
* `migrate` converter no more changes the linefeed format for output files.
* Adjusted log message format of several utilities.
* Fixed missing support of hash in source URL for the generated static index file.
* Fixed a potential error when converting a legacy ScrapBook ID with the `migrate` converter.
* Fixed an issue of generating extra loader elements if one exists for the `migrate` converter.
* Fixed potential bad handling of XHTML files for the `migrate` converter.

## [0.41.0] - 2021-04-27
* Hash part of source URL is now considered when viewing an item in the generated map file.
* Added support of `limit:` command for search page.
* Added `items` converter.

## [0.40.0] - 2021-04-17
* `server.browse` now defaults to `false`.

## [0.39.0] - 2021-04-12
* Fixed a security issue that may allow the user to access any directory on Windows.
* Fixed an issue that `file2wsb` converter does not handle a page named `index.html` with a support folder.
* No more generate a title from ID if title is empty for the checker and some converters.
* `file2wsb` converter now generates an item for every normal file.
* `file2wsb` converter now preserves the original filename by default, with an added `--no-preserve-filename` option to tweak the behavior.

## [0.38.0] - 2021-04-11
* Fixed an issue of crash for `check` if a page has an empty title.
* Renamed converter `migrate0` to `migrate`.
* Added `app.locale` config to determine the locale of the APP theme.
* Added support of downloading a folder or files and folders under a folder for the web interface.
* Added `--data-folder-suffixes` and `--ignore-*-meta` options for `file2wsb` converter.

## [0.36.0] - 2021-04-01
* Fixed an issue that auto backup may not include a deleted file.
* Added support of note for a backup.
* Added support for `unbackup` action.

## [0.35.2] - 2021-03-30
* Fixed an issue that backup does not work for `sb2wsb` converter if input path is not absolute.

## [0.35.0] - 2021-03-27
* Fixed an issue that fulltext cache does not work for iframes with srcdoc attribute. (Rebuild the fulltext cache to correct existing caches.)
* Added support of page conversion for `sb2wsb` and `wsb2sb` converters.
* Added `migrate0` converter.

## [0.32.0] - 2020-11-05
* Added `file2wsb` and `wsb2file` converters.

## [0.30.0] - 2020-10-29
* ID for item added by `wsb check --resolve-unindexed-files` is now always in standard format.

## [0.29.0] - 2020-10-27
* Added support for `backup` action.
* Fixed potential ID overwriting for item added by `wsb check --resolve-unindexed-files`.

## [0.28.0] - 2020-10-26
* Fixed a conversion error between "site" and legacy "combine" item type.
* Fixed a conversion error that wsb2sb converter converts an item other than "" type with marked property to "marked" type.
* Added support to convert data file between "postit" and legacy "note" item type.
* Added `app.backup_dir` config.

## [0.27.2] - 2020-10-26
* Fixed bad ID for item added by `wsb check --resolve-unindexed-files`.

## [0.26.0] - 2020-10-14
* Dropped support for `recursive` parameter of `list` server action.
* Added support of top-level None value for *.js tree files.

## [0.25.0] - 2020-10-12
* Added `export` and `import` command.
* Moved config `browser.index` to `app.index`.

## [0.24.0] - 2020-10-09
* Added `convert wsb2sb` command.

## [0.23.0] - 2020-10-05
* Bumped client requirement to >= 0.79.
* Adjusted locking mechanism:
  * A lock is now created under `.wsb/locks` instead of `.wsb/server/locks`.
  * A lock is now created as a file instead of a folder.
  * A lock is now created with an ID, and can be extended using the same ID. Releasing a lock now requires its ID.
  * The server now responses 503 rather than 500 for a timeout of `lock` server action.
* Added `cache`, `check`, and `convert` commands.

## [0.22.0] - 2020-09-22
* Removed shebang for script files.

## [0.21.0] - 2020-09-16
* A lock is now created using a hashed filename instead of a plain filename.

## [0.20.0] - 2020-09-13
* Added content security policy restriction for served web pages. They can no longer send AJAX requests and form actions to prevent a potential attack. A config `app.content_security_policy` is added to change the behavior.

## [0.18.1] - 2020-09-08
* Installation requirement is now declared as Python >= 3.6. Note that version compatibility is not thoroughly checked for prior versions, and some functionalities are known to break in Python < 3.7 for some versions despite marked as installable.
* Response of a server`config` action now exposes a new `WSB_EXTENSION_MIN_VERSION` value, which informs the client to apply self version checking.

## [0.17.0] - 2020-08-27
* Bumped client requirement to >= 0.75.6.
* Bumped requirement of `werkzeug` to >= 1.0.0.
* Removed `cryptography` from installation requirement. It is now an optional requirement (for ad hoc SSL key generating).
* Fixed a bug for zip editing through server actions in Python < 3.7.
* Response 404 rather than 400 for `list` server action when the directory is not found.
* Added unit tests.

## [0.15.0] - 2020-04-12
* Tokens are now created under `.wsb/server/tokens` instead of `.wsb/server/token`.

## [0.14.0] - 2020-04-01
* Switched backend server framework to `Flask` from `Bottle`.
* Added support for `app.allow_x_*` configs to prevent issues when serving behind a reverse proxy.
* Dropped support for `server.ssl_pw` config.

## [0.11.0] - 2020-01-14
* Added support of zip editing through server actions.

## [0.8.0] - 2019-09-01
* Added support for `book.*.no_tree` config.

## [0.6.0] - 2019-04-14
* Added `lock` and `unlock` actions.
* Merged `upload` action into `save`.

## [0.4.0] - 2019-04-06
* Added `wsbview` CLI executable.

## [0.1.5] - 2019-03-14
* First public release.
