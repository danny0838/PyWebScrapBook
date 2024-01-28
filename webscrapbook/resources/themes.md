## Customize a theme

A custom theme can be defined at `<root>/.wsb/themes/<name>`, which contains:
- a `templates` sub-directory for template files;
- a `static` sub-directory for static files;
- a `locales` sub-directory for localizations.

The `<name>` should match the `app.theme` config.

If the custom theme has the same name as the built-in one, the application
will look up for a resource first from the custom one and fallback to the
default one when not found.


## `templates`

Used to format the HTML output. It should follow HTML5 standard and can use
Jinja2 syntax for templating.


## `static`

The resource files used by the template. The file `example.css` under the
`static` sub-directory will be mapped as `/example.css?a=static` (if the
application is hosted at root directory), and can generally be referenced
using the template function like `{{ static_url('example.css') }}` in a
template.


## `locales`

Localized strings can be defined under the `locales` sub-directory. The locale
name should follow RFC 1766 and be normalized as all lower case and use `_` as
the subtag separator. For example, a directory named `en_us` will be searched
if the `app.locale` config value is `en_US`, `en-US`, `en_us`, `en-us`, or so.

The localized string for entry `mykey = 'My message'` can be referenced using
the template function like `{{ i18n('mykey') }}` in a template. It can also
contain placeholders using Python `str.format()` syntax to format the string
for a call with arguments.
