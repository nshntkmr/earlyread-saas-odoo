# Phase 2: Database integration tests for SqlAssembler
# Runs assembled SQL against the real mv_hha_final_inhome materialized view.
#
# Usage:
#   cd "C:\Program Files\Odoo 19.0.20251113\server"
#   "C:\Program Files\Odoo 19.0.20251113\python\python.exe" odoo-bin shell -c odoo.conf -d odoo_db < "C:\Users\nisha\Odoo_Dev\dashboard_builder\tests\test_sql_assembler_db.py"

import sys
import json

# Import assembler and filter utilities
import os
for _p in [
    'C:\\Users\\nisha\\Odoo_Dev\\dashboard_builder\\services',
    'C:\\Users\\nisha\\Odoo_Dev\\posterra_portal\\utils',
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sql_assembler import SqlAssembler
from filter_builder import resolve_optional_clauses
from sql_params import build_sql_params


def assert_true(condition, message=''):
    if not condition:
        raise AssertionError(message)

# ── Setup: Load real filter defs and columns from DB ─────────────────────

print('Phase 2: Database Integration Tests for SqlAssembler')
print('=' * 60)

# Find the Inhome Market Overview page
page = env['dashboard.page'].sudo().search([('key', '=', 'inhome_overview')], limit=1)
if not page:
    print('SKIP: inhome_overview page not found. Run after creating the Inhome app.')
    sys.exit(0)

# Load real filter definitions from the page
filters = env['dashboard.page.filter'].sudo().search([
    ('page_id', '=', page.id),
    ('is_active', '=', True),
])
filter_defs = [{
    'param_name': f.param_name or f.field_name or '',
    'db_column': (
        f.schema_column_id.column_name
        if f.schema_column_id
        else f.field_name or f.param_name or ''
    ),
    'is_multiselect': f.is_multiselect,
    'col_type': (
        f.schema_column_id.data_type
        if f.schema_column_id
        else 'text'
    ),
} for f in filters if (f.param_name or f.field_name)]

print('Loaded %d filter defs from page %r' % (len(filter_defs), page.key))
for fd in filter_defs:
    print('  %s (%s, multi=%s, type=%s)' % (
        fd['param_name'], fd['db_column'], fd['is_multiselect'], fd['col_type']))

# Find the schema source
source = env['dashboard.schema.source'].sudo().search([
    ('table_name', '=', 'mv_hha_final_inhome')
], limit=1)
if not source:
    print('SKIP: mv_hha_final_inhome schema source not found.')
    sys.exit(0)

source_columns = {c.column_name for c in source.column_ids}
table_name = source.table_name
print('Loaded %d columns from schema source %r' % (len(source_columns), table_name))

# Multiselect param names (for build_sql_params)
multiselect_params = {fd['param_name'] for fd in filter_defs if fd['is_multiselect']}

# ── Helper to execute assembled SQL ──────────────────────────────────────

def execute_test(test_name, intent, filter_values, expected_checks):
    """Assemble SQL from intent, resolve filters, execute, and verify results."""
    print('\n--- %s ---' % test_name)
    try:
        asm = SqlAssembler(table_name, filter_defs, source_columns)
        result = asm.assemble(intent)
        sql = result['sql']

        # Build SQL params from filter values
        params = build_sql_params(filter_values, multiselect_params)

        # Resolve [[optional]] clauses
        resolved_sql = resolve_optional_clauses(sql, params)

        print('SQL (resolved):')
        for line in resolved_sql.strip().split('\n'):
            print('  %s' % line)

        # Execute
        env.cr.execute(resolved_sql, params)
        cols = [desc[0] for desc in env.cr.description]
        rows = env.cr.fetchall()

        print('Result: %d rows, columns=%s' % (len(rows), cols))
        if rows:
            for i, row in enumerate(rows[:5]):
                print('  Row %d: %s' % (i, dict(zip(cols, row))))

        # Run checks
        all_pass = True
        for check_name, check_fn in expected_checks.items():
            try:
                check_fn(cols, rows)
                print('  CHECK %s: PASS' % check_name)
            except AssertionError as e:
                print('  CHECK %s: FAIL - %s' % (check_name, e))
                all_pass = False

        return all_pass

    except Exception as e:
        print('  ERROR: %s' % e)
        return False


# ── Test 2.1: KPI with YoY — FFS 2024 All States ────────────────────────

passed = 0
failed = 0

ok = execute_test(
    'Test 2.1: KPI Total HHAs (FFS, 2024, All States)',
    intent={
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'value'},
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'prior_value', 'is_prior_year': True},
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': 'prior_value',
        'explanation': 'Total HHAs with YoY',
    },
    filter_values={
        'ffs_ma': 'FFS',
        'year': '2024',
        'hha_state': '',
        'hha_county': '',
        'hha_ccn': '',
        'hha_brand_name': '',
        'priority_group': '',
        'bd_priority_tier_overall': '',
        'bd_priority_frequency': '',
        'bd_priority_intensity': '',
        'bd_priority_stability': '',
    },
    expected_checks={
        'has_rows': lambda cols, rows: (
            assert_true(len(rows) == 1, 'Expected 1 row, got %d' % len(rows))
        ),
        'value_positive': lambda cols, rows: (
            assert_true(rows[0][cols.index('value')] > 0,
                        'value should be > 0, got %s' % rows[0][cols.index('value')])
        ),
        'prior_positive': lambda cols, rows: (
            assert_true(rows[0][cols.index('prior_value')] > 0,
                        'prior_value should be > 0, got %s' % rows[0][cols.index('prior_value')])
        ),
        'reasonable_change': lambda cols, rows: (
            assert_true(
                abs(rows[0][cols.index('value')] - rows[0][cols.index('prior_value')])
                / max(rows[0][cols.index('prior_value')], 1) < 1.0,
                'YoY change > 100%% is suspicious: value=%s, prior=%s' % (
                    rows[0][cols.index('value')], rows[0][cols.index('prior_value')])
            )
        ),
    },
)
if ok: passed += 1
else: failed += 1


