import unittest
from functools import partial

from webscrapbook.util.css import CssRewriter


class TestRewrite(unittest.TestCase):
    @staticmethod
    def rewrite_func(url):
        return f'http://example.com/{url}'

    def test_image(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # basic
        input = """body { image-background: url(image.jpg); }"""
        expected = """body { image-background: url("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """body { image-background: url('image.jpg'); }"""
        expected = """body { image-background: url("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """body { image-background: url("image.jpg"); }"""
        expected = """body { image-background: url("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        # keyframes
        input = """\
@keyframes mykeyframe {
from { background-image: url(image.bmp); }
to { background-image: url("image.bmp"); }
}"""
        expected = """\
@keyframes mykeyframe {
from { background-image: url("http://example.com/image.bmp"); }
to { background-image: url("http://example.com/image.bmp"); }
}"""
        self.assertEqual(rewrite(input), expected)

        # keep original spaces
        input = """body{image-background:url(image.jpg);}"""
        expected = """body{image-background:url("http://example.com/image.jpg");}"""
        self.assertEqual(rewrite(input), expected)

        input = """body { image-background: url(  image.jpg  ) ; }"""
        expected = """body { image-background: url(  "http://example.com/image.jpg"  ) ; }"""
        self.assertEqual(rewrite(input), expected)

        input = """body\t{\timage-background\t:\turl(\timage.jpg\t)\t;\t}"""
        expected = """body\t{\timage-background\t:\turl(\t"http://example.com/image.jpg"\t)\t;\t}"""
        self.assertEqual(rewrite(input), expected)

        # keep original case
        input = """body { image-background: URL(image.jpg); }"""
        expected = """body { image-background: URL("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """body { image-background: uRl(image.jpg); }"""
        expected = """body { image-background: uRl("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        # escape quotes
        input = """body { image-background: url('i "like" it.jpg'); }"""
        expected = r"""body { image-background: url("http://example.com/i \"like\" it.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        # skip comments
        input = """/*url(image.jpg)*/"""
        self.assertEqual(rewrite(input), input)

        input = """/*url(image.jpg)*/body { color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body/*url(image.jpg)*/{ color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body {/*url(image.jpg)*/color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color/*url(image.jpg)*/: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color:/*url(image.jpg)*/red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color: red/*url(image.jpg)*/; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color: red;/*url(image.jpg)*/}"""
        self.assertEqual(rewrite(input), input)

        input = """body { color: red; }/*url(image.jpg)*/"""
        self.assertEqual(rewrite(input), input)

    def test_image_ignore_unrelated_pattern(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        input = """div::after { content: "url(image.jpg)" }"""
        self.assertEqual(rewrite(input), input)

        input = """[myattr="url(image.jpg)"] { }"""
        self.assertEqual(rewrite(input), input)

    def test_image_ignore_unrelated_rules(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        input = """@import "file.css";"""
        self.assertEqual(rewrite(input), input)

        input = """@import url("file.css");"""
        self.assertEqual(rewrite(input), input)

        input = """@namespace url("file.css");"""
        self.assertEqual(rewrite(input), input)

        input = """@font-face { font-family: myfont; src: url("file.woff"); }"""
        self.assertEqual(rewrite(input), input)

    def test_image_complicated_cases(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        input = r""".my\"class\" { background-image: url("image.jpg"); }"""
        expected = r""".my\"class\" { background-image: url("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

    def test_font_face(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_font_face_url=self.rewrite_func)

        # basic
        input = """@font-face { font-family: myfont; src: url(file.woff); }"""
        expected = """@font-face { font-family: myfont; src: url("http://example.com/file.woff"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """@font-face { font-family: myfont; src: url('file.woff'); }"""
        expected = """@font-face { font-family: myfont; src: url("http://example.com/file.woff"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """@font-face { font-family: myfont; src: url("file.woff"); }"""
        expected = """@font-face { font-family: myfont; src: url("http://example.com/file.woff"); }"""
        self.assertEqual(rewrite(input), expected)

        # keep original spaces
        input = """@font-face{font-family:myfont;src:url(file.woff);}"""
        expected = """@font-face{font-family:myfont;src:url("http://example.com/file.woff");}"""
        self.assertEqual(rewrite(input), expected)

        input = """@font-face { font-family: myfont; src  : url(  file.woff  )  ; }"""
        expected = """@font-face { font-family: myfont; src  : url(  "http://example.com/file.woff"  )  ; }"""
        self.assertEqual(rewrite(input), expected)

        input = """\t@font-face\t{\tfont-family\t:\tmyfont\t;\tsrc\t:\turl(\tfile.woff\t)\t;\t}"""
        expected = """\t@font-face\t{\tfont-family\t:\tmyfont\t;\tsrc\t:\turl(\t"http://example.com/file.woff"\t)\t;\t}"""
        self.assertEqual(rewrite(input), expected)

        # keep original case
        input = """@font-face { font-family: myfont; src: URL(file.woff); }"""
        expected = """@font-face { font-family: myfont; src: URL("http://example.com/file.woff"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """@font-face { font-family: myfont; src: UrL(file.woff); }"""
        expected = """@font-face { font-family: myfont; src: UrL("http://example.com/file.woff"); }"""
        self.assertEqual(rewrite(input), expected)

        # escape quotes
        input = """@font-face { font-family: myfont; src: url('i"like"it.woff'); }"""
        expected = r"""@font-face { font-family: myfont; src: url("http://example.com/i\"like\"it.woff"); }"""
        self.assertEqual(rewrite(input), expected)

        # skip comments
        input = """/*@font-face{src:url(file.woff)}*/"""
        self.assertEqual(rewrite(input), input)

        input = """/*@font-face{src:url(file.woff)}*/body { color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body/*@font-face{src:url(file.woff)}*/{ color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body {/*@font-face{src:url(file.woff)}*/color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color/*@font-face{src:url(file.woff)}*/: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color:/*@font-face{src:url(file.woff)}*/red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color: red/*@font-face{src:url(file.woff)}*/; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color: red;/*@font-face{src:url(file.woff)}*/}"""
        self.assertEqual(rewrite(input), input)

    def test_font_face_ignore_unrelated_pattern(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_font_face_url=self.rewrite_func)

        input = """div::after { content: "@font-face{src:url(file.woff)}" }"""
        self.assertEqual(rewrite(input), input)

        input = """[myattr="@font-face{src:url(file.woff)}"] { }"""
        self.assertEqual(rewrite(input), input)

    def test_font_face_complicated_cases(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_font_face_url=self.rewrite_func)

        input = r""".my\"class\" { }
@font-face { src: url("file.woff"); }"""
        expected = r""".my\"class\" { }
@font-face { src: url("http://example.com/file.woff"); }"""
        self.assertEqual(rewrite(input), expected)

    def test_import(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_import_url=self.rewrite_func)

        # basic
        input = """@import "file.css";"""
        expected = """@import "http://example.com/file.css";"""
        self.assertEqual(rewrite(input), expected)

        input = """@import 'file.css';"""
        expected = """@import "http://example.com/file.css";"""
        self.assertEqual(rewrite(input), expected)

        input = """@import url(file.css);"""
        expected = """@import url("http://example.com/file.css");"""
        self.assertEqual(rewrite(input), expected)

        input = """@import url('file.css');"""
        expected = """@import url("http://example.com/file.css");"""
        self.assertEqual(rewrite(input), expected)

        input = """@import url("file.css");"""
        expected = """@import url("http://example.com/file.css");"""
        self.assertEqual(rewrite(input), expected)

        # keep original spaces
        input = """@import   "file.css"  ;"""
        expected = """@import   "http://example.com/file.css"  ;"""
        self.assertEqual(rewrite(input), expected)

        input = """@import\t"file.css"\t;"""
        expected = """@import\t"http://example.com/file.css"\t;"""
        self.assertEqual(rewrite(input), expected)

        input = """@import   url(  file.css   )  ;"""
        expected = """@import   url(  "http://example.com/file.css"   )  ;"""
        self.assertEqual(rewrite(input), expected)

        input = """@import\turl(\tfile.css\t)\t;"""
        expected = """@import\turl(\t"http://example.com/file.css"\t)\t;"""
        self.assertEqual(rewrite(input), expected)

        # keep original case
        input = """@import URL(file.css);"""
        expected = """@import URL("http://example.com/file.css");"""
        self.assertEqual(rewrite(input), expected)

        input = """@import URl(file.css);"""
        expected = """@import URl("http://example.com/file.css");"""
        self.assertEqual(rewrite(input), expected)

        # escape quotes
        input = """@import 'I"love"you.css';"""
        expected = r"""@import "http://example.com/I\"love\"you.css";"""
        self.assertEqual(rewrite(input), expected)

        input = """@import url('I"love"you.css');"""
        expected = r"""@import url("http://example.com/I\"love\"you.css");"""
        self.assertEqual(rewrite(input), expected)

        # skip comments
        input = """/*@import url(file.css);*/"""
        self.assertEqual(rewrite(input), input)

        input = """/*@import url(file.css);*/body { color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body/*@import url(file.css);*/{ color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body {/*@import url(file.css);*/color: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color/*@import url(file.css);*/: red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color:/*@import url(file.css);*/red; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color: red/*@import url(file.css);*/; }"""
        self.assertEqual(rewrite(input), input)

        input = """body { color: red;/*@import url(file.css);*/}"""
        self.assertEqual(rewrite(input), input)

    def test_import_ignore_unrelated_pattern(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_import_url=self.rewrite_func)

        input = """div::after { content: "@import url(file.css);" }"""
        self.assertEqual(rewrite(input), input)

        input = """[myattr="@import url(file.css);"] { }"""
        self.assertEqual(rewrite(input), input)

    def test_import_complicated_cases(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_import_url=self.rewrite_func)

        input = r""".my\"class\" { }
@import "file.css";"""
        expected = r""".my\"class\" { }
@import "http://example.com/file.css";"""
        self.assertEqual(rewrite(input), expected)


if __name__ == '__main__':
    unittest.main()
