# -*- coding: utf-8 -*-
"""Unit tests for SqlAssembler — Phase 1 of the test plan.

Run standalone (no Odoo required):
    cd dashboard_builder/tests
    python test_sql_assembler.py

Or via pytest:
    pytest dashboard_builder/tests/test_sql_assembler.py -v
"""

import sys
import os

# Direct import of the assembler module (no Odoo dependency)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from sql_assembler import SqlAssembler


# ── Test filter definitions (reusable across tests) ─────────────────────────
INHOME_FILTERS = [
    {'param_name': 'ffs_ma', 'db_column': 'ffs_ma', 'is_multiselect': True, 'col_type': 'text'},
    {'param_name': 'year', 'db_column': 'year', 'is_multiselect': True, 'col_type': 'bigint'},
    {'param_name': 'hha_state', 'db_column': 'hha_state', 'is_multiselect': True, 'col_type': 'text'},
    {'param_name': 'hha_county', 'db_column': 'hha_county', 'is_multiselect': True, 'col_type': 'text'},
    {'param_name': 'hha_ccn', 'db_column': 'hha_ccn', 'is_multiselect': True, 'col_type': 'bigint'},
    {'param_name': 'hha_brand_name', 'db_column': 'hha_brand_name', 'is_multiselect': True, 'col_type': 'text'},
    {'param_name': 'priority_group', 'db_column': 'priority_group', 'is_multiselect': True, 'col_type': 'text'},
    {'param_name': 'bd_priority_tier_overall', 'db_column': 'bd_priority_tier_overall', 'is_multiselect': True, 'col_type': 'text'},
    {'param_name': 'bd_priority_frequency', 'db_column': 'bd_priority_frequency', 'is_multiselect': True, 'col_type': 'text'},
    {'param_name': 'bd_priority_intensity', 'db_column': 'bd_priority_intensity', 'is_multiselect': True, 'col_type': 'text'},
    {'param_name': 'bd_priority_stability', 'db_column': 'bd_priority_stability', 'is_multiselect': True, 'col_type': 'text'},
]

MIXED_FILTERS = [
    {'param_name': 'year', 'db_column': 'year', 'is_multiselect': True, 'col_type': 'bigint'},
    {'param_name': 'ffs_ma', 'db_column': 'ffs_ma', 'is_multiselect': False, 'col_type': 'text'},
    {'param_name': 'hha_state', 'db_column': 'hha_state', 'is_multiselect': False, 'col_type': 'text'},
    {'param_name': 'hha_ccn', 'db_column': 'hha_ccn', 'is_multiselect': True, 'col_type': 'bigint'},
]

TABLE = 'mv_hha_final_inhome'
COLUMNS = {
    'hha_ccn', 'hha_state', 'hha_county', 'hha_city', 'hha_brand_name',
    'year', 'ffs_ma', 'hha_admits', 'hha_visits', 'pt_visit', 'ot_visit',
    'slp_visit', 'priority_group', 'bd_priority_tier_overall',
    'bd_priority_frequency', 'bd_priority_intensity', 'bd_priority_stability',
    'hha_rating', 'offers_physical_therapy_services', 'therapy_share',
}


def _asm(filters=None):
    return SqlAssembler(TABLE, filters or INHOME_FILTERS, COLUMNS)


# =========================================================================
# Test 1.1: Simple KPI (no YoY)
# =========================================================================
def test_1_1_simple_kpi():
    intent = {
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'value'},
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': '',
        'explanation': 'Count of unique HHAs',
    }
    result = _asm().assemble(intent)
    sql = result['sql']

    assert 'COUNT(DISTINCT hha_ccn) AS value' in sql, \
        'SELECT should contain the measure'
    assert 'FROM "mv_hha_final_inhome"' in sql, \
        'FROM clause should reference the table'
    assert 'GROUP BY' not in sql, \
        'No GROUP BY for KPI without dimensions'
    assert '[[AND "ffs_ma" IN %(ffs_ma)s]]' in sql, \
        'Multiselect filter should use IN with [[optional]]'
    assert '_year_prior' not in sql, \
        'No YoY reference when no prior_year measure'
    print('  PASS: test_1_1_simple_kpi')


