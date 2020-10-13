from unittest import mock
import unittest
import os
from webscrapbook.locales import I18N

root_dir = os.path.abspath(os.path.dirname(__file__))
test_root = os.path.join(root_dir, 'test_locales')
test_dirs = [
    os.path.join(test_root, 'test_general', 'host'),
    os.path.join(test_root, 'test_general', 'user'),
    ]

class TestI18N(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def test_init(self):
        # zh_CN, ch-CN, zh_cn, zh-cn should all work same
        i18n = I18N(test_dirs, 'zh_CN', 'messages')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

        i18n = I18N(test_dirs, 'zh-CN', 'messages')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

        i18n = I18N(test_dirs, 'zh_cn', 'messages')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

        i18n = I18N(test_dirs, 'zh-cn', 'messages')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

        # zh_tw => zh => en
        i18n = I18N(test_dirs, 'zh_TW', 'messages')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

        # no domain => defaults to 'messages'
        i18n = I18N(test_dirs, 'zh_TW')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

        # en
        i18n = I18N(test_dirs, 'en')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

        # unknown lang should fallback to default
        i18n = I18N(test_dirs, 'wtf')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

    def test_call(self):
        i18n = I18N(test_dirs, 'zh_CN')
        self.assertEqual(i18n('test'), '测试 host')

        i18n = I18N(test_dirs, 'zh_TW')
        self.assertEqual(i18n('test'), '測試 host')

        i18n = I18N(test_dirs, 'en')
        self.assertEqual(i18n('test'), 'Test host')

    def test_call_missing(self):
        i18n = I18N(test_dirs, 'zh_TW')
        self.assertEqual(i18n('MyMessage'), 'MyMessage')

    def test_special(self):
        i18n = I18N([os.path.join(test_root, 'test_special')], 'zh_TW')
        self.assertEqual(i18n('@@ui_locale'), 'zh_tw')
        self.assertEqual(i18n('@@bidi_dir'), 'ltr')
        self.assertEqual(i18n('@@bidi_reversed_dir'), 'rtl')
        self.assertEqual(i18n('@@bidi_start_edge'), 'left')
        self.assertEqual(i18n('@@bidi_end_edge'), 'right')

        i18n = I18N([os.path.join(test_root, 'test_special')], 'ar')
        self.assertEqual(i18n('@@ui_locale'), 'ar')
        self.assertEqual(i18n('@@bidi_dir'), 'rtl')
        self.assertEqual(i18n('@@bidi_reversed_dir'), 'ltr')
        self.assertEqual(i18n('@@bidi_start_edge'), 'right')
        self.assertEqual(i18n('@@bidi_end_edge'), 'left')

if __name__ == '__main__':
    unittest.main()
