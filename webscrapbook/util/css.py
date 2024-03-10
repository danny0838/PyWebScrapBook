import re
from urllib.parse import urljoin
from urllib.request import pathname2url

from . import util


class CssRewriter:
    """The base class that handles CSS rewriting for a reference path.
    """  # noqa: N815, F541
    pCm = fr"""(?:/\*[\s\S]*?(?:\*/|$))"""  # comment  # noqa: N815, F541  # noqa: N815, F541
    pSp = fr"""(?:[ \t\r\n\v\f]*)"""  # space equivalents  # noqa: N815, F541
    pCmSp = fr"""(?:(?:{pCm}|{pSp})*)"""  # comment or space  # noqa: N815, F541
    pCmSp2 = fr"""(?:(?:{pCm}|{pSp})+)"""  # comment or space, at least one  # noqa: N815, F541
    pEscaped = r"""\\(?:[0-9A-Fa-f]{1,6} ?|.)"""  # an escaped char sequence  # noqa: N815, F541
    pChar = fr"""(?:{pEscaped}|[^\\"'])"""  # a non-quote char or an escaped char sequence  # noqa: N815, F541
    pStr = fr"""(?:{pChar}*?)"""  # string  # noqa: N815, F541
    pSStr = fr"""(?:{pCmSp}{pStr}{pCmSp})"""  # comment-or-space enclosed string  # noqa: N815, F541
    pDQStr = fr"""(?:"[^\\"]*(?:\\.[^\\"]*)*")"""  # double quoted string  # noqa: N815, F541
    pSQStr = fr"""(?:'[^\\']*(?:\\.[^\\']*)*')"""  # single quoted string  # noqa: N815, F541
    pES = fr"""(?:(?:{pCm}|{pDQStr}|{pSQStr}|{pChar})*?)"""  # embeded string  # noqa: N815, F541
    pUrl = fr"""(?:\burl\({pSp}(?:{pDQStr}|{pSQStr}|{pStr}){pSp}\))"""  # URL  # noqa: N815, F541
    pUrl2 = fr"""(\burl\({pSp})({pDQStr}|{pSQStr}|{pStr})({pSp}\))"""  # URL; catch 3  # noqa: N815, F541
    pRImport = fr"""(@import{pCmSp})({pUrl}|{pDQStr}|{pSQStr})"""  # @import; catch 2  # noqa: N815, F541
    pRFontFace = fr"""(@font-face{pCmSp}{{{pES}}})"""  # @font-face; catch 1  # noqa: N815, F541
    pRNamespace = fr"""(@namespace{pCmSp}(?:{pStr}{pCmSp2})?{pUrl})"""  # @namespace; catch 1  # noqa: N815, F541

    REGEX_REWRITE_CSS = re.compile(fr"""{pEscaped}|{pDQStr}|{pSQStr}|{pCm}|{pRImport}|{pRFontFace}|{pRNamespace}|({pUrl})""", re.I)
    REGEX_PARSE_URL = re.compile(pUrl2, re.I)
    REGEX_UNESCAPE_CSS = re.compile(r"""\\(?:([0-9A-Fa-f]{1,6}) ?|(.))""")

    def __init__(self, file=None, *,
                 encoding=None,
                 ref_url=None, url_chain=set()):  # noqa: B006
        """Initialize the class and bind associated information.

        Args:
            file: path of the associated file.
            ref_url: overriding URL path of the reference path.
            encoding: the encoding for reading a file. None for autodetection
                (and self.encoding will be auto reset on reading).
        """
        self.file = file
        self.encoding = encoding
        self.ref_url = ref_url
        self.url_chain = url_chain.copy()

        if file:
            if not ref_url:
                self.ref_url = urljoin('file:///', pathname2url(file))

        if self.ref_url:
            self.url_chain.add(self.ref_url)

    def run(self, *args, **kwargs):
        """Common rewriting case when an associated file is provided.
        """
        if not self.file:
            raise RuntimeError('Associated file not set.')

        text = self.load(self.file)
        return self.rewrite(text, *args, **kwargs)

    def load(self, file):
        """Load a CSS file and return content text.

        May reset self.encoding.

        Args:
            file: str, path-like, or file-like bytes object
        Raises:
            OSError: failed to read the file
        """
        try:
            fh = open(file, 'rb')
        except TypeError:
            fh = file

        try:
            if not self.encoding:
                # Seek for the correct charset (encoding).
                # Use ISO-8859-1 if no encoding can be determined, so that
                # rewriting work independently with encoding.
                self.encoding = util.sniff_bom(fh) or 'ISO-8859-1'

            return fh.read().decode(self.encoding)
        finally:
            if fh != file:
                fh.close()

    def rewrite(self, text,
                rewrite_import_url=lambda url: url,
                rewrite_font_face_url=lambda url: url,
                rewrite_background_url=lambda url: url,
                ):
        def parse_url(text, callback):
            def parse_url_sub(m):
                pre, url, post = m.groups()
                if url.startswith('"') and url.endswith('"'):
                    rewritten = callback(self.unescape_css(url[1:-1]))
                elif url.startswith("'") and url.endswith("'"):
                    rewritten = callback(self.unescape_css(url[1:-1]))
                else:
                    rewritten = callback(url.strip())
                return f'{pre}"{self.escape_quotes(rewritten)}"{post}'

            if not callback:
                return text

            return self.REGEX_PARSE_URL.sub(parse_url_sub, text)

        def rewrite_sub(m):
            im1, im2, ff, ns, u = m.groups()
            if im2:
                if im2.startswith('"') and im2.endswith('"'):
                    rewritten = rewrite_import_url(self.unescape_css(im2[1:-1]))
                    rewritten = f'"{self.escape_quotes(rewritten)}"'
                elif im2.startswith("'") and im2.endswith("'"):
                    rewritten = rewrite_import_url(self.unescape_css(im2[1:-1]))
                    rewritten = f'"{self.escape_quotes(rewritten)}"'
                else:
                    rewritten = parse_url(im2, rewrite_import_url)
                return f'{im1}{rewritten}'
            elif ff:
                return parse_url(ff, rewrite_font_face_url)
            elif ns:
                # do not rewrite @namespace rule
                return ns
            elif u:
                return parse_url(u, rewrite_background_url)
            return m.group(0)

        return self.REGEX_REWRITE_CSS.sub(rewrite_sub, text)

    def escape_quotes(self, str):
        return str.replace('\\', r'\\').replace(r'"', r'\"')

    def unescape_css(self, str):
        return self.REGEX_UNESCAPE_CSS.sub(self.unescape_css_sub, str)

    def unescape_css_sub(self, m):
        u, c = m.groups()
        if c:
            return c
        if u:
            return chr(int(u, 16))
