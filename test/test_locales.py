from unittest import mock
import unittest
from webscrapbook.locales import I18N

class TestI18N(unittest.TestCase):
    def test_langs(self):
        i18n = I18N('en')
        self.assertEqual(i18n.lang, 'en')
        self.assertEqual(i18n.langs, ['en'])

        i18n = I18N('en_GB')
        self.assertEqual(i18n.lang, 'en_GB')
        self.assertEqual(i18n.langs, ['en_GB', 'en'])

        i18n = I18N('zh_TW')
        self.assertEqual(i18n.lang, 'zh_TW')
        self.assertEqual(i18n.langs, ['zh_TW', 'zh', 'en'])

    def test_call01(self):
        i18n = I18N('zh_TW')
        self.assertEqual(i18n('MyMessage'), 'MyMessage')

    def test_special(self):
        i18n = I18N('zh_TW')
        self.assertEqual(i18n('@@ui_locale'), 'zh_TW')
        self.assertEqual(i18n('@@bidi_dir'), 'ltr')
        self.assertEqual(i18n('@@bidi_reversed_dir'), 'rtl')
        self.assertEqual(i18n('@@bidi_start_edge'), 'left')
        self.assertEqual(i18n('@@bidi_end_edge'), 'right')

        i18n = I18N('ar')
        self.assertEqual(i18n('@@ui_locale'), 'ar')
        self.assertEqual(i18n('@@bidi_dir'), 'rtl')
        self.assertEqual(i18n('@@bidi_reversed_dir'), 'ltr')
        self.assertEqual(i18n('@@bidi_start_edge'), 'right')
        self.assertEqual(i18n('@@bidi_end_edge'), 'left')

if __name__ == '__main__':
    unittest.main()
