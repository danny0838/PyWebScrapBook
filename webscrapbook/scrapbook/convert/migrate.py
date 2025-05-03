import json
import os
import re
import shutil
import tempfile
import time
import traceback
from datetime import datetime
from urllib.parse import urlsplit

from ... import util
from ...util import Info
from ...util.html import HtmlRewriter, Markup, MarkupTag
from ..host import Host

HTML_FILE_FILTER = re.compile(r'^.+\.x?html$', re.I)


# @TODO: better way to sync with WebScrapBook browser extension
ANNOTATION_CSS = r"""
[data-scrapbook-elem="linemarker"][title] {
  cursor: help;
}
[data-scrapbook-elem="sticky"] {
  display: block;
  overflow: auto;
}
[data-scrapbook-elem="sticky"].styled {
  position: absolute;
  z-index: 2147483647;
  opacity: .95;
  box-sizing: border-box;
  margin: 0;
  border: 1px solid #CCCCCC;
  border-top-width: 1.25em;
  border-radius: .25em;
  padding: .25em;
  min-width: 6em;
  min-height: 4em;
  background: #FAFFFA;
  box-shadow: .15em .15em .3em black;
  font: .875em/1.2 sans-serif;
  color: black;
  overflow-wrap: break-word;
  cursor: help;
}
[data-scrapbook-elem="sticky"].styled.relative {
  position: relative;
  margin: 16px auto;
}
[data-scrapbook-elem="sticky"].styled.plaintext {
  white-space: pre-wrap;
}
[data-scrapbook-elem="sticky"].dragging {
  opacity: .75;
  z-index: 2147483641;
}
"""

ANNOTATION_JS = r"""
function () {
  var w = window, d = document, r = d.documentElement, e;
  d.addEventListener('click', function (E) {
    if (r.hasAttribute('data-scrapbook-toolbar-active')) { return; }
    if (!w.getSelection().isCollapsed) { return; }
    e = E.target;
    if (e.matches('[data-scrapbook-elem="linemarker"]')) {
      if (e.title) {
        if (!confirm(e.title)) {
          E.preventDefault();
          E.stopPropagation();
        }
      }
    } else if (e.matches('[data-scrapbook-elem="sticky"]')) {
      if (confirm('%EditorDeleteAnnotationConfirm%')) {
        e.parentNode.removeChild(e);
        E.preventDefault();
        E.stopPropagation();
      }
    }
  }, true);
}
"""

