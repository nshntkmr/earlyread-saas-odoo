# -*- coding: utf-8 -*-
"""PDF print-layout fields shared by the definition and instance models
(``pdf_include``, ``pdf_page_break_before``, ``pdf_col_span`` — declared on
``dashboard.widget.action.mixin``).

Sync rule (same as col_span): seeded from the definition when an instance is
PLACED, then instance-owned — ``library_update`` never writes them to
instances. One normalisation for every API path.
"""

PDF_COL_SPANS = ('3', '4', '6', '8', '12')
PDF_LAYOUT_FIELDS = ('pdf_include', 'pdf_page_break_before', 'pdf_col_span')


def normalize_pdf_col_span(value):
    """'' / None / unknown → False (blank = same width as on screen)."""
    text = str(value).strip() if value not in (None, False) else ''
    return text if text in PDF_COL_SPANS else False


def _bool(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)


def pdf_layout_vals(body, create=False):
    """Write vals from an API payload. ``create=True`` fills defaults for
    missing keys; otherwise only keys present in the payload are written."""
    vals = {}
    if create or 'pdf_include' in body:
        vals['pdf_include'] = _bool(body.get('pdf_include'), True)
    if create or 'pdf_page_break_before' in body:
        vals['pdf_page_break_before'] = _bool(body.get('pdf_page_break_before'), False)
    if create or 'pdf_col_span' in body:
        vals['pdf_col_span'] = normalize_pdf_col_span(body.get('pdf_col_span'))
    return vals


def pdf_layout_payload(record):
    """Detail-response keys for a definition or instance."""
    return {
        'pdf_include': bool(record.pdf_include),
        'pdf_page_break_before': bool(record.pdf_page_break_before),
        'pdf_col_span': record.pdf_col_span or '',
    }


def pdf_layout_from_definition(defn):
    """Instance create vals seeded from a library definition (placement)."""
    return {
        'pdf_include': bool(defn.pdf_include),
        'pdf_page_break_before': bool(defn.pdf_page_break_before),
        'pdf_col_span': defn.pdf_col_span or False,
    }
