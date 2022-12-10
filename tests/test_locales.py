import os
import unittest
from unittest import mock

from webscrapbook.locales import I18N

from . import ROOT_DIR

test_root = os.path.join(ROOT_DIR, 'test_locales')
test_dirs = [
    os.path.join(test_root, 'test_general', 'host'),
    os.path.join(test_root, 'test_general', 'user'),
]


class TestI18N(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

    def test_init_lang(self):
        # zh_CN, ch-CN, zh_cn, zh-cn should all work same
        i18n = I18N(test_dirs, 'zh_CN')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
        ])

        i18n = I18N(test_dirs, 'zh-CN')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
        ])

        i18n = I18N(test_dirs, 'zh_cn')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
        ])

        i18n = I18N(test_dirs, 'zh-cn')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh_cn', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
        ])

        # zh_tw => zh => en
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

        # unknown lang => fallback to default
        i18n = I18N(test_dirs, 'wtf')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
            os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
        ])

        # unprovided lang => take default locale
        with mock.patch('locale.getdefaultlocale', return_value=('zh', 'cp950')):
            i18n = I18N(test_dirs)
            self.assertEqual([t.__file__ for t in i18n.translators], [
                os.path.join(test_root, 'test_general', 'host', 'zh', 'messages.py'),
                os.path.join(test_root, 'test_general', 'host', 'en', 'messages.py'),
                os.path.join(test_root, 'test_general', 'user', 'zh', 'messages.py'),
                os.path.join(test_root, 'test_general', 'user', 'en', 'messages.py'),
            ])

    def test_init_domain(self):
        # mydomain
        i18n = I18N([os.path.join(test_root, 'test_domain')], 'zh_TW', 'mydomain')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_domain', 'zh_tw', 'mydomain.py'),
            os.path.join(test_root, 'test_domain', 'zh', 'mydomain.py'),
            os.path.join(test_root, 'test_domain', 'en', 'mydomain.py'),
        ])

        # no domain => defaults to 'messages'
        i18n = I18N([os.path.join(test_root, 'test_domain')], 'zh_TW')
        self.assertEqual([t.__file__ for t in i18n.translators], [
            os.path.join(test_root, 'test_domain', 'zh_tw', 'messages.py'),
            os.path.join(test_root, 'test_domain', 'zh', 'messages.py'),
            os.path.join(test_root, 'test_domain', 'en', 'messages.py'),
        ])

    def test_call(self):
        i18n = I18N(test_dirs, 'zh_CN')
        self.assertEqual(i18n('test'), '测试 host')

        i18n = I18N(test_dirs, 'zh_TW')
        self.assertEqual(i18n('test'), '測試 host')

        i18n = I18N(test_dirs, 'en')
        self.assertEqual(i18n('test'), 'Test host')

    def test_call_args(self):
        i18n = I18N(test_dirs, 'en')
        self.assertEqual(i18n('test_args1', '111', '222', '333'), 'Test 111 222 333')
        self.assertEqual(i18n('test_args2', '111', '222', '333'), 'Test 111 333 222')
        self.assertEqual(i18n('test_args3', a='aaa', b='bbb', c='ccc'), 'Test aaa ccc bbb')

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
