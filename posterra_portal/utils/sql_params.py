# -*- coding: utf-8 -*-
"""
Shared SQL parameter conversion utility.

Converts filter values (strings from URL params) into SQL-ready params
for psycopg2. Used by portal.py, widget_api.py, and the designer preview.

This is the SINGLE source of truth for how filter values become SQL params.
Any change here automatically affects all three consumers.
"""


def build_sql_params(filter_values_by_name, multiselect_params=None):
    """Convert filter values dict into SQL-ready params.

    Args:
        filter_values_by_name: dict {param_name: value_string}
            All values are expected to be strings (or None).
            Multi-select values are comma-separated: "FFS,MA".

        multiselect_params: set of param_name strings that are multi-select
            filters. Read from dashboard.page.filter.is_multiselect at runtime.
            When None or empty, all params are treated as single-select.

    Returns:
        dict of SQL params ready for psycopg2 cr.execute(sql, params):
        - Multi-select params: CSV → tuple for IN %(param)s
          Empty/all → ('__all__',) sentinel tuple
        - Single-select params: plain string for = %(param)s
        - Helper params for each multi-select key:
          _<key>_single: int or None (when exactly 1 numeric value selected)
          _<key>_prior:  int or None (single value minus 1, for YoY)

    Examples:
        >>> build_sql_params({'year': '2023', 'ffs_ma': 'FFS'}, {'year'})
        {'year': ('2023',), '_year_single': 2023, '_year_prior': 2022, 'ffs_ma': 'FFS'}

        >>> build_sql_params({'year': '', 'hha_ccn': '017014,047114'}, {'year', 'hha_ccn'})
        {'year': ('__all__',), '_year_single': None, '_year_prior': None,
         'hha_ccn': ('017014', '047114'), '_hha_ccn_single': None, '_hha_ccn_prior': None}
    """
    multiselect_params = multiselect_params or set()
    sql_params = {}

    for key, val in filter_values_by_name.items():
        if key in multiselect_params:
            if val and val not in ('', 'all'):
                parts = tuple(v.strip() for v in val.split(',') if v.strip())
                sql_params[key] = parts
                # Helper params for single-value numeric selections
                # (e.g. year=2023 → _year_single=2023, _year_prior=2022)
                numeric = [v for v in parts if v.isdigit()]
                if len(parts) == 1 and numeric:
                    sql_params['_%s_single' % key] = int(numeric[0])
                    sql_params['_%s_prior' % key] = int(numeric[0]) - 1
                else:
                    sql_params['_%s_single' % key] = None
                    sql_params['_%s_prior' % key] = None
            else:
                sql_params[key] = ('__all__',)
                sql_params['_%s_single' % key] = None
                sql_params['_%s_prior' % key] = None
        else:
            sql_params[key] = val

    # Ensure derived helper params (e.g. _year_single, _year_prior) are
    # NULL-safe: empty strings become None so psycopg2 sends SQL NULL
    # instead of '' which would crash on numeric column comparisons.
    for key in list(sql_params):
        if key.startswith('_') and sql_params[key] == '':
            sql_params[key] = None

    return sql_params