# ── Test 2.2: KPI with YoY — FFS 2024 California ────────────────────────

ok = execute_test(
    'Test 2.2: KPI Total HHAs (FFS, 2024, California)',
    intent={
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'value'},
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'prior_value', 'is_prior_year': True},
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': 'prior_value',
        'explanation': 'CA HHAs with YoY',
    },
    filter_values={
        'ffs_ma': 'FFS',
        'year': '2024',
        'hha_state': 'California',
        'hha_county': '',
        'hha_ccn': '',
        'hha_brand_name': '',
        'priority_group': '',
        'bd_priority_tier_overall': '',
        'bd_priority_frequency': '',
        'bd_priority_intensity': '',
        'bd_priority_stability': '',
    },
    expected_checks={
        'has_rows': lambda cols, rows: (
            assert_true(len(rows) == 1, 'Expected 1 row')
        ),
        'value_less_than_all': lambda cols, rows: (
            assert_true(rows[0][cols.index('value')] < 5000,
                        'CA alone should be < 5000 HHAs, got %s' % rows[0][cols.index('value')])
        ),
    },
)
if ok: passed += 1
else: failed += 1


# ── Test 2.3: KPI with Priority Group filter ─────────────────────────────

ok = execute_test(
    'Test 2.3: KPI Total HHAs (FFS, 2025, Tier 1)',
    intent={
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'value'},
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': '',
        'explanation': 'Tier 1 HHAs in 2025',
    },
    filter_values={
        'ffs_ma': 'FFS',
        'year': '2025',
        'hha_state': '',
        'hha_county': '',
        'hha_ccn': '',
        'hha_brand_name': '',
        'priority_group': 'Tier 1',
        'bd_priority_tier_overall': '',
        'bd_priority_frequency': '',
        'bd_priority_intensity': '',
        'bd_priority_stability': '',
    },
    expected_checks={
        'has_rows': lambda cols, rows: (
            assert_true(len(rows) == 1, 'Expected 1 row')
        ),
        'value_positive': lambda cols, rows: (
            assert_true(rows[0][cols.index('value')] > 0,
                        'Tier 1 count should be > 0 for 2025 FFS, got %s' % rows[0][cols.index('value')])
        ),
    },
)
if ok: passed += 1
else: failed += 1