BASIC_LOADER_JS = r"""
function () {
  var k1 = "data-scrapbook-shadowdom",
      k2 = "data-scrapbook-canvas",
      k3 = "data-scrapbook-input-indeterminate",
      k4 = "data-scrapbook-input-checked",
      k5 = "data-scrapbook-option-selected",
      k6 = "data-scrapbook-input-value",
      k7 = "data-scrapbook-textarea-value",
      k8 = "data-scrapbook-adoptedstylesheets",
      k9 = /^data-scrapbook-adoptedstylesheet-(\d+)$/,
      k10 = "data-scrapbook-shadowdom-mode",
      k11 = "data-scrapbook-shadowdom-clonable",
      k12 = "data-scrapbook-shadowdom-delegates-focus",
      k13 = "data-scrapbook-shadowdom-serializable",
      k14 = "data-scrapbook-shadowdom-slot-assignment",
      k15 = "data-scrapbook-slot-assigned",
      k16 = "data-scrapbook-slot-index",
      k17 = /^scrapbook-slot-index=(\d+)$/,
      k18 = '/scrapbook-slot-index',
      d = document,
      r = d.documentElement,
      $s = !!r.attachShadow,
      $as = !!d.adoptedStyleSheets,
      $c = !!window.HTMLCanvasElement,
      $sa = !!d.createElement('slot').assign,
      sle = [],
      sls = [],
      slt = function (r) {
        if ($sa) {
          var E = r.childNodes, i, e, s, m;
          for (i = 0; i < E.length; i++) {
            e = E[i];
            if (e.nodeType === 8) {
              s = e.nodeValue;
              if (m = s.match(k17)) {
                s = e.nextSibling;
                if (s.nodeType === 3) {
                  sls[m[1]] = s;
                }
                r.removeChild(e);
                i--;
              } else if (s === k18) {
                r.removeChild(e);
                i--;
              }
            }
          }
        }
      },
      sl = function () {
        var i = sle.length, j, d, e;
        while (i--) {
          d = sle[i];
          e = d.elem;
          d = d.value.split(',');
          j = d.length;
          while (j--) {
            d[j] = sls[parseInt(d[j], 10)];
          }
          try {
            e.assign.apply(e, d);
          } catch (ex) {
            console.error(ex);
          }
        }
      },
      asl = (function (r) {
        var l = [], E, i, e, m, c, j;
        if ($as) {
          E = r.attributes;
          i = E.length;
          while (i--) {
            e = E[i];
            if (!(m = e.nodeName.match(k9))) { continue; }
            c = l[m[1]] = new CSSStyleSheet();
            r.removeAttribute(m[0]);
            m = e.nodeValue.split('\n\n');
            j = m.length;
            while (j--) {
              try {
                m[j] && c.insertRule(m[j]);
              } catch (ex) {
                console.error(ex);
              }
            }
          }
        }
        return l;
      })(r),
      as = function (d, e) {
        var l, i, I;
        if ($as && (l = e.getAttribute(k8)) !== null) {
          l = l.split(',');
          for (i = 0, I = l.length; i < I; i++) {
            d.adoptedStyleSheets.push(asl[l[i]]);
          }
          e.removeAttribute(k8);
        }
      },
      fn = function (r) {
        var E = r.querySelectorAll ? r.querySelectorAll("*") : r.getElementsByTagName("*"), i = E.length, e, d, s, m;
        while (i--) {
          e = E[i];
          s = e.shadowRoot;
          if ($s && (d = e.getAttribute(k1))) {
            if (!s) {
              try {
                s = e.attachShadow({
                  mode: (m = e.getAttribute(k10)) !== null ? m : 'open',
                  clonable: e.hasAttribute(k11),
                  delegatesFocus: e.hasAttribute(k12),
                  serializable: e.hasAttribute(k13),
                  slotAssignment: (m = e.getAttribute(k14)) !== null ? m : void 0,
                });
                s.innerHTML = d;
              } catch (ex) {
                console.error(ex);
              }
            }
            e.removeAttribute(k1);
            e.removeAttribute(k10);
            e.removeAttribute(k11);
            e.removeAttribute(k12);
            e.removeAttribute(k13);
            e.removeAttribute(k14);
          }
          if ($c && (d = e.getAttribute(k2)) !== null) {
            (function () {
              var c = e, g = new Image();
              g.onload = function () { c.getContext('2d').drawImage(g, 0, 0); };
              g.src = d;
            })();
            e.removeAttribute(k2);
          }
          if ((d = e.getAttribute(k3)) !== null) {
            e.indeterminate = true;
            e.removeAttribute(k3);
          }
          if ((d = e.getAttribute(k4)) !== null) {
            e.checked = d === 'true';
            e.removeAttribute(k4);
          }
          if ((d = e.getAttribute(k5)) !== null) {
            e.selected = d === 'true';
            e.removeAttribute(k5);
          }
          if ((d = e.getAttribute(k6)) !== null) {
            e.value = d;
            e.removeAttribute(k6);
          }
          if ((d = e.getAttribute(k7)) !== null) {
            e.value = d;
            e.removeAttribute(k7);
          }
          if ($sa && (d = e.getAttribute(k15)) !== null) {
            sle.push({elem: e, value: d});
            e.removeAttribute(k15);
          }
          if ($sa && (d = e.getAttribute(k16)) !== null) {
            sls[d] = e;
            e.removeAttribute(k16);
          }
          if (s) {
            slt(e);
            as(s, e);
            fn(s);
          }
        }
      };
  as(d, r);
  fn(d);
  sl();
}
"""


class Converter:
    def __init__(self, input, output, book_ids=None, *,
                 convert_legacy=False,
                 convert_v1=False,
                 use_native_tags=False,
                 ):
        self.input = input
        self.output = output
        self.book_ids = book_ids
        self.convert_legacy = convert_legacy
        self.convert_v1 = convert_v1
        self.use_native_tags = use_native_tags

    def run(self):
        if self.input != self.output:
            yield Info('info', 'Copying files...')
            os.makedirs(self.output, exist_ok=True)
            self._copy_files()

        yield Info('info', 'Applying migration...')
        host = Host(self.output)

        # handle all books if none specified
        for book_id in self.book_ids or host.books:
            try:
                book = host.books[book_id]
            except KeyError:
                # skip invalid book ID
                yield Info('warn', f'Skipped invalid book {book_id!r}.')
                continue

            yield Info('info', f'Handling book {book_id!r}...')
            book.load_meta_files()
            book.load_toc_files()

            if self.convert_legacy:
                yield Info('info', 'Migrating data files from legacy ScrapBook...')
                converter = ConvertDataFilesLegacy(book, use_native_tags=self.use_native_tags)
                yield from converter.run()

            if self.convert_v1:
                yield Info('info', 'Migrating to WebScrapBook 1.*...')
                converter = ConvertDataFilesV1(book, use_native_tags=self.use_native_tags)
                yield from converter.run()

    def _copy_files(self):
        with os.scandir(self.input) as dirs:
            for src in dirs:
                dst = os.path.join(self.output, src.name)
                try:
                    shutil.copytree(src, dst)
                except NotADirectoryError:
                    shutil.copy2(src, dst)


