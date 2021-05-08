import re
from urllib.parse import urljoin
from urllib.request import pathname2url

from . import util


class CssRewriter:
    """The base class that handles CSS rewriting for a reference path.
    """
    pCm = f"""(?:/\\*[\\s\\S]*?(?:\\*/|$))"""  # comment
    pSp = f"""(?:[ \\t\\r\\n\\v\\f]*)"""  # space equivalents
    pCmSp = f"""(?:(?:{pCm}|{pSp})*)"""  # comment or space
    pCmSp2 = f"""(?:(?:{pCm}|{pSp})+)"""  # comment or space, at least one
    pChar = f"""(?:\\\\.|[^\\\\"'])"""  # a non-quote char or an escaped char sequence
    pStr = f"""(?:{pChar}*?)"""  # string
    pSStr = f"""(?:{pCmSp}{pStr}{pCmSp})"""  # comment-or-space enclosed string
    pDQStr = f"""(?:"[^\\\\"]*(?:\\\\.[^\\\\"]*)*")"""  # double quoted string
    pSQStr = f"""(?:'[^\\\\']*(?:\\\\.[^\\\\']*)*')"""  # single quoted string
    pES = f"""(?:(?:{pCm}|{pDQStr}|{pSQStr}|{pChar})*?)"""  # embeded string
    pUrl = f"""(?:\\burl\\({pSp}(?:{pDQStr}|{pSQStr}|{pStr}){pSp}\\))"""  # URL
    pUrl2 = f"""(\\burl\\({pSp})({pDQStr}|{pSQStr}|{pStr})({pSp}\\))"""  # URL; catch 3
    pRImport = f"""(@import{pCmSp})({pUrl}|{pDQStr}|{pSQStr})"""  # @import; catch 2
    pRFontFace = f"""(@font-face{pCmSp}{{{pES}}})"""  # @font-face; catch 1
    pRNamespace = f"""(@namespace{pCmSp}(?:{pStr}{pCmSp2})?{pUrl})"""  # @namespace; catch 1

    REGEX_REWRITE_CSS = re.compile(f"""{pCm}|{pRImport}|{pRFontFace}|{pRNamespace}|({pUrl})""", re.I)
    REGEX_PARSE_URL = re.compile(pUrl2, re.I)
    REGEX_UNESCAPE_CSS = re.compile(r"""\\(?:([0-9A-Fa-f]{1,6}) ?|(.))""")

    def __init__(self, file=None, *,
            encoding=None,
            ref_url=None, url_chain=set()):
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
        def unescape_css(str):
            return self.REGEX_UNESCAPE_CSS.sub(unescape_css_sub, str)

        def unescape_css_sub(m):
            u, c = m.groups()
            if c:
                return c
            if u:
                return chr(int(u, 16))
  
        def parse_url(text, callback):
            def parse_url_sub(m):
                pre, url, post = m.groups()
                if url.startswith('"') and url.endswith('"'):
                    rewritten = callback(unescape_css(url[1:-1]))
                elif url.startswith("'") and url.endswith("'"):
                    rewritten = callback(unescape_css(url[1:-1]))
                else:
                    rewritten = callback(url.strip())
                return f'{pre}"{rewritten}"{post}'

            if not callback:
                return text

            return self.REGEX_PARSE_URL.sub(parse_url_sub, text)

        def rewrite_sub(m):
            im1, im2, ff, ns, u = m.groups()
            if im2:
                if im2.startswith('"') and im2.endswith('"'):
                    rewritten = rewrite_import_url(unescape_css(im2[1:-1]))
                elif im2.startswith("'") and im2.endswith("'"):
                    rewritten = rewrite_import_url(unescape_css(im2[1:-1]))
                else:
                    rewritten = parse_url(im2, rewrite_import_url)
                return f'{im1}"{rewritten}"'
            elif ff:
                return parse_url(ff, rewrite_font_face_url)
            elif ns:
                # do not rewrite @namespace rule
                return ns
            elif u:
                return parse_url(u, rewrite_background_url)
            return m.group(0)

        return self.REGEX_REWRITE_CSS.sub(rewrite_sub, text)