# =========================================================================
# Test 1.2: Simple KPI with YoY
# =========================================================================
def test_1_2_kpi_with_yoy():
    intent = {
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'value'},
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'prior_value', 'is_prior_year': True},
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': 'prior_value',
        'explanation': 'HHA count with YoY',
    }
    result = _asm().assemble(intent)
    sql = result['sql']

    # Verify year scoping with parentheses
    assert '("year"::text IN %(year)s OR "year"::text = %(_year_prior)s::text)' in sql, \
        'Year scope must have parentheses around OR: got\n%s' % sql
    # Verify current year CASE WHEN
    assert 'CASE WHEN "year"::text IN %(year)s THEN hha_ccn END' in sql, \
        'Current year measure should be wrapped in CASE WHEN'
    # Verify prior year CASE WHEN
    assert 'CASE WHEN "year"::text = %(_year_prior)s::text THEN hha_ccn END' in sql, \
        'Prior year measure should be wrapped in CASE WHEN'
    # Verify year filter is NOT duplicated in optional clauses
    assert sql.count('%(year)s') == 2, \
        'Year param should appear exactly 2 times (scope + current CASE): got %d' % sql.count('%(year)s')
    print('  PASS: test_1_2_kpi_with_yoy')


# =========================================================================
# Test 1.3: Bar chart with GROUP BY
# =========================================================================
def test_1_3_bar_chart():
    intent = {
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
    }
    result = _asm().assemble(intent)
    sql = result['sql']

    assert '"hha_state"' in sql, 'SELECT should include dimension'
    assert 'SUM(hha_admits) AS admits' in sql, 'SELECT should include measure'
    assert 'GROUP BY "hha_state"' in sql, 'GROUP BY required for dimensional query'
    assert 'ORDER BY admits DESC' in sql, 'ORDER BY should be present'
    print('  PASS: test_1_3_bar_chart')


# =========================================================================
# Test 1.4: Multiselect vs single-select operators
# =========================================================================
def test_1_4_mixed_operators():
    intent = {
        'mode': 'simple',
        'measures': [{'expression': 'COUNT(*)', 'alias': 'cnt'}],
        'dimensions': [],
        'x_column': 'cnt',
        'y_columns': '',
        'explanation': 'Count',
    }
    result = SqlAssembler(TABLE, MIXED_FILTERS, COLUMNS).assemble(intent)
    sql = result['sql']

    # Multiselect: IN
    assert '[[AND "year"::text IN %(year)s]]' in sql, \
        'Multiselect year should use IN with ::text cast'
    assert '[[AND "hha_ccn"::text IN %(hha_ccn)s]]' in sql, \
        'Multiselect hha_ccn should use IN with ::text cast'
    # Single-select: =
    assert '[[AND "ffs_ma" = %(ffs_ma)s]]' in sql, \
        'Single-select ffs_ma should use = : got\n%s' % sql
    assert '[[AND "hha_state" = %(hha_state)s]]' in sql, \
        'Single-select hha_state should use = : got\n%s' % sql
    print('  PASS: test_1_4_mixed_operators')


