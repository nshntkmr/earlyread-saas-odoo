# -*- coding: utf-8 -*-
"""Backfill dashboard.widget.metric_direction from legacy visual_config.trend_invert.

Runs once when upgrading from a prior version. Before this release, the
"lower is better" polarity lived inside the visual_config JSON as
``{"trend_invert": true}``. This script promotes it to the proper
``metric_direction`` field so the value is queryable and admin-editable.

After this migration runs, every dashboard.widget row has an explicit
``metric_direction`` value (lower_better or higher_better). The runtime
JSON-fallback path in dashboard_widget.py becomes dead code in practice
and is kept only as a safety net.
"""
import json
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT id, visual_config
        FROM dashboard_widget
        WHERE visual_config IS NOT NULL
          AND visual_config != ''
    """)
    invert_ids = []
    for wid, vc in cr.fetchall():
        try:
            data = json.loads(vc or '{}') or {}
        except (json.JSONDecodeError, TypeError):
            continue
        if data.get('trend_invert'):
            invert_ids.append(wid)

    if invert_ids:
        cr.execute(
            "UPDATE dashboard_widget SET metric_direction = 'lower_better' WHERE id = ANY(%s)",
            (invert_ids,),
        )
        _logger.info(
            "Migrated %s widget(s) from visual_config.trend_invert=true to metric_direction='lower_better'",
            len(invert_ids),
        )

    cr.execute("""
        UPDATE dashboard_widget
        SET metric_direction = 'higher_better'
        WHERE metric_direction IS NULL OR metric_direction = ''
    """)
    if cr.rowcount:
        _logger.info(
            "Backfilled %s widget(s) with metric_direction='higher_better' (default)",
            cr.rowcount,
        )