class ConvertDataFilesLegacy:
    """Convert data files with legacy data format.

    - Convert a web page with legacy annotations and chrome:// stylesheets or icons.
    - Convert a postit with legacy or other bad page wrapper.
    """
    def __init__(self, book, *, use_native_tags=False):
        self.book = book
        self.use_native_tags = use_native_tags

    def run(self):
        book = self.book
        for id, meta in book.meta.items():
            index = meta.get('index', '')
            if not index.endswith('/index.html'):
                continue

            type = meta.get('type', '')
            yield Info('debug', f'Converting data files for {id!r} (type={type!r})...')
            if type == 'postit':
                index_file = os.path.normpath(os.path.join(book.data_dir, index))
                yield Info('debug', f'Checking: {index_file}...')
                try:
                    content = book.load_postit_file(index_file)
                except OSError as exc:
                    yield Info('error', f'Failed to convert {index!r} for {id!r}: {exc.strerror}', exc=exc)
                else:
                    book.save_postit_file(index_file, content)
            else:
                index_dir = os.path.normpath(os.path.dirname(os.path.join(book.data_dir, index)))
                for root, _dirs, files in os.walk(index_dir):
                    for file in files:
                        if HTML_FILE_FILTER.search(file):
                            file = os.path.join(root, file)
                            yield Info('debug', f'Checking: {file}...')
                            try:
                                conv = ConvertHtmlFileLegacy(
                                    file,
                                    use_native_tags=self.use_native_tags,
                                    host=self.book.host,
                                )
                                conv.run()
                            except Exception as exc:
                                traceback.print_exc()
                                yield Info('error', f'Failed to convert {file!r} for {id!r}: {exc}', exc=exc)


