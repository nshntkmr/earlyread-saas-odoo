# -*- coding: utf-8 -*-
"""Font Awesome icons in the page PDF (user decision D2, 2026-10-16).

The portal draws icons with Font Awesome 4.7 classes (``fa-phone``) — Odoo's
own copy in the ``web`` addon. The render service has no network, so the PDF
embeds that same font as a ``data:`` URI (the renderer's deny-list already
allows ``data:``; the chart library is loaded the same way) and prints each
icon as its glyph character in a span using that font. The font is embedded
only in documents that print at least one icon; a class that is not a
Font Awesome glyph prints nothing.
"""

import base64
import logging
import re

from markupsafe import Markup

_logger = logging.getLogger(__name__)

_FA_DIR = 'web/static/src/libs/fontawesome'
_CSS_REL = f'{_FA_DIR}/css/font-awesome.css'
_FONT_REL = f'{_FA_DIR}/fonts/fontawesome-webfont.woff2'
FONT_FAMILY = 'PvFontAwesome'

# ".fa-remove:before,\n.fa-close:before,\n.fa-times:before {\n  content: "\f00d";"
_RULE_RE = re.compile(r'((?:\.fa-[a-z0-9-]+:before\s*,?\s*)+)\{\s*content:\s*"\\([0-9a-fA-F]{4})"\s*;?')
_NAME_RE = re.compile(r'\.(fa-[a-z0-9-]+):before')
_CACHE = {}


def _read(rel, mode):
    from odoo.tools.misc import file_path
    with open(file_path(rel), mode, **({'encoding': 'utf-8'} if mode == 'r' else {})) as fh:
        return fh.read()


def glyph_map():
    """``{'fa-phone': '\\uf095', ...}`` parsed once per process from Odoo's
    ``font-awesome.css`` (empty when the file cannot be read)."""
    if 'map' not in _CACHE:
        mapping = {}
        try:
            css = _read(_CSS_REL, 'r')
        except (OSError, ValueError) as exc:
            _logger.warning('PDF export: Font Awesome CSS not readable (%s)', type(exc).__name__)
            css = ''
        for selectors, code in _RULE_RE.findall(css):
            char = chr(int(code, 16))
            for name in _NAME_RE.findall(selectors):
                mapping[name] = char
        _CACHE['map'] = mapping
    return _CACHE['map']


def glyph(fa_class):
    """The character for a class string (``'fa-user'``, ``'fa fa-user-md fa-fw'``);
    ``''`` when no token names a glyph."""
    if not isinstance(fa_class, str) or not fa_class.strip():
        return ''
    mapping = glyph_map()
    for token in fa_class.split():
        char = mapping.get(token.strip())
        if char:
            return char
    return ''


def font_face_css():
    """``@font-face`` rule with the woff2 font as a ``data:`` URI, as Markup
    for the template's ``<style>`` (``''`` when the font cannot be read)."""
    if 'css' not in _CACHE:
        try:
            data = base64.b64encode(_read(_FONT_REL, 'rb')).decode('ascii')
            _CACHE['css'] = Markup(
                "@font-face { font-family: '%s'; font-weight: normal; font-style: normal;"
                " src: url(data:font/woff2;base64,%s) format('woff2'); }"
                ' .pv-fa { font-family: \'%s\'; font-style: normal; font-weight: normal;'
                ' line-height: 1; display: inline-block; }'
            ) % (Markup(FONT_FAMILY), Markup(data), Markup(FONT_FAMILY))
        except (OSError, ValueError) as exc:
            _logger.warning('PDF export: Font Awesome font not readable (%s)', type(exc).__name__)
            _CACHE['css'] = Markup('')
    return _CACHE['css']


class IconSet:
    """Collects the glyphs one document prints, so the font is embedded only
    when at least one icon was resolved."""

    def __init__(self):
        self.used = False

    def __call__(self, fa_class):
        char = glyph(fa_class)
        if char:
            self.used = True
        return char
