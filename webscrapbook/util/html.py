"""HTML Parser
"""
import html
import html.parser
import re

REGEX_CLASS_SEPARATOR = re.compile(r'[ \t\n\r\f]+')

VOID_ELEMENTS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
FOREIGN_ELEMENTS = {'svg', 'math'}


class Error(Exception):
    pass


class Markup:
    """Class representing an HTML markup.
    """
    SHOWN_FLAG_ATTRS = ['ignored', 'hidden']
    SHOWN_ATTRS = {
        'pi': ['data'],
        'decl': ['data'],
        'comment': ['data'],
        'starttag': ['tag', 'attrs', 'is_self_end'],
        'endtag': ['tag', 'attrs'],
        'data': ['data', 'is_cdata', 'convert_charrefs'],
        'entityref': ['name'],
        'charref': ['name'],
        }

    def __init__(self, **kwargs):
        # general
        self.is_xhtml = False
        self.type = None
        self.src = None  # corresponding source text
        self.ignored = False  # should be treated as non-exist in the DOM
        self.hidden = False  # should not be output

        # starttag, endtag, startendtag
        self.tag = None
        self.attrs = None
        self.starttag = None
        self.endtag = None
        self.is_self_end = False

        # entityref, charref
        self.name = None

        # pi, decl, comment, data
        self.data = None
        self.is_unknown = False

        # data
        self.convert_charrefs = False
        self.is_cdata = False

        # merge passed kwargs
        for attr, value in kwargs.items():
            setattr(self, attr, value)

    def __repr__(self):
        attrs = []
        for k in self.SHOWN_ATTRS[self.type]:
            attrs.append(f'{k}={repr(getattr(self, k))}')

        # try:
            # attrs.append(f'id={id(self)}')
        # except AttributeError:
            # pass

        # try:
            # attrs.append(f'starttag={id(self.starttag)}')
        # except AttributeError:
            # pass

        # try:
            # attrs.append(f'endtag={id(self.endtag)}')
        # except AttributeError:
            # pass

        for k in self.SHOWN_FLAG_ATTRS:
            if getattr(self, k):
                attrs.append(k)

        return f'{self.type}({", ".join(attrs)})'

    def __str__(self):
        # use recorded src if exists
        if self.src is not None:
            return self.src

        if self.type == 'data':
            if self.is_cdata:
                return self.data
            if self.convert_charrefs:
                return html.escape(self.data, quote=False)
            return self.data
        elif self.type == 'starttag':
            if self.is_xhtml:
                attrs = ' '.join((f'{k}="{html.escape(k if v is None else v)}"') for k, v in self.attrs)
            else:
                attrs = ' '.join((k if v is None else f'{k}="{html.escape(v)}"') for k, v in self.attrs)
            attrs = ' ' + self._rewrite_attrs(attrs) if attrs else ''
            return f'<{self.tag}{attrs}{" /" if self.is_self_end else ""}>'
        elif self.type == 'endtag':
            return f'</{self.tag}>'
        elif self.type == 'pi':
            return f'<?{self.data}>'
        elif self.type == 'decl':
            return f'<!{self.data}>'
        elif self.type == 'comment':
            return f'<!--{self.data}-->'
        elif self.type == 'entityref':
            return f'&{self.name};'
        elif self.type == 'charref':
            return f'&#{self.name};'
        return self.__repr__()

    def _rewrite_attrs(self, attr):
        return attr.replace('\xA0', '&nbsp;').replace("&#x27;", "'")


class MarkupTag(Markup):
    @property
    def classes(self):
        try:
            return self._classes
        except AttributeError:
            pass
        classes_text = self.getattr('class')
        rv = [] if classes_text is None else REGEX_CLASS_SEPARATOR.split(classes_text)
        setattr(self, '_classes', rv)
        return rv

    def getattr(self, attr, default=None):
        for k, v in self.attrs:
            if k == attr:
                return v
        return default