# ── Test 2.4: Bar chart — admits by state ────────────────────────────────

ok = execute_test(
    'Test 2.4: Bar Chart — Admits by State (FFS, 2024)',
    intent={
        'mode': 'simple',
        'measures': [
            {'expression': 'SUM(hha_admits)', 'alias': 'admits'},
        ],
        'dimensions': [
            {'column': 'hha_state'},
        ],
        'order_by': [{'column': 'admits', 'direction': 'DESC'}],
        'x_column': 'hha_state',
        'y_columns': 'admits',
        'explanation': 'Admits by state',
    },
    filter_values={
        'ffs_ma': 'FFS',
        'year': '2024',
        'hha_state': '',
        'hha_county': '',
        'hha_ccn': '',
        'hha_brand_name': '',
        'priority_group': '',
        'bd_priority_tier_overall': '',
        'bd_priority_frequency': '',
        'bd_priority_intensity': '',
        'bd_priority_stability': '',
    },
    expected_checks={
        'has_5_states': lambda cols, rows: (
            assert_true(len(rows) == 5, 'Expected 5 states, got %d' % len(rows))
        ),
        'admits_positive': lambda cols, rows: (
            assert_true(all(r[cols.index('admits')] > 0 for r in rows),
                        'All states should have positive admits')
        ),
    },
)
if ok: passed += 1
else: failed += 1


# ── Test 2.5: Donut — priority group distribution ────────────────────────

ok = execute_test(
    'Test 2.5: Donut — Priority Group Distribution (FFS, 2024)',
    intent={
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'hha_count'},
        ],
        'dimensions': [
            {'column': 'priority_group'},
        ],
        'order_by': [{'column': 'hha_count', 'direction': 'DESC'}],
        'x_column': 'priority_group',
        'y_columns': 'hha_count',
        'explanation': 'HHAs by priority group',
    },
    filter_values={
        'ffs_ma': 'FFS',
        'year': '2024',
        'hha_state': '',
        'hha_county': '',
        'hha_ccn': '',
        'hha_brand_name': '',
        'priority_group': '',
        'bd_priority_tier_overall': '',
        'bd_priority_frequency': '',
        'bd_priority_intensity': '',
        'bd_priority_stability': '',
    },
    expected_checks={
        'has_groups': lambda cols, rows: (
            assert_true(len(rows) >= 2, 'Expected at least 2 priority groups, got %d' % len(rows))
        ),
        'groups_known': lambda cols, rows: (
            assert_true(
                all(r[cols.index('priority_group')] in ('Tier 1', 'Tier 2', 'Watchlist', None, '')
                    for r in rows),
                'Unknown priority groups: %s' % [r[cols.index('priority_group')] for r in rows]
            )
        ),
    },
)
if ok: passed += 1
else: failed += 1


# ── Test 2.6: Therapy Share % with YoY ───────────────────────────────────