class ConvertHtmlFileLegacy(HtmlRewriter):
    PRE_WRAP_REGEX = re.compile(r'\bwhite-space:\s*pre-wrap\b', re.I)

    LEGACY_CLASSES_MAP = {
        'linemarker-marked-line': 'linemarker',
        'scrapbook-inline': 'inline',
        'scrapbook-sticky': 'sticky',
        'scrapbook-sticky-header': 'sticky-header',
        'scrapbook-sticky-footer': 'sticky-footer',
        'scrapbook-block-comment': 'block-comment',
    }
    LEGACY_FREENOTE_STYLE_POSITION_REGEX = re.compile(r'position:\s*(\w+);', re.I)
    LEGACY_POS_STYLE_REGEX = re.compile(r'(?:left|top|width|height):\s*[\d.]+px;', re.I)
    LEGACY_COMBINE_CSS = """\
body {
    margin: 0px;
    background-color: #FFFFFF;
}
cite.scrapbook-header {
    clear: both;
    display: block;
    padding: 3px 6px;
    font-family: "MS UI Gothic","Tahoma","Verdana","Arial","Sans-Serif","Helvetica";
    font-style: normal;
    font-size: 12px;
    background-color: InfoBackground;
    border: 1px solid ThreeDShadow;
}
cite.scrapbook-header img {
    vertical-align: middle;
}
cite.scrapbook-header a {
    color: InfoText;
    text-decoration: none;
}
cite.scrapbook-header a[href]:hover {
    color: #3388FF;
}
cite.scrapbook-header a.marked { font-weight: bold; }
cite.scrapbook-header a.combine  { color: blue; }
cite.scrapbook-header a.bookmark { color: limegreen; }
cite.scrapbook-header a.notex { color: rgb(80,0,32); }
"""
    LEGACY_COMBINE_ICON_MAP = {
        'chrome://scrapbook/skin/treefolder.png': 'fclose.png',
        'chrome://scrapbook/skin/treenote.png': 'postit.png',
        'chrome://scrapbook/skin/treenotex.png': 'note.png',
        'chrome://scrapbook/skin/treeitem.png': 'item.png',
    }

    def __init__(self, file, *, use_native_tags=False, host=None):
        super().__init__(file)
        self.use_native_tags = use_native_tags
        self.host = host

    def run(self):
        self.require_annotation_loader = False
        self.combine_icons = {}
        self.map_id_markups = {}

        super().run()

    def rewrite(self, markups):
        for markup in markups:
            if markup.type == 'starttag':
                # record map of data-sb-id to markup
                id = markup.getattr('data-sb-id')
                self.map_id_markups.setdefault(id, []).append(markup)

                # check and record requirement of loader
                type = markup.getattr('data-scrapbook-elem')
                if type == 'sticky' or (type == 'linemarker' and markup.getattr('title') is not None):
                    self.require_annotation_loader = True

        markups, _ = self.convert(markups)

        # update annotation loader if there's a change
        if self.changed:
            markups = self._update_annotation_loaders(markups)

        return markups

    def convert(self, markups, start=0, endtag=None):
        rv = []
        i = start
        while True:
            try:
                markup = markups[i]
            except IndexError:
                break

            if markup.type == 'starttag':
                # pass-through special context tags
                if markup.tag in ('template', 'svg', 'math'):
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023
                    for j in range(i, iend + 1):
                        rv.append(markups[j])
                    i = iend + 1
                    continue

                # handle legacy stylesheet
                if markup.tag == 'link' and markup.getattr('rel') == 'stylesheet':
                    href = markup.getattr('href')

                    # remove legacy annotation CSS
                    if href == 'chrome://scrapbook/skin/annotation.css':
                        i += 1
                        self.changed = True
                        continue

                    # convert legacy combine CSS
                    if href == 'chrome://scrapbook/skin/combine.css':
                        rv.append(MarkupTag(
                            is_xhtml=self.is_xhtml,
                            type='starttag',
                            tag='style',
                            attrs=[
                                ('data-scrapbook-elem', 'custom-css'),
                            ],
                        ))
                        rv.append(Markup(
                            is_xhtml=self.is_xhtml,
                            type='data',
                            data=util.compress_code(self.LEGACY_COMBINE_CSS),
                            is_cdata=True,
                        ))
                        rv.append(MarkupTag(
                            is_xhtml=self.is_xhtml,
                            type='endtag',
                            tag='style',
                        ))

                        i += 1
                        self.changed = True
                        continue

                # handle legacy combine icon
                if markup.tag == 'img':
                    src_changed = False
                    for j, attr_value in enumerate(markup.attrs):
                        attr, value = attr_value
                        if attr == 'src' and value in self.LEGACY_COMBINE_ICON_MAP:
                            new_src = self._get_legacy_combine_icon_url(value)
                            if new_src is not None:
                                markup.attrs[j] = (attr, new_src)
                                src_changed = True
                                break

                    if src_changed:
                        rv.append(MarkupTag(
                            is_xhtml=self.is_xhtml,
                            type='starttag',
                            tag=markup.tag,
                            attrs=markup.attrs,
                        ))

                        i += 1
                        self.changed = True
                        continue

                # handle annotations
                type = self._get_legacy_scrapbook_object_type(markup)

                if type in ('linemarker', 'inline'):
                    tag = 'span' if self.use_native_tags else 'scrapbook-linemarker'
                    attrs = {
                        'data-scrapbook-id': None,
                        'data-scrapbook-elem': 'linemarker',
                        'class': [],
                    }

                    # id
                    id = markup.getattr('data-sb-id')
                    new_id = None

                    if id:
                        new_id = self._convert_legacy_scrapbook_elem_id(id)
                        try:
                            if markup == self.map_id_markups[id][0]:
                                attrs['class'].append('first')
                        except KeyError:
                            pass
                        try:
                            if markup == self.map_id_markups[id][-1]:
                                attrs['class'].append('last')
                        except KeyError:
                            pass

                    if new_id:
                        attrs['data-scrapbook-id'] = new_id

                    # style
                    css = markup.getattr('style')
                    if css:
                        attrs['style'] = css

                    # title
                    title = markup.getattr('title')
                    if title is not None:
                        attrs['title'] = title
                        self.require_annotation_loader = True

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(
                        MarkupTag(
                            is_xhtml=self.is_xhtml,
                            type='starttag',
                            tag=tag,
                            attrs=attrs,
                        )
                    )

                    _rv, _i = self.convert(markups, i + 1, markup.endtag)
                    rv.extend(_rv)
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='endtag',
                        tag=tag,
                    ))

                    i = _i + 1
                    self.changed = True
                    continue

                elif type == 'freenote':
                    tag = 'div' if self.use_native_tags else 'scrapbook-sticky'
                    attrs = {
                        'data-scrapbook-elem': 'sticky',
                        'class': ['styled'],
                    }

                    # CSS
                    # @TODO: implement CSS parser for better error proof
                    css = markup.getattr('style')
                    if css:
                        m = self.LEGACY_FREENOTE_STYLE_POSITION_REGEX.search(css)
                        if m and m.group(1).lower() == 'static':
                            attrs['class'].append('relative')

                        css_new = ' '.join(m.group(0) for m in self.LEGACY_POS_STYLE_REGEX.finditer(css))
                        if css_new:
                            attrs['style'] = css_new

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                    ))

                    _rv, _i = self.convert(markups, i + 1, markup.endtag)
                    rv.extend(_rv)
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='endtag',
                        tag=tag,
                    ))

                    i = _i + 1
                    self.changed = True
                    self.require_annotation_loader = True
                    continue

                elif type == 'sticky':
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023

                    tag = 'div' if self.use_native_tags else 'scrapbook-sticky'
                    attrs = {
                        'data-scrapbook-elem': 'sticky',
                        'class': ['styled', 'plaintext'],
                    }
                    if 'scrapbook-sticky-relative' in markup.classes:
                        attrs['class'].append('relative')

                    # CSS
                    # @TODO: implement CSS parser for better error proof
                    css = markup.getattr('style')
                    if css:
                        css_new = ' '.join(m.group(0) for m in self.LEGACY_POS_STYLE_REGEX.finditer(css))
                        if css_new:
                            attrs['style'] = css_new

                    # text content
                    textarea_i = self.find(markups, lambda x: x.tag == 'textarea', i + 1, markup.endtag)
                    if textarea_i is not None:
                        # unsaved sticky: take textarea content
                        textarea_iend = self.find(markups, lambda x: x == markups[textarea_i].endtag, textarea_i + 1, markup.endtag)  # noqa: B023
                        text = ''.join(str(d) for d in markups[textarea_i + 1:textarea_iend])
                    else:
                        last_child_i = i
                        for j in self.iterfind(markups, lambda x: x.type == 'endtag' and x != markup.endtag, i + 1, markup.endtag):  # noqa: B023
                            last_child_i = j
                        text = ''.join(str(d) for d in markups[last_child_i + 1:iend] if d.type == 'data')

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                    ))
                    if text:
                        rv.append(Markup(
                            is_xhtml=self.is_xhtml,
                            type='data',
                            data=text,
                            convert_charrefs=False,
                        ))
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='endtag',
                        tag=tag,
                    ))

                    i = iend + 1
                    self.changed = True
                    self.require_annotation_loader = True
                    continue

                elif type == 'block-comment':
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023

                    tag = 'div' if self.use_native_tags else 'scrapbook-sticky'
                    attrs = {
                        'data-scrapbook-elem': 'sticky',
                        'class': ['plaintext', 'relative'],
                    }

                    # CSS
                    css = markup.getattr('style')
                    if css:
                        if not self.PRE_WRAP_REGEX.search(css):
                            css += ' white-space: pre-wrap;'
                    else:
                        css = 'white-space: pre-wrap;'
                    attrs['style'] = css

                    # text content
                    textarea_i = self.find(markups, lambda x: x.tag == 'textarea', i + 1, markup.endtag)
                    if textarea_i is not None:
                        # unsaved block-comment: take textarea content
                        textarea_iend = self.find(markups, lambda x: x == markups[textarea_i].endtag, textarea_i + 1, markup.endtag)  # noqa: B023
                        text = ''.join(str(d) for d in markups[textarea_i + 1:textarea_iend])
                    else:
                        text = ''.join(str(d) for d in markups[i + 1:iend] if d.type == 'data')

                    attrs['class'] = ' '.join(attrs['class'])
                    attrs = [(a, v) for a, v in attrs.items() if v]
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='starttag',
                        tag=tag,
                        attrs=attrs,
                    ))
                    if text:
                        rv.append(Markup(
                            is_xhtml=self.is_xhtml,
                            type='data',
                            data=text,
                            convert_charrefs=False,
                        ))
                    rv.append(MarkupTag(
                        is_xhtml=self.is_xhtml,
                        type='endtag',
                        tag=tag,
                    ))

                    i = iend + 1
                    self.changed = True
                    self.require_annotation_loader = True
                    continue

                else:
                    markup_changed = False
                    has_data_sb_obj = False
                    for j, attr_value in enumerate(markup.attrs):
                        attr, value = attr_value

                        # convert type attribute
                        if attr == 'data-sb-obj':
                            has_data_sb_obj = True
                            markup.attrs[j] = ('data-scrapbook-elem', type)
                            markup_changed = True

                        # convert id attribute
                        elif attr == 'data-sb-id':
                            markup.attrs[j] = ('data-scrapbook-id', self._convert_legacy_scrapbook_elem_id(value))
                            markup_changed = True

                        # convert data-sb-orig-<attr>
                        elif attr.startswith('data-sb-orig-'):
                            attr = f'data-scrapbook-orig-attr-{attr[13:]}'
                            markup.attrs[j] = (attr, value)
                            markup_changed = True

                    if type and not has_data_sb_obj:
                        markup.attrs.append(('data-scrapbook-elem', type))
                        markup_changed = True

                    if markup_changed:
                        rv.append(MarkupTag(
                            is_xhtml=self.is_xhtml,
                            type='starttag',
                            tag=markup.tag,
                            attrs=markup.attrs,
                            is_self_end=markup.is_self_end,
                        ))

                        i += 1
                        self.changed = True
                        continue

            elif markup.type == 'endtag':
                if endtag is not None:
                    if markup == endtag:
                        break

            rv.append(markup)
            i += 1

        return rv, i

    def _get_legacy_scrapbook_object_type(self, markup):
        type = markup.getattr('data-sb-obj')
        if not type:
            for cls in markup.classes:
                if cls in self.LEGACY_CLASSES_MAP:
                    type = self.LEGACY_CLASSES_MAP[cls]
                    break
        return type

    def _get_legacy_combine_icon_url(self, src):
        if self.host is None or self.file is None:
            return None

        # attempt to load from cache
        try:
            return self.combine_icons[src]
        except KeyError:
            pass

        # save the icon under the root index dir
        root = os.path.dirname(self.file)
        filename, ext = os.path.splitext(os.path.basename(urlsplit(src).path))
        fsrc = self.host.get_static_file(self.LEGACY_COMBINE_ICON_MAP[src])
        fdst = os.path.join(root, f'{filename}{ext}')
        i = 1
        while os.path.lexists(fdst):
            fdst = os.path.join(root, f'{filename}-{i}{ext}')
            i += 1

        shutil.copyfile(fsrc, fdst)

        new_src = self.combine_icons[src] = util.get_relative_url(
            fdst,
            self.file,
            path_is_dir=False,
            start_is_dir=False,
        )

        return new_src

    def _convert_legacy_scrapbook_elem_id(self, id):
        """Convert legacy sb-obj-id (JavaScript timestamp) to WebScrapBook id.
        """
        try:
            dt = datetime.fromtimestamp(int(id) / 1000.0)
            return util.datetime_to_id(dt)
        except Exception:
            return id

    def _update_annotation_loaders(self, markups):
        # remove current loader
        rv = []
        i = 0
        while True:
            try:
                markup = markups[i]
            except IndexError:
                break

            if markup.type == 'starttag':
                if markup.getattr('data-scrapbook-elem') in {'annotation-loader', 'annotation-css'}:
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023
                    i = iend + 1
                    continue

            rv.append(markup)
            i += 1

        # insert new loader
        if not self.require_annotation_loader:
            return rv

        markups = []

        markups.append(MarkupTag(
            is_xhtml=self.is_xhtml,
            type='starttag',
            tag='style',
            attrs=[
                ('data-scrapbook-elem', 'annotation-css'),
            ],
        ))
        markups.append(Markup(
            is_xhtml=self.is_xhtml,
            type='data',
            data=util.compress_code(ANNOTATION_CSS),
            is_cdata=True,
        ))
        markups.append(MarkupTag(
            is_xhtml=self.is_xhtml,
            type='endtag',
            tag='style',
        ))

        script = util.compress_code(ANNOTATION_JS)
        if self.host:
            script = util.format_string(script, self.host.get_i18n())
        script = f'({script})()'

        markups.append(MarkupTag(
            is_xhtml=self.is_xhtml,
            type='starttag',
            tag='script',
            attrs=[
                ('data-scrapbook-elem', 'annotation-loader'),
            ],
        ))
        markups.append(Markup(
            is_xhtml=self.is_xhtml,
            type='data',
            data=script,
            is_cdata=True,
        ))
        markups.append(MarkupTag(
            is_xhtml=self.is_xhtml,
            type='endtag',
            tag='script',
        ))

        pos = None
        for i in reversed(range(0, len(rv))):
            markup = rv[i]
            if markup.type == 'endtag':
                if markup.tag == 'body':
                    pos = i
                    break

                if markup.tag == 'html':
                    pos = i

        if pos is not None:
            rv = rv[:pos] + markups + rv[pos:]
        else:
            rv += markups

        return rv


