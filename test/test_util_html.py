from unittest import mock
import unittest
import os
from webscrapbook.util.html import Markup, MarkupTag, HtmlRewriter

root_dir = os.path.abspath(os.path.dirname(__file__))

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

class TestHtmlRewriter(Test):
    def test_load_html_markups_html(self):
        # HTML5
        markups = HtmlRewriter().load(os.path.join(root_dir, 'test_util_html', 'load_html_markups', 'sample.html'))
        with open(os.path.join(root_dir, 'test_util_html', 'load_html_markups', 'sample.html'), encoding='UTF-8', newline='\n') as fh:
            input = fh.read()
        with open(os.path.join(root_dir, 'test_util_html', 'load_html_markups', 'sample.expected.html'), encoding='UTF-8', newline='\n') as fh:
            expected = fh.read()
        self.assertEqual(''.join(str(m) for m in markups if not m.hidden), input)
        self.assertEqual(''.join(str(m) for m in markups), expected)
        for m in markups:
            self.assertFalse(m.is_xhtml)

    def test_load_html_markups_xhtml(self):
        # XHTML
        markups = HtmlRewriter(is_xhtml=True).load(os.path.join(root_dir, 'test_util_html', 'load_html_markups', 'sample.xhtml'))
        with open(os.path.join(root_dir, 'test_util_html', 'load_html_markups', 'sample.xhtml'), encoding='UTF-8', newline='\n') as fh:
            input = fh.read()
        with open(os.path.join(root_dir, 'test_util_html', 'load_html_markups', 'sample.expected.xhtml'), encoding='UTF-8', newline='\n') as fh:
            expected = fh.read()
        self.assertEqual(''.join(str(m) for m in markups if not m.hidden), input)
        self.assertEqual(''.join(str(m) for m in markups), expected)
        for m in markups:
            self.assertTrue(m.is_xhtml)

    def test_load_html_markups_html_reserialized(self):
        # HTML5
        markups = HtmlRewriter().load(os.path.join(root_dir, 'test_util_html', 'load_html_markups_reserialized', 'sample.html'))
        with open(os.path.join(root_dir, 'test_util_html', 'load_html_markups_reserialized', 'sample.html'), encoding='UTF-8', newline='\n') as fh:
            input = fh.read()
        with open(os.path.join(root_dir, 'test_util_html', 'load_html_markups_reserialized', 'sample.expected.html'), encoding='UTF-8', newline='\n') as fh:
            expected = fh.read()
        for m in markups:
            m.src = None
        self.assertEqual(''.join(str(m) for m in markups), expected)

    def test_load_html_markups_xhtml_reserialized(self):
        # XHTML
        markups = HtmlRewriter(is_xhtml=True).load(os.path.join(root_dir, 'test_util_html', 'load_html_markups_reserialized', 'sample.xhtml'))
        with open(os.path.join(root_dir, 'test_util_html', 'load_html_markups_reserialized', 'sample.xhtml'), encoding='UTF-8', newline='\n') as fh:
            input = fh.read()
        with open(os.path.join(root_dir, 'test_util_html', 'load_html_markups_reserialized', 'sample.expected.xhtml'), encoding='UTF-8', newline='\n') as fh:
            expected = fh.read()
        for m in markups:
            m.src = None
        self.assertEqual(''.join(str(m) for m in markups), expected)



if __name__ == '__main__':
    unittest.main()