ok = execute_test(
    'Test 2.6: KPI Therapy Share % (FFS, 2024, YoY)',
    intent={
        'mode': 'simple',
        'measures': [
            {
                'expression': 'ROUND(SUM(pt_visit+ot_visit+slp_visit)::numeric / NULLIF(SUM(hha_visits),0) * 100, 2)',
                'alias': 'value',
            },
            {
                'expression': 'ROUND(SUM(pt_visit+ot_visit+slp_visit)::numeric / NULLIF(SUM(hha_visits),0) * 100, 2)',
                'alias': 'prior_value',
                'is_prior_year': True,
            },
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': 'prior_value',
        'explanation': 'Therapy share with YoY',
    },
    filter_values={
        'ffs_ma': 'FFS',
        'year': '2024',
        'hha_state': '',
        'hha_county': '',
        'hha_ccn': '',
        'hha_brand_name': '',
        'priority_group': '',
        'bd_priority_tier_overall': '',
        'bd_priority_frequency': '',
        'bd_priority_intensity': '',
        'bd_priority_stability': '',
    },
    expected_checks={
        'has_rows': lambda cols, rows: (
            assert_true(len(rows) == 1, 'Expected 1 row')
        ),
        'value_is_percentage': lambda cols, rows: (
            assert_true(0 < rows[0][cols.index('value')] < 100,
                        'Therapy share should be 0-100%%, got %s' % rows[0][cols.index('value')])
        ),
        'prior_is_percentage': lambda cols, rows: (
            assert_true(0 < rows[0][cols.index('prior_value')] < 100,
                        'Prior therapy share should be 0-100%%, got %s' % rows[0][cols.index('prior_value')])
        ),
    },
)
if ok: passed += 1
else: failed += 1


# ── Test 2.7: Extra conditions — 4+ star HHAs ───────────────────────────

ok = execute_test(
    'Test 2.7: KPI HHAs with 4+ Star Rating (FFS, 2024)',
    intent={
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'value'},
        ],
        'dimensions': [],
        'extra_conditions': ["hha_rating >= '4'"],
        'x_column': 'value',
        'y_columns': '',
        'explanation': 'HHAs with 4+ star rating',
    },
    filter_values={
        'ffs_ma': 'FFS',
        'year': '2024',
        'hha_state': '',
        'hha_county': '',
        'hha_ccn': '',
        'hha_brand_name': '',
        'priority_group': '',
        'bd_priority_tier_overall': '',
        'bd_priority_frequency': '',
        'bd_priority_intensity': '',
        'bd_priority_stability': '',
    },
    expected_checks={
        'has_rows': lambda cols, rows: (
            assert_true(len(rows) == 1, 'Expected 1 row')
        ),
        'value_less_than_total': lambda cols, rows: (
            assert_true(rows[0][cols.index('value')] < 5400,
                        '4+ star HHAs should be less than total, got %s' % rows[0][cols.index('value')])
        ),
    },
)
if ok: passed += 1
else: failed += 1


# ── Test 2.8: Table — top 10 counties ────────────────────────────────────

ok = execute_test(
    'Test 2.8: Table — Top 10 Counties by Admits (FFS, 2024)',
    intent={
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'hha_count'},
            {'expression': 'SUM(hha_admits)', 'alias': 'total_admits'},
            {
                'expression': 'ROUND(SUM(pt_visit+ot_visit+slp_visit)::numeric / NULLIF(SUM(hha_visits),0) * 100, 1)',
                'alias': 'therapy_share_pct',
            },
        ],
        'dimensions': [
            {'column': 'hha_county'},
            {'column': 'hha_state'},
        ],
        'order_by': [{'column': 'total_admits', 'direction': 'DESC'}],
        'limit': 10,
        'x_column': 'hha_county',
        'y_columns': 'hha_count,total_admits,therapy_share_pct',
        'explanation': 'Top 10 counties',
    },
    filter_values={
        'ffs_ma': 'FFS',
        'year': '2024',
        'hha_state': '',
        'hha_county': '',
        'hha_ccn': '',
        'hha_brand_name': '',
        'priority_group': '',
        'bd_priority_tier_overall': '',
        'bd_priority_frequency': '',
        'bd_priority_intensity': '',
        'bd_priority_stability': '',
    },
    expected_checks={
        'has_10_rows': lambda cols, rows: (
            assert_true(len(rows) == 10, 'Expected 10 rows, got %d' % len(rows))
        ),
        'ordered_desc': lambda cols, rows: (
            assert_true(
                rows[0][cols.index('total_admits')] >= rows[-1][cols.index('total_admits')],
                'Should be ordered by admits DESC'
            )
        ),
    },
)
if ok: passed += 1
else: failed += 1


# ── Summary ──────────────────────────────────────────────────────────────

print('\n' + '=' * 60)
print('Phase 2 Results: %d passed, %d failed out of %d tests.' % (
    passed, failed, passed + failed))
if failed:
    print('SOME TESTS FAILED — review output above.')
else:
    print('ALL TESTS PASSED.')