class ConvertDataFilesV1:
    """Convert data files to latest WebScrapBook 1.*
    """
    def __init__(self, book, *, use_native_tags):
        self.book = book
        self.use_native_tags = use_native_tags

    def run(self):
        book = self.book
        for id, meta in book.meta.items():
            type = meta.get('type', '')
            if type == 'postit':
                continue

            index = meta.get('index', '')
            if not index:
                continue

            yield Info('debug', f'Converting data files for {id!r} (type={type!r})...')

            # folder
            if index.endswith('/index.html'):
                index_dir = os.path.normpath(os.path.dirname(os.path.join(book.data_dir, index)))
                for root, _dirs, files in os.walk(index_dir):
                    for file in files:
                        if HTML_FILE_FILTER.search(file):
                            file = os.path.join(root, file)
                            yield Info('debug', f'Checking: {file}...')
                            try:
                                conv = ConvertHtmlFileV1(file)
                                conv.run()
                            except Exception as exc:
                                traceback.print_exc()
                                yield Info('error', f'Failed to convert {file!r} for {id!r}: {exc}', exc=exc)

            # htz/maff
            elif util.is_htz(index) or util.is_maff(index):
                index_file = os.path.normpath(os.path.join(book.data_dir, index))
                tempdir = tempfile.mkdtemp()
                tempzipdir = os.path.join(tempdir, 'zip')
                try:
                    util.fs.zip_extract(index_file, tempzipdir)

                    changed = False
                    for root, _dirs, files in os.walk(tempzipdir):
                        for file in files:
                            if HTML_FILE_FILTER.search(file):
                                file = os.path.join(root, file)
                                subpath = file[len(tempzipdir) + 1:].replace('\\', '/')
                                yield Info('debug', f'Checking: {subpath!r} in {index_file!r}...')
                                try:
                                    conv = ConvertHtmlFileV1(file)
                                    conv.run()
                                    if conv.changed:
                                        changed = True
                                except Exception as exc:
                                    traceback.print_exc()
                                    yield Info('error', f'Failed to convert {subpath!r} in {index_file!r} for {id!r}: {exc}', exc=exc)

                    # don't recompress (and change mtime) if no content changed
                    if changed:
                        util.fs.zip_compress(index_file, tempzipdir, '')
                finally:
                    try:
                        shutil.rmtree(tempdir)
                    except OSError:
                        pass

            # single file
            elif util.is_html(index):
                file = os.path.normpath(os.path.join(book.data_dir, index))
                yield Info('debug', f'Checking: {file}...')
                try:
                    conv = ConvertHtmlFileV1(file)
                    conv.run()
                except Exception as exc:
                    traceback.print_exc()
                    yield Info('error', f'Failed to convert {file!r} for {id!r}: {exc}', exc=exc)