class HTMLParser(html.parser.HTMLParser):
    """HTML parser extended from native to support some HTML5 behaviors.
    """
    # include escapable raw text elements
    CDATA_CONTENT_ELEMENTS = ('script', 'style', 'textarea', 'title')

    def __init__(self, convert_charrefs=False, is_xhtml=False):
        super().__init__(convert_charrefs=convert_charrefs)
        self._is_xhtml = is_xhtml

        self._rv = []
        self._stack = []

    def error(self, message):
        raise Error(message)

    def parse_html_declaration(self, i):
        """Hook parent class to retrieve source text of special declaration
        """
        self.__last_added_decl_markup = None
        endpos = super().parse_html_declaration(i)
        if self.__last_added_decl_markup is not None:
            setattr(self.__last_added_decl_markup, 'src', self.rawdata[i:endpos])
        return endpos

    def parse_endtag(self, i):
        """Hook parent class to retrieve source text of endtag
        """
        self.__last_added_endtag_markup = None
        endpos = super().parse_endtag(i)
        if self.__last_added_endtag_markup is not None:
            setattr(self.__last_added_endtag_markup, 'src', self.rawdata[i:endpos])
        return endpos

    def handle_pi(self, data):
        self._process(Markup(
            is_xhtml=self._is_xhtml,
            type='pi',
            data=data,
            ))

    def handle_decl(self, decl):
        self._process(Markup(
            is_xhtml=self._is_xhtml,
            type='decl',
            data=decl,
            ))

    def handle_comment(self, data):
        markup = Markup(
            is_xhtml=self._is_xhtml,
            type='comment',
            data=data,
            )
        self.__last_added_decl_markup = markup
        self._process(markup)

    def handle_starttag(self, tag, attrs):
        self._process(MarkupTag(
            is_xhtml=self._is_xhtml,
            type='starttag',
            tag=tag,
            attrs=attrs,
            src=self.get_starttag_text(),
            ))

    def handle_startendtag(self, tag, attrs):
        self._process(MarkupTag(
            is_xhtml=self._is_xhtml,
            type='starttag',
            tag=tag,
            attrs=attrs,
            src=self.get_starttag_text(),
            is_self_end=True,
            ))

    def handle_endtag(self, tag):
        markup = MarkupTag(
            is_xhtml=self._is_xhtml,
            type='endtag',
            tag=tag,
            )
        self.__last_added_endtag_markup = markup
        self._process(markup)

    def handle_data(self, data):
        self._process(Markup(
            is_xhtml=self._is_xhtml,
            type='data',
            data=data,
            convert_charrefs=self.convert_charrefs,
            is_cdata=bool(self.cdata_elem),
            ))

    def handle_entityref(self, name):
        self._process(Markup(
            is_xhtml=self._is_xhtml,
            type='entityref',
            name=name,
            ))

    def handle_charref(self, name):
        self._process(Markup(
            is_xhtml=self._is_xhtml,
            type='charref',
            name=name,
            ))

    def unknown_decl(self, data):
        markup = Markup(
            is_xhtml=self._is_xhtml,
            type='decl',
            data=data,
            is_unknown=True,
            )
        self.__last_added_decl_markup = markup
        self._process(markup)

    def close(self):
        super().close()

        for i in reversed(range(0, len(self._stack))):
            starttag = self._stack.pop()

            # create a hidden starttag for the unmatched starting tag
            endtag = MarkupTag(
                type='endtag',
                tag=starttag.tag,
                starttag= starttag,
                hidden=True,
                )
            setattr(starttag, 'endtag', endtag)
            self._rv.append(endtag)

    def _process(self, markup):
        """Process according to the current parser status

        @TODO: further implementation of HTML5 standard to prevent a potential
               error due to not well-formed HTML
               ref: https://html.spec.whatwg.org/multipage/parsing.html
        """
        self._process_token(markup)

    def _process_token(self, markup):
        getattr(self, f'_process_token_{markup.type}')(markup)

    def _process_token_pi(self, markup):
        self._rv.append(markup)

    def _process_token_decl(self, markup):
        self._rv.append(markup)

    def _process_token_comment(self, markup):
        self._rv.append(markup)

    def _process_token_starttag(self, markup):
        self._rv.append(markup)

        if self._is_xhtml or self._in_html_foreign_element():
            # don't push stack for a <tag /> in XHTML or XML
            if markup.is_self_end:
                return

        elif markup.tag in VOID_ELEMENTS:
            # create a hidden endtag for a void element
            # and don't push stack
            endtag = MarkupTag(
                is_xhtml=self._is_xhtml,
                type='endtag',
                tag=markup.tag,
                starttag=markup,
                hidden=True,
                )
            setattr(markup, 'endtag', endtag)
            self._rv.append(endtag)
            return

        self._stack.append(markup)

    def _process_token_endtag(self, markup):
        for i in reversed(range(0, len(self._stack))):
            starttag = self._stack.pop()
            if starttag.tag == markup.tag:
                setattr(starttag, 'endtag', markup)
                setattr(markup, 'starttag', starttag)
                break

            # create a hidden endtag for the implicitly closed tag
            endtag = MarkupTag(
                is_xhtml=self._is_xhtml,
                type='endtag',
                tag=starttag.tag,
                starttag= starttag,
                hidden=True,
                )
            setattr(starttag, 'endtag', endtag)
            self._rv.append(endtag)
        else:
            # create a hidden starttag for the unmatched ending tag
            starttag = MarkupTag(
                is_xhtml=self._is_xhtml,
                type='starttag',
                tag=markup.tag,
                attrs=[],
                endtag=markup,
                hidden=True,
                )
            setattr(markup, 'starttag', starttag)
            self._rv.append(starttag)

        self._rv.append(markup)

    def _process_token_data(self, markup):
        self._rv.append(markup)

    def _process_token_entityref(self, markup):
        self._rv.append(markup)

    def _process_token_charref(self, markup):
        self._rv.append(markup)

    def _ignore_markup(self, markup):
        setattr(markup, 'ignored', True)
        self._rv.append(markup)

    def _in_html_foreign_element(self):
        for markup in self._stack:
            if markup.tag in FOREIGN_ELEMENTS:
                return True
        return False


def markup_find(markups, filter, start=0, endtag=None):
    return next(markup_iterfind(markups, filter, start, endtag), None)


def markup_iterfind(markups, filter, start=0, endtag=None):
    i = start
    while True:
        try:
            markup = markups[i]
        except IndexError:
            break

        if filter(markup):
            yield i

        if markup.type == 'endtag':
            if endtag is not None:
                if markup == endtag:
                    break

        i += 1
