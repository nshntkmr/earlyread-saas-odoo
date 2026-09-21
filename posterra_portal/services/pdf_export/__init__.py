# -*- coding: utf-8 -*-
"""Page PDF export (plan v5, accepted 2026-09-21).

Pipeline: ``collector`` builds ONE immutable report dataset from the same
display paths the dashboard uses (bounded + timed), ``document`` renders it
to HTML with QWeb, ``render_client`` posts the HTML to the Gotenberg render
service and returns the PDF bytes. ``cell_format`` is the Python print mirror
of the AG Grid formatters/renderers; ``deadline`` holds the time budget.
PostgreSQL and ClickHouse sources only — Snowflake-backed widgets are
skipped with a visible notice (decision V1).
"""
