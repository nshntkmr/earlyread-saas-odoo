"""19.0.1.2.0 pre-migrate — no-op.

col_span remains a Selection field. Custom widths use the new width_pct
Integer field instead of changing col_span's type.
"""


def migrate(cr, version):
    pass
