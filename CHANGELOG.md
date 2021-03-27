# Changelog
* This project generally follows [semantic versioning](https://semver.org/). For a version `x.y.z`, `x` means a major (backward incompatible) change, `y` means a minor (backward compatible) change, and `z` means a patch (bug fix). Few versions may not strictly follow this rule due to historical reasons, though.
* Versions before 1.0 are in initial development. APIs are not stable for these versions, even a `y` version can involve a breaking change, and only partial notable changes are summarized in this document. See full commit history in the source repository for details.
* Client requirement in this document refers to the version of [`WebScrapBook`](https://github.com/danny0838/webscrapbook) browser extension.

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
