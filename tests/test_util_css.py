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

        input = """body { image-background: url(  "image.jpg"  ) ; }"""
        expected = """body { image-background: url(  "http://example.com/image.jpg"  ) ; }"""
        self.assertEqual(rewrite(input), expected)

        input = """body { image-background: url(\t"image.jpg"\t) ; }"""
        expected = """body { image-background: url(\t"http://example.com/image.jpg"\t) ; }"""
        self.assertEqual(rewrite(input), expected)

        # keep original case
        input = """body { image-background: URL(image.jpg); }"""
        expected = """body { image-background: URL("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """body { image-background: uRl(image.jpg); }"""
        expected = """body { image-background: uRl("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """body { image-background: URL("image.jpg"); }"""
        expected = """body { image-background: URL("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        input = """body { image-background: uRl("image.jpg"); }"""
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

        # don't break normal rewriting
        input = r""".my\"class\" { background-image: url("image.jpg"); }"""
        expected = r""".my\"class\" { background-image: url("http://example.com/image.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

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

    def test_image_char_escape_or_replace(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # 0x01~0x1F and 0x7F (except for newlines) should be escaped
        input = """.mycls { background-image: url("\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0B\x0E\x0F"); }"""
        expected = r""".mycls { background-image: url("http://example.com/\1 \2 \3 \4 \5 \6 \7 \8 \9 \b \e \f "); }"""
        self.assertEqual(rewrite(input), expected)

        input = """.mycls { background-image: url("\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1A\x1B\x1C\x1D\x1E\x1F\x7F"); }"""
        expected = r""".mycls { background-image: url("http://example.com/\10 \11 \12 \13 \14 \15 \16 \17 \18 \19 \1a \1b \1c \1d \1e \1f \7f "); }"""
        self.assertEqual(rewrite(input), expected)

        # escaped sequence of 0x01~0x1F and 0x7F should keep escaped
        input = r""".mycls { background-image: url("\1 \2 \3 \4 \5 \6 \7 \8 \9 \a \b \c \d \e \f "); }"""
        expected = r""".mycls { background-image: url("http://example.com/\1 \2 \3 \4 \5 \6 \7 \8 \9 \a \b \c \d \e \f "); }"""
        self.assertEqual(rewrite(input), expected)

        input = r""".mycls { background-image: url("\10 \11 \12 \13 \14 \15 \16 \17 \18 \19 \1a \1b \1c \1d \1e \1f \7f "); }"""
        expected = r""".mycls { background-image: url("http://example.com/\10 \11 \12 \13 \14 \15 \16 \17 \18 \19 \1a \1b \1c \1d \1e \1f \7f "); }"""
        self.assertEqual(rewrite(input), expected)

        # null, surrogate, and char code > 0x10FFFF should be replaced with \uFFFD
        input = r""".mycls { background-image: url("\0 \D800 \DFFF \110000"); }"""
        expected = """.mycls { background-image: url("http://example.com/\uFFFD\uFFFD\uFFFD\uFFFD"); }"""
        self.assertEqual(rewrite(input), expected)

        # other chars should be unescaped
        input = r""".mycls { background-image: url("\80 \4E00 \20000 \10FFFF "); }"""
        expected = """.mycls { background-image: url("http://example.com/\u0080\u4E00\U00020000\U0010FFFF"); }"""
        self.assertEqual(rewrite(input), expected)

    @unittest.expectedFailure
    def test_image_quoted_string_extra_comps(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad URL, should be skipped
        input = r""".mycls { background-image: url("image.jpg"foo); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url("image.jpg" foo); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url("image.jpg""foo"); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url("image.jpg" "foo"); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url("image.jpg"'foo'); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url("image.jpg" 'foo'); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url("image.jpg" url(foo)); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url("image.jpg" url("foo")); }"""
        self.assertEqual(rewrite(input), input)

    def test_image_quoted_string_newline(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad string, should be skipped
        input = r""".mycls { background-image: url("image.jpg
); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url('image.jpg
); }"""
        self.assertEqual(rewrite(input), input)

    @unittest.expectedFailure
    def test_image_quoted_string_escaped_newline(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # escaped newlines should be stripped
        input = r""".mycls { background-image: url("my\
image\
.jpg"); }"""
        expected = r""".mycls { background-image: url("http://example.com/myimage.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

        input = r""".mycls { background-image: url('my\
image\
.jpg'); }"""
        expected = r""".mycls { background-image: url("http://example.com/myimage.jpg"); }"""
        self.assertEqual(rewrite(input), expected)

    @unittest.expectedFailure
    def test_image_quoted_string_eof(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad string, should be skipped to the end
        input = r""".mycls { background-image: url("img.jpg"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url("url(img.jpg)"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url('img.jpg"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url('url(img.jpg)"""
        self.assertEqual(rewrite(input), input)

    @unittest.expectedFailure
    def test_image_quoted_string_escaped_eof(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad string, should be skipped to the end
        input = """.mycls { background-image: url("img.jpg\\"""
        self.assertEqual(rewrite(input), input)

        input = """.mycls { background-image: url("url(img.jpg)\\"""
        self.assertEqual(rewrite(input), input)

        input = """.mycls { background-image: url('img.jpg\\"""
        self.assertEqual(rewrite(input), input)

        input = """.mycls { background-image: url('url(img.jpg)\\"""
        self.assertEqual(rewrite(input), input)

    @unittest.expectedFailure
    def test_image_unquoted_string_bad_chars(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad URL, should be skipped
        input = r""".mycls { background-image: url(image"foo.jpg); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url(image"foo".jpg); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url(image'foo.jpg); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url(image'foo'.jpg); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url(image(foo.jpg); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url(url(foo).jpg); }"""
        self.assertEqual(rewrite(input), input)

    def test_image_unquoted_string_newline_last(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # last whitespaces, should be stripped
        input = r""".mycls { background-image: url(image.jpg
); }"""
        expected = r""".mycls { background-image: url("http://example.com/image.jpg"
); }"""
        self.assertEqual(rewrite(input), expected)

    @unittest.expectedFailure
    def test_image_unquoted_string_newline_intermediate(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad url, should be skipped
        input = r""".mycls { background-image: url(image.jpg
foo); }"""
        self.assertEqual(rewrite(input), input)

    def test_image_unquoted_string_escaped_newline(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad escape, should be skipped
        input = r""".mycls { background-image: url(image\
.jpg); }"""
        self.assertEqual(rewrite(input), input)

        input = r""".mycls { background-image: url(image.jpg\
); }"""
        self.assertEqual(rewrite(input), input)

    def test_image_unquoted_string_eof(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad url, should be skipped to the end
        input = """.mycls { background-image: url(img.jpg"""
        self.assertEqual(rewrite(input), input)

    def test_image_unquoted_string_escaped_eof(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_background_url=self.rewrite_func)

        # bad escape, should be skipped to the end
        input = """.mycls { background-image: url(img.jpg\\"""
        self.assertEqual(rewrite(input), input)

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

        # don't break normal rewriting
        input = r""".my\"class\" { }
@font-face { src: url("file.woff"); }"""
        expected = r""".my\"class\" { }
@font-face { src: url("http://example.com/file.woff"); }"""
        self.assertEqual(rewrite(input), expected)

    @unittest.expectedFailure
    def test_font_face_quoted_string_escaped_newline(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_font_face_url=self.rewrite_func)

        # escaped newlines should be stripped
        input = r"""@font-face { font-family: myfont; src: url("my\
font\
.woff"); }"""
        expected = """@font-face { font-family: myfont; src: url("http://example.com/myfont.woff"); }"""
        self.assertEqual(rewrite(input), expected)

        input = r"""@font-face { font-family: myfont; src: url('my\
font\
.woff'); }"""
        expected = """@font-face { font-family: myfont; src: url("http://example.com/myfont.woff"); }"""
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

        # don't break normal rewriting
        input = r""".my\"class\" { }
@import "file.css";"""
        expected = r""".my\"class\" { }
@import "http://example.com/file.css";"""
        self.assertEqual(rewrite(input), expected)

    @unittest.expectedFailure
    def test_import_quoted_string_escaped_newline(self):
        rewrite = partial(CssRewriter().rewrite, rewrite_import_url=self.rewrite_func)

        # escaped newlines should be stripped
        input = r"""@import "my\
file\
.css";"""
        expected = """@import "http://example.com/myfile.css";"""
        self.assertEqual(rewrite(input), expected)

        input = r"""@import 'my\
file\
.css';"""
        expected = """@import "http://example.com/myfile.css";"""
        self.assertEqual(rewrite(input), expected)

        input = r"""@import url("my\
file\
.css");"""
        expected = """@import url("http://example.com/myfile.css");"""
        self.assertEqual(rewrite(input), expected)

        input = r"""@import url('my\
file\
.css');"""
        expected = """@import url("http://example.com/myfile.css");"""
        self.assertEqual(rewrite(input), expected)


if __name__ == '__main__':
    unittest.main()
