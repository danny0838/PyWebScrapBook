from unittest import mock
import unittest
from webscrapbook.util.html import Markup, MarkupTag

class Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = 8192

class TestMarkupTag(Test):
    def test_html01(self):
        m = MarkupTag(
            type='starttag',
            tag='input',
            attrs=[
                ('type', 'checkbox'),
                ('checked', None),
                ],
            )
        self.assertEqual(str(m), '<input type="checkbox" checked>')

    def test_html02(self):
        m = MarkupTag(
            type='starttag',
            tag='div',
            attrs=[
                ('title', '中文<span title="foo">bar</span>'),
                ],
            )
        self.assertEqual(str(m), '<div title="中文&lt;span title=&quot;foo&quot;&gt;bar&lt;/span&gt;">')

    def test_xhtml01(self):
        m = MarkupTag(
            is_xhtml=True,
            type='starttag',
            tag='input',
            attrs=[
                ('type', 'checkbox'),
                ('checked', None),
                ],
            is_self_end=True,
            )
        self.assertEqual(str(m), '<input type="checkbox" checked="checked" />')

    def test_xhtml02(self):
        m = MarkupTag(
            is_xhtml=True,
            type='starttag',
            tag='div',
            attrs=[
                ('title', '中文<span title="foo">bar</span>'),
                ],
            )
        self.assertEqual(str(m), '<div title="中文&lt;span title=&quot;foo&quot;&gt;bar&lt;/span&gt;">')

if __name__ == '__main__':
    unittest.main()