class ConvertHtmlFileV1(HtmlRewriter):
    def run(self):
        self.require_basic_loader = False
        self.require_annotation_loader = False

        super().run()

    def rewrite(self, markups):
        markups = self.rewrite_doc(markups)

        # update loaders if there's a change
        if self.changed:
            markups = self._update_loaders(markups)

        return markups

    def rewrite_doc(self, markups):
        rv = []
        i = 0
        while True:
            try:
                markup = markups[i]
            except IndexError:
                break

            if markup.type == 'starttag':
                # pass-through special context tags
                if markup.tag in ('template', 'svg', 'math'):
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023
                    for j in range(i, iend + 1):
                        rv.append(markups[j])
                    i = iend + 1
                    continue

                # check and record requirement of loader
                type = markup.getattr('data-scrapbook-elem')

                if type == 'basic-loader':
                    self.require_basic_loader = True

                if type in {'annotation-css', 'annotation-loader'}:
                    self.require_annotation_loader = True

                # handle old WebScrapBook loaders
                if markup.tag == 'script':
                    if markup.getattr('data-scrapbook-elem') in {
                        'canvas-loader',  # WebScrapBook < 0.69
                        'shadowroot-loader',  # WebScrapBook < 0.69
                    }:
                        iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023

                        i = iend + 1
                        self.changed = True
                        self.require_basic_loader = True
                        continue

                # handle old WebScrapBook attributes
                else:
                    inserts = []
                    for j, attr_value in enumerate(markup.attrs):
                        attr, value = attr_value
                        if attr == 'data-scrapbook-shadowroot':  # WebScrapBook < 0.115
                            try:
                                data = self._convert_shadowroot_attribute(value)
                            except (json.decoder.JSONDecodeError, KeyError):
                                raise ValueError(f'Invalid value of {attr!r} attribute: {value!r}') from None
                            inserts.append((j, data))
                    if inserts:
                        for j, data in reversed(inserts):
                            html, mode = data
                            markup.attrs[j] = ('data-scrapbook-shadowdom', html)
                            if mode != 'open':
                                markup.attrs.insert(j + 1, ('data-scrapbook-shadowdom-mode', mode))
                        markup.src = None
                        self.changed = True
                        self.require_basic_loader = True

            rv.append(markup)
            i += 1

        return rv

    def _update_loaders(self, markups):
        # remove current loader
        rv = []
        i = 0
        while True:
            try:
                markup = markups[i]
            except IndexError:
                break

            if markup.type == 'starttag':
                if markup.getattr('data-scrapbook-elem') in {'basic-loader', 'annotation-loader', 'annotation-css'}:
                    iend = self.find(markups, lambda x: x == markup.endtag, i + 1, markup.endtag)  # noqa: B023
                    i = iend + 1
                    continue

            rv.append(markup)
            i += 1

        # insert new loader
        if self.require_basic_loader:
            markups = []

            script = util.compress_code(BASIC_LOADER_JS)
            script = f'({script})()'

            markups.append(MarkupTag(
                is_xhtml=self.is_xhtml,
                type='starttag',
                tag='script',
                attrs=[
                    ('data-scrapbook-elem', 'basic-loader'),
                ],
            ))
            markups.append(Markup(
                is_xhtml=self.is_xhtml,
                type='data',
                data=script,
                is_cdata=True,
            ))
            markups.append(MarkupTag(
                is_xhtml=self.is_xhtml,
                type='endtag',
                tag='script',
            ))

            pos = None
            for i in reversed(range(0, len(rv))):
                markup = rv[i]
                if markup.type == 'endtag':
                    if markup.tag == 'body':
                        pos = i
                        break

                    if markup.tag == 'html':
                        pos = i

            if pos is not None:
                rv = rv[:pos] + markups + rv[pos:]
            else:
                rv += markups

        if self.require_annotation_loader:
            markups = []

            markups.append(MarkupTag(
                is_xhtml=self.is_xhtml,
                type='starttag',
                tag='style',
                attrs=[
                    ('data-scrapbook-elem', 'annotation-css'),
                ],
            ))
            markups.append(Markup(
                is_xhtml=self.is_xhtml,
                type='data',
                data=util.compress_code(ANNOTATION_CSS),
                is_cdata=True,
            ))
            markups.append(MarkupTag(
                is_xhtml=self.is_xhtml,
                type='endtag',
                tag='style',
            ))

            script = util.compress_code(ANNOTATION_JS)
            if self.host:
                script = util.format_string(script, self.host.get_i18n())
            script = f'({script})()'

            markups.append(MarkupTag(
                is_xhtml=self.is_xhtml,
                type='starttag',
                tag='script',
                attrs=[
                    ('data-scrapbook-elem', 'annotation-loader'),
                ],
            ))
            markups.append(Markup(
                is_xhtml=self.is_xhtml,
                type='data',
                data=script,
                is_cdata=True,
            ))
            markups.append(MarkupTag(
                is_xhtml=self.is_xhtml,
                type='endtag',
                tag='script',
            ))

            pos = None
            for i in reversed(range(0, len(rv))):
                markup = rv[i]
                if markup.type == 'endtag':
                    if markup.tag == 'body':
                        pos = i
                        break

                    if markup.tag == 'html':
                        pos = i

            if pos is not None:
                rv = rv[:pos] + markups + rv[pos:]
            else:
                rv += markups

        return rv

    def _convert_shadowroot_attribute(self, data):
        data = json.loads(data)
        markups = self.loads(data['data'])
        markups = self.rewrite_doc(markups)
        html = ''.join(str(m) for m in markups if not m.hidden)
        mode = data['mode']
        return html, mode


def run(input, output, book_ids=None, *,
        convert_legacy=False,
        convert_v1=False,
        use_native_tags=False,
        ):
    start = time.time()
    book_ids_text = ', '.join(f'{id!r}' for id in book_ids) if book_ids else 'all'
    yield Info('info', 'migrating:')
    yield Info('info', f'input directory: {os.path.abspath(input)}')
    yield Info('info', f'output directory: {os.path.abspath(output) if output is not None else "(in-place)"}')
    yield Info('info', f'book(s): {book_ids_text}')
    yield Info('info', f'convert legacy: {convert_legacy}')
    yield Info('info', f'convert v1: {convert_v1}')
    yield Info('info', f'use native tags: {use_native_tags}')
    yield Info('info', '')

    if output is None:
        output = input

    try:
        conv = Converter(input, output, book_ids=book_ids,
                         convert_legacy=convert_legacy,
                         convert_v1=convert_v1,
                         use_native_tags=use_native_tags,
                         )
        yield from conv.run()
    except Exception as exc:
        traceback.print_exc()
        yield Info('critical', str(exc), exc=exc)
        return
    else:
        yield Info('info', 'Done.')

    elapsed = time.time() - start
    yield Info('info', f'Time spent: {elapsed} seconds.')
