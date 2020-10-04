"""Package for i18n

Usage:
    from webscrapbook.locales import I18N
    i18n = I18N('en', 'messages')
    i18n('something to translate')

@TODO: Consider using official gettext for i18n.
"""
import importlib
import locale


DEFAULT_LANG = 'en'

PREFIX_LOCALE = '@@ui_locale'
PREFIX_BIDI = '@@bidi_'

BIDI = {
    'ltr': {
        'dir': 'ltr',
        'reversed_dir': 'rtl',
        'start_edge': 'left',
        'end_edge': 'right',
        },
    'rtl': {
        'dir': 'rtl',
        'reversed_dir': 'ltr',
        'start_edge': 'right',
        'end_edge': 'left',
        },
    }


class I18N:
    """An i18n translator
    """
    def __init__(self, lang=None, domain=None):
        """Initialize an i18n translator

        Loads locales/[lang]/[domain].py
        """
        if not lang:
            lang, _ = locale.getdefaultlocale()

        if not domain:
            domain = 'messages'

        self.lang = lang
        self.domain = domain

        lang_parts = lang.split('_')
        langs = ['_'.join(lang_parts[:i]) for i in range(len(lang_parts), 0, -1)]
        if DEFAULT_LANG not in langs:
            langs.append(DEFAULT_LANG)
        self.langs = langs

        translators = {}
        for lang in langs:
            try:
                translator = importlib.import_module(f'.{lang}.{domain}', __package__)
            except ImportError:
                pass
            else:
                translators[lang] = translator
        self.translators = translators

    def __call__(self, name):
        """Search for a translate of the given message name.

        Fallbacks to non-variant, DEFAULT_LANG, and then the original name if
            the searching message is not found. For example:

            zh_TW => zh => en => name

        Also support special entries like the chrome.i18n of browser
            extensions:

            @@ui_locale
            @@bidi_dir
            @@bidi_reversed_dir
            @@bidi_start_edge
            @@bidi_end_edge
        """
        if name == PREFIX_LOCALE:
            return self.lang

        if name.startswith(PREFIX_BIDI):
            try:
                return BIDI[self._get('bidi_dir')][name[len(PREFIX_BIDI):]]
            except KeyError:
                return name

        return self._get(name)
            
    def _get(self, name):
        for lang in self.langs:
            try:
                return getattr(self.translators[lang], name)
            except (KeyError, AttributeError):
                pass
        return name