# =========================================================================
# Test 1.5: Extra conditions
# =========================================================================
def test_1_5_extra_conditions():
    intent = {
        'mode': 'simple',
        'measures': [{'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'value'}],
        'dimensions': [],
        'extra_conditions': [
            "hha_rating >= '4'",
            "offers_physical_therapy_services = 'Yes'",
        ],
        'x_column': 'value',
        'y_columns': '',
        'explanation': 'HHAs with 4+ stars offering PT',
    }
    result = _asm().assemble(intent)
    sql = result['sql']

    assert "hha_rating >= '4'" in sql, 'Extra condition should be in WHERE'
    assert "offers_physical_therapy_services = 'Yes'" in sql, 'Extra condition should be in WHERE'
    assert '[[AND "ffs_ma" IN %(ffs_ma)s]]' in sql, 'Filter clauses should still be present'
    print('  PASS: test_1_5_extra_conditions')


# =========================================================================
# Test 1.6: Therapy share ratio with YoY
# =========================================================================
def test_1_6_ratio_yoy():
    expr = 'ROUND(SUM(pt_visit+ot_visit+slp_visit)::numeric / NULLIF(SUM(hha_visits),0) * 100, 2)'
    intent = {
        'mode': 'simple',
        'measures': [
            {'expression': expr, 'alias': 'value'},
            {'expression': expr, 'alias': 'prior_value', 'is_prior_year': True},
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': 'prior_value',
        'explanation': 'Therapy share % with YoY',
    }
    result = _asm().assemble(intent)
    sql = result['sql']

    # Prior value measure: both SUM calls should be wrapped
    assert 'CASE WHEN "year"::text = %(_year_prior)s::text THEN pt_visit+ot_visit+slp_visit END' in sql, \
        'Numerator SUM in prior should be wrapped'
    assert 'CASE WHEN "year"::text = %(_year_prior)s::text THEN hha_visits END' in sql, \
        'Denominator SUM in prior should be wrapped'
    # Current value measure: both SUM calls should also be wrapped (for current year)
    assert 'CASE WHEN "year"::text IN %(year)s THEN pt_visit+ot_visit+slp_visit END' in sql, \
        'Numerator SUM in current should be wrapped'
    print('  PASS: test_1_6_ratio_yoy')


# =========================================================================
# Test 1.7: Year scope with YoY — verify parentheses
# =========================================================================
def test_1_7_year_parentheses():
    intent = {
        'mode': 'simple',
        'measures': [
            {'expression': 'SUM(hha_admits)', 'alias': 'value'},
            {'expression': 'SUM(hha_admits)', 'alias': 'prior_value', 'is_prior_year': True},
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': 'prior_value',
        'explanation': 'Admits YoY',
    }
    result = _asm().assemble(intent)
    sql = result['sql']

    # The critical check: OR must be inside parentheses
    # This was the root cause bug
    where_idx = sql.index('WHERE')
    where_part = sql[where_idx:]

    assert 'WHERE 1=1' in where_part, \
        'WHERE must start with 1=1, got:\n%s' % where_part
    assert 'OR "year"' in where_part, 'OR for prior year must be present'

    # Find the year scope line and verify it's wrapped in parens
    year_line = [l.strip() for l in where_part.split('\n') if 'OR "year"' in l][0]
    assert year_line.startswith('AND (') or year_line.startswith('('), \
        'Year scope line must be wrapped in parens: got %r' % year_line
    assert year_line.endswith(')'), \
        'Year scope line must end with ): got %r' % year_line
    print('  PASS: test_1_7_year_parentheses')


# =========================================================================
# Test 1.8: Numeric column in multiselect
# =========================================================================
def test_1_8_numeric_multiselect():
    filters = [
        {'param_name': 'hha_ccn', 'db_column': 'hha_ccn', 'is_multiselect': True, 'col_type': 'bigint'},
    ]
    intent = {
        'mode': 'simple',
        'measures': [{'expression': 'COUNT(*)', 'alias': 'cnt'}],
        'dimensions': [],
        'x_column': 'cnt',
        'y_columns': '',
        'explanation': 'Count',
    }
    result = SqlAssembler(TABLE, filters, COLUMNS).assemble(intent)
    sql = result['sql']

    assert '"hha_ccn"::text IN %(hha_ccn)s' in sql, \
        'Numeric multiselect should have ::text cast: got\n%s' % sql
    print('  PASS: test_1_8_numeric_multiselect')


# =========================================================================
# Test 1.9: Column not in schema source — skipped
# =========================================================================
def test_1_9_missing_column():
    filters = [
        {'param_name': 'unknown', 'db_column': 'nonexistent_col', 'is_multiselect': True, 'col_type': 'text'},
        {'param_name': 'hha_state', 'db_column': 'hha_state', 'is_multiselect': True, 'col_type': 'text'},
    ]
    intent = {
        'mode': 'simple',
        'measures': [{'expression': 'COUNT(*)', 'alias': 'cnt'}],
        'dimensions': [],
        'x_column': 'cnt',
        'y_columns': '',
        'explanation': 'Count',
    }
    result = SqlAssembler(TABLE, filters, COLUMNS).assemble(intent)
    sql = result['sql']

    assert 'nonexistent_col' not in sql, \
        'Column not in schema source should be skipped'
    assert '"hha_state" IN %(hha_state)s' in sql, \
        'Valid column should still be present'
    print('  PASS: test_1_9_missing_column')


# =========================================================================
# Test 1.10: Union ALL mode
# =========================================================================
def test_1_10_union_all():
    intent = {
        'mode': 'union_all',
        'measures': [],
        'union_blocks': [
            {
                'measures': [{'expression': 'SUM(hha_admits)', 'alias': 'value'}],
                'label': 'Total Admits',
            },
            {
                'measures': [{'expression': 'SUM(hha_visits)', 'alias': 'value'}],
                'label': 'Total Visits',
            },
        ],
        'x_column': 'metric_name',
        'y_columns': 'value',
        'explanation': 'Two metrics via UNION ALL',
    }
    result = _asm().assemble(intent)
    sql = result['sql']

    assert 'UNION ALL' in sql, 'Should contain UNION ALL'
    assert "'Total Admits' AS metric_name" in sql, 'First block label'
    assert "'Total Visits' AS metric_name" in sql, 'Second block label'
    assert sql.count('FROM "mv_hha_final_inhome"') == 2, \
        'Each block should have its own FROM'
    print('  PASS: test_1_10_union_all')


# =========================================================================
# Test 1.11: Raw override mode
# =========================================================================
def test_1_11_raw_override():
    raw = 'SELECT * FROM mv_hha_final_inhome {where_clause} LIMIT 10'
    intent = {
        'mode': 'raw_override',
        'measures': [],
        'raw_sql': raw,
        'x_column': '',
        'y_columns': '',
        'explanation': 'Raw SQL passthrough',
    }
    result = _asm().assemble(intent)
    assert result['sql'] == raw, 'Raw SQL should pass through as-is'
    print('  PASS: test_1_11_raw_override')


# =========================================================================
# Test 1.12: Invalid table name rejected
# =========================================================================
def test_1_12_invalid_table():
    try:
        SqlAssembler('DROP TABLE users; --', [], None)
        assert False, 'Should have raised ValueError'
    except ValueError as e:
        assert 'Invalid table name' in str(e)
    print('  PASS: test_1_12_invalid_table')


# =========================================================================
# Test 1.13: COUNT DISTINCT rewriting for YoY
# =========================================================================
def test_1_13_count_distinct_yoy():
    intent = {
        'mode': 'simple',
        'measures': [
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'value'},
            {'expression': 'COUNT(DISTINCT hha_ccn)', 'alias': 'prior_value', 'is_prior_year': True},
        ],
        'dimensions': [],
        'x_column': 'value',
        'y_columns': 'prior_value',
        'explanation': 'Count distinct with YoY',
    }
    result = _asm().assemble(intent)
    sql = result['sql']

    # Current year
    assert 'COUNT(DISTINCT CASE WHEN "year"::text IN %(year)s THEN hha_ccn END) AS value' in sql, \
        'Current COUNT DISTINCT should be wrapped: got\n%s' % sql
    # Prior year
    assert 'COUNT(DISTINCT CASE WHEN "year"::text = %(_year_prior)s::text THEN hha_ccn END) AS prior_value' in sql, \
        'Prior COUNT DISTINCT should be wrapped: got\n%s' % sql
    print('  PASS: test_1_13_count_distinct_yoy')


# =========================================================================
# Run all tests
# =========================================================================
if __name__ == '__main__':
    tests = [
        test_1_1_simple_kpi,
        test_1_2_kpi_with_yoy,
        test_1_3_bar_chart,
        test_1_4_mixed_operators,
        test_1_5_extra_conditions,
        test_1_6_ratio_yoy,
        test_1_7_year_parentheses,
        test_1_8_numeric_multiselect,
        test_1_9_missing_column,
        test_1_10_union_all,
        test_1_11_raw_override,
        test_1_12_invalid_table,
        test_1_13_count_distinct_yoy,
    ]

    print('Running SqlAssembler unit tests...\n')
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except (AssertionError, Exception) as e:
            print('  FAIL: %s — %s' % (test.__name__, e))
            failed += 1

    print('\n%d passed, %d failed out of %d tests.' % (passed, failed, len(tests)))
    if failed:
        sys.exit(1)
