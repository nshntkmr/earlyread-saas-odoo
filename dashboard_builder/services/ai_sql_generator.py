# -*- coding: utf-8 -*-
"""
AI SQL Generator — Natural Language to SQL via Claude on Azure AI Foundry

Assembles schema context dynamically from the selected app/page/source
and sends it to Claude Sonnet 4.6 to generate dashboard widget SQL.

Everything is read from the live system at request time — no hardcoding.
Different apps, pages, tables, and filters produce different SQL.
"""

import json
import logging

_logger = logging.getLogger(__name__)


# ── System prompt — generic SQL rules for all requests ──────────────────────

SYSTEM_PROMPT = """You are a PostgreSQL SQL expert generating queries for healthcare analytics dashboards.

RULES — follow these EXACTLY:
1. Only SELECT or WITH statements. Never INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
2. Use %(param_name)s for filter placeholders (psycopg2 named parameter syntax).
3. Filter operator MUST match the filter type shown in AVAILABLE FILTER PARAMETERS:
   - [MULTISELECT] filters: ALWAYS use IN %(param)s. Value is a tuple like ('FFS', 'MA').
     Optional clause: [[AND col IN %(param)s]]
   - Single-select filters (no [MULTISELECT] tag): ALWAYS use = %(param)s. Value is a plain string.
     Optional clause: [[AND col = %(param)s]]
   NEVER use IN with a single-select filter — it causes a SQL syntax error.
   NEVER use = with a multiselect filter — it cannot bind tuples.
4. The [[...]] wrapper means: include this clause only when the param has a value.
   When the user selects "All", the entire [[...]] clause is dropped.
5. Use NULLIF(expr, 0) for ALL division — division by zero is common when filters narrow to sparse data.
6. For rates and ratios: ALWAYS compute as SUM(numerator_col) / NULLIF(SUM(denominator_col), 0) * multiplier.
   NEVER use AVG() on a pre-computed rate column (like timely_access_pct or hospitalization_rate).
   Pre-computed rates have different denominators per row — averaging them is mathematically wrong.
7. Use %% for literal percent signs in string literals (psycopg2 escapes % as %%).
   Example: 'Target: 85%%' not 'Target: 85%'.
8. For multi-metric output (bullet gauge, RAG scorecard, multi-ring): use UNION ALL with one SELECT block per metric.
9. Return column names that match the chart type's expected format exactly.
10. When benchmark/peer comparison is requested: use CROSS JOIN with the same table aliased as 'peer'.
    Scope the peer group using [[AND peer.hha_state IN %(hha_state)s]] optional clauses.

COLUMN INTELLIGENCE:
- Columns marked "NEVER AVG" are pre-computed rates. NEVER use AVG() on them.
  Instead, find the paired count columns (numerator/denominator) and compute:
  SUM(numerator) / NULLIF(SUM(denominator), 0) * 100.
- Columns with role "ratio_numerator" have a paired denominator column listed.
  Use these pairs for correct weighted rate computation.
- Columns with role "additive_measure" are safe to SUM directly.
- Columns with role "dimension" are for grouping (GROUP BY, X-axis).
- Columns with role "identifier" are for filtering (WHERE), not aggregation.

SYSTEM HELPER PARAMS (auto-generated for every multiselect filter):
- For each multiselect filter param %(param)s, the system auto-generates:
  - %(_param_single)s — integer when exactly 1 value selected, else NULL
  - %(_param_prior)s  — integer value minus 1 (for YoY comparison), else NULL
  Example: If year filter has "2023" selected:
    %(year)s = ('2023',)       — use with IN
    %(_year_single)s = 2023    — use with = for single-year logic
    %(_year_prior)s = 2022     — use for prior year comparison
  If year filter has "2022,2023" selected:
    %(year)s = ('2022','2023') — use with IN
    %(_year_single)s = NULL    — multiple years, no single value
    %(_year_prior)s = NULL     — no prior year available

{WHERE_CLAUSE} MACRO:
- When the widget has a schema_source_id, use {where_clause} in the SQL.
  The system auto-generates WHERE from ALL active page filters.
  Example: SELECT ... FROM mv_table WHERE {where_clause}
  This is preferred for simple single-table queries.
- Use manual %(param)s only when you need different filter logic per table
  (e.g., CROSS JOIN peer benchmark with different scoping).

STATUS KPI PATTERN:
- Status KPI expects columns: value [, prior_value]
- Use %(_year_prior)s for YoY comparison when year filter is available.
- The React component computes % change and trend arrow automatically.
- Return raw numbers, NOT pre-formatted text.
"""


# ── Tool definition for structured output ──────────────────────────────────

GENERATE_SQL_TOOL = {
    'name': 'generate_sql',
    'description': 'Generate a PostgreSQL SQL query for a dashboard widget. '
                   'The SQL must be valid PostgreSQL with psycopg2 named parameters.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'sql': {
                'type': 'string',
                'description': 'The complete SQL query. Must be a valid SELECT or WITH statement.',
            },
            'x_column': {
                'type': 'string',
                'description': 'The column name for X axis / labels / metric name.',
            },
            'y_columns': {
                'type': 'string',
                'description': 'Comma-separated column names for Y axis / values / benchmark.',
            },
            'series_column': {
                'type': 'string',
                'description': 'Column name for series/grouping (optional). '
                               'Only set when the chart type supports multiple series '
                               'and the query groups data by a category dimension '
                               '(e.g., ffs_ma to split FFS vs MA). Leave empty if not applicable.',
            },
            'explanation': {
                'type': 'string',
                'description': 'Brief explanation of what the query does, what aggregations are used, '
                               'and how filters/benchmarks are handled.',
            },
            'warnings': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Any warnings about the query (performance, data quality, etc.).',
            },
        },
        'required': ['sql', 'x_column', 'y_columns', 'explanation'],
    },
}

# ── Suggest tool — for generating schema-aware query suggestions ───────────

SUGGEST_TOOL = {
    'name': 'suggest_queries',
    'description': 'Generate natural language query suggestions for a dashboard widget '
                   'based on the chart type and available data columns.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'suggestions': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'List of 10 natural language descriptions of useful queries '
                               'for this chart type using the available columns. '
                               'Use actual column names from the schema. '
                               'Be specific and practical — each suggestion should describe '
                               'a concrete, useful visualization. '
                               'Order from most common/useful to most specialized.',
            },
        },
        'required': ['suggestions'],
    },
}


# ── Intent system prompt — for the new split pipeline ────────────────────

INTENT_SYSTEM_PROMPT = """You are a healthcare analytics query designer.

Your job is to describe WHAT to compute, NOT how to filter. The system handles all filtering (WHERE clauses, year scoping, filter operators) automatically. You NEVER write WHERE clauses.

RULES:
1. Return structured intent using the generate_sql_intent tool.
2. For each measure, provide a SQL aggregate expression (e.g. SUM(hha_admits), COUNT(DISTINCT hha_ccn)).
3. For year-over-year comparison: add a second measure with the SAME expression and set is_prior_year=true.
   The system will automatically wrap it in CASE WHEN for the prior year.
4. For rates and ratios: compute as SUM(numerator) / NULLIF(SUM(denominator), 0) * multiplier.
   NEVER use AVG() on pre-computed rate columns (marked NEVER AVG in column metadata).
5. extra_conditions is ONLY for hardcoded business logic from the user's request
   (e.g. "hha_rating >= '4'", "offers_physical_therapy_services = 'Yes'").
   NEVER put page filter parameters in extra_conditions — they are handled automatically.
6. Use mode="simple" for single SELECT queries (KPI, bar, line, donut, table, scatter, etc.).
7. Use mode="union_all" for multi-metric widgets (bullet gauge, RAG scorecard, multi-ring gauge).
8. Use mode="cte" for sparkline KPIs or complex queries requiring WITH clauses.
9. Use mode="raw_override" only as a last resort when no other mode fits.

COLUMN INTELLIGENCE:
- Columns marked "NEVER AVG" are pre-computed rates. Compute from numerator/denominator pairs.
- Columns with role "additive_measure" are safe to SUM directly.
- Columns with role "dimension" are for grouping (GROUP BY / X-axis).
- Columns with role "identifier" are for filtering, not aggregation.
"""

# ── Intent tool definition ───────────────────────────────────────────────

GENERATE_SQL_INTENT_TOOL = {
    'name': 'generate_sql_intent',
    'description': 'Describe a dashboard widget query as structured intent. '
                   'The system builds the SQL automatically with correct filtering.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'mode': {
                'type': 'string',
                'enum': ['simple', 'union_all', 'cte', 'raw_override'],
                'description': (
                    'simple: single SELECT (KPI, bar, line, donut, table, scatter, etc.). '
                    'union_all: multiple SELECTs combined (bullet gauge, RAG, multi-ring). '
                    'cte: WITH clause for sparkline/complex queries. '
                    'raw_override: full SQL escape hatch (must use {where_clause}).'
                ),
            },
            'measures': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'expression': {
                            'type': 'string',
                            'description': 'SQL aggregate expression, e.g. SUM(hha_admits), '
                                           'COUNT(DISTINCT hha_ccn), '
                                           'ROUND(SUM(pt_visit+ot_visit+slp_visit)::numeric / NULLIF(SUM(hha_visits),0) * 100, 2)',
                        },
                        'alias': {
                            'type': 'string',
                            'description': 'Output column name, e.g. value, prior_value, admits, therapy_share',
                        },
                        'is_prior_year': {
                            'type': 'boolean',
                            'description': 'Set true for prior-year comparison. The system wraps the expression '
                                           'with CASE WHEN year = prior_year automatically.',
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Human-readable description of what this measure represents.',
                        },
                    },
                    'required': ['expression', 'alias'],
                },
                'description': 'List of SELECT expressions to compute.',
            },
            'dimensions': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'column': {
                            'type': 'string',
                            'description': 'Column name for GROUP BY, e.g. hha_state, priority_group',
                        },
                        'alias': {
                            'type': 'string',
                            'description': 'Optional output alias.',
                        },
                    },
                    'required': ['column'],
                },
                'description': 'Columns to GROUP BY (empty for KPIs, populated for bar/donut/table).',
            },
            'extra_conditions': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Hardcoded business logic from the user request '
                               '(e.g. "hha_rating >= \'4\'"). '
                               'NEVER include page filter params — those are automatic.',
            },
            'order_by': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'column': {'type': 'string'},
                        'direction': {'type': 'string', 'enum': ['ASC', 'DESC']},
                    },
                },
                'description': 'ORDER BY clauses. Reference measure aliases or dimension columns.',
            },
            'limit': {
                'type': 'integer',
                'description': 'LIMIT clause value (e.g. 10 for top-10 queries).',
            },
            'x_column': {
                'type': 'string',
                'description': 'Column name for X axis / labels / metric name.',
            },
            'y_columns': {
                'type': 'string',
                'description': 'Comma-separated column names for Y axis / values.',
            },
            'series_column': {
                'type': 'string',
                'description': 'Column name for multi-series grouping (optional).',
            },
            'explanation': {
                'type': 'string',
                'description': 'Brief explanation of what the query computes.',
            },
            'warnings': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Warnings about data quality, performance, or caveats.',
            },
            'union_blocks': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'measures': {'type': 'array'},
                        'label': {'type': 'string'},
                        'extra_conditions': {'type': 'array', 'items': {'type': 'string'}},
                    },
                },
                'description': 'For union_all mode: each block produces one SELECT.',
            },
            'cte_sql': {
                'type': 'string',
                'description': 'For cte mode: full WITH ... AS ... SQL. Use {where_clause} placeholder.',
            },
            'raw_sql': {
                'type': 'string',
                'description': 'For raw_override mode: complete SQL. Must use {where_clause} or [[...]].',
            },
        },
        'required': ['mode', 'measures', 'x_column', 'y_columns', 'explanation'],
    },
}


# ── Chart type --> expected column format ────────────────────────────────────
# Mirrors CustomSqlEditor.jsx SQL_COLUMN_HELP — used to tell Claude
# what column shape the chart expects.

SQL_COLUMN_REQUIREMENTS = {
    'bar':                  'category, value1 [, value2, ...]',
    'line':                 'x_value, y_value1 [, y_value2, ...]',
    'line_waterfall':       'step_name, delta_value',
    'line_combo':           'x_value, bar_col, line_col [, ...]',
    'line_benchmark':       'x_value, actual, target',
    'pie':                  'label, value',
    'donut':                'label, value',
    'donut_nested':         'parent, child, value',
    'donut_multi_ring':     'ring_group, label, value',
    'gauge':                'value',
    'gauge_half_arc':       'value',
    'gauge_three_quarter':  'value',
    'gauge_bullet':         'metric_name, actual_value, benchmark_value [, benchmark_label]',
    'gauge_traffic_light_rag': 'value [, red_threshold, green_threshold, badge_text]',
    'gauge_traffic_light_rag_scorecard': 'metric_name, value, rag_status [, status_text]',
    'gauge_percentile_rank': 'percentile [, subtitle, actual_value, actual_label]',
    'gauge_multi_ring':     'metric_name, metric_value [, metric_max]',
    'radar':                'indicator, score1 [, score2, ...]',
    'scatter':              'x_value, y_value',
    'heatmap':              'x_category, y_category, intensity',
    'kpi':                  'value [, prior_value]',
    'kpi_sparkline':        'value [, prior_value], sparkline_data (CSV string via STRING_AGG of the metric over time periods)',
    'kpi_progress':         'value, target [, benchmark_label]',
    'kpi_mini_gauge':       'value, target [, benchmark_label, status_text]',
    'kpi_comparison':       'value, prior_value [, current_label, prior_label]',
    'kpi_rag_status':       'value',
    'status_kpi':           'value, status_text',
    'table':                'col1, col2, col3, ...',
}


def _get_column_requirement_key(chart_type, gauge_style=None, line_style=None,
                                 donut_style=None, rag_layout=None, kpi_style=None):
    """Resolve the column requirement key from chart type + variant."""
    if chart_type == 'gauge' and gauge_style:
        if gauge_style == 'traffic_light_rag' and rag_layout == 'scorecard':
            return 'gauge_traffic_light_rag_scorecard'
        key = f'gauge_{gauge_style}'
        if key in SQL_COLUMN_REQUIREMENTS:
            return key
    if chart_type == 'donut' and donut_style in ('nested', 'multi_ring'):
        return f'donut_{donut_style}'
    if chart_type == 'line' and line_style in ('waterfall', 'combo', 'benchmark'):
        return f'line_{line_style}'
    if chart_type == 'kpi' and kpi_style and kpi_style != 'stat_card':
        key = f'kpi_{kpi_style}'
        if key in SQL_COLUMN_REQUIREMENTS:
            return key
    return chart_type


# ── Main service class ─────────────────────────────────────────────────────

class AiSqlGenerator:
    """Generates SQL from natural language using Claude on Azure AI Foundry.

    All context (schema, filters, relations) is assembled dynamically
    from the Odoo database at request time. Nothing is hardcoded.
    """

    def __init__(self, env):
        self.env = env
        ICP = env['ir.config_parameter'].sudo()
        self._api_key = ICP.get_param('dashboard_builder.ai_api_key', '')
        self._endpoint = ICP.get_param('dashboard_builder.ai_endpoint', '')
        self._model = ICP.get_param('dashboard_builder.ai_model', 'claude-sonnet-4-6')

        if not self._api_key or not self._endpoint:
            _logger.warning('AI SQL Generator: API key or endpoint not configured. '
                            'Set dashboard_builder.ai_api_key and dashboard_builder.ai_endpoint '
                            'in System Parameters.')

    def _get_client(self):
        """Lazy-initialize the Anthropic client."""
        from anthropic import AnthropicFoundry
        return AnthropicFoundry(
            api_key=self._api_key,
            base_url=self._endpoint,
        )

    # ── Context assembly (all dynamic) ─────────────────────────────────

    def assemble_context(self, source_id, page_id, chart_type,
                         gauge_style=None, line_style=None,
                         donut_style=None, rag_layout=None, kpi_style=None,
                         sparkline_metric=None, value_display=None):
        """Assemble schema context from the live system.

        Reads:
          - Source columns from dashboard.schema.source
          - Source relations from dashboard.schema.relation
          - Page filters from dashboard.page.filter
          - Chart column requirements from SQL_COLUMN_REQUIREMENTS

        Returns a dict ready to be serialized into the Claude prompt.
        """
        context = {
            'chart_type': chart_type,
            'gauge_style': gauge_style,
            'kpi_style': kpi_style,
            'sparkline_metric': sparkline_metric,
            'value_display': value_display,
        }

        # ── Primary table + columns ────────────────────────────────
        if source_id:
            Source = self.env['dashboard.schema.source'].sudo()
            source = Source.browse(int(source_id))
            if source.exists():
                context['primary_table'] = {
                    'table_name': source.table_name,
                    'display_name': source.name,
                    'columns': [self._build_column_context(c) for c in source.column_ids],
                }

                # ── Related tables ─────────────────────────────────
                if source.relation_ids:
                    related = []
                    for rel in source.relation_ids:
                        target = rel.target_source_id
                        related.append({
                            'table_name': target.table_name,
                            'display_name': target.name,
                            'join_type': rel.join_type,
                            'join_from_column': rel.source_column,
                            'join_to_column': rel.target_column,
                            'columns': [self._build_column_context(c) for c in target.column_ids],
                        })
                    context['related_tables'] = related

        # ── Page filters ───────────────────────────────────────────
        if page_id:
            PageFilter = self.env['dashboard.page.filter'].sudo()
            filters = PageFilter.search([
                ('page_id', '=', int(page_id)),
                ('is_active', '=', True),
            ])
            context['page_filters'] = [{
                'param': f.param_name or f.field_name or '',
                'label': f.display_template or f.param_name or '',
                'multiselect': f.is_multiselect,
                'is_visible': f.is_visible,
                # Auto-generated helper params for multiselect filters
                'helpers': [
                    f'_{f.param_name}_single',
                    f'_{f.param_name}_prior',
                ] if f.is_multiselect and f.param_name else [],
            } for f in filters if (f.param_name or f.field_name)]

        # ── Chart column requirements ──────────────────────────────
        req_key = _get_column_requirement_key(
            chart_type, gauge_style, line_style, donut_style, rag_layout, kpi_style)
        context['expected_columns'] = SQL_COLUMN_REQUIREMENTS.get(req_key, '')

        return context

    @staticmethod
    def _build_column_context(col):
        """Build rich column context dict with Layer 2+3 metadata."""
        ctx = {
            'name': col.column_name,
            'display_name': col.display_name,
            'type': col.data_type,
            'role': col.column_role or ('measure' if col.is_measure else 'dimension'),
        }
        if col.never_avg:
            ctx['never_avg'] = True
        if col.paired_column_id:
            ctx['paired_with'] = col.paired_column_id.column_name
        if col.description:
            ctx['description'] = col.description
        if col.domain_notes:
            ctx['domain_notes'] = col.domain_notes
        return ctx

    # ── Prompt building ────────────────────────────────────────────────

    def _build_user_message(self, context, user_prompt):
        """Build the user message with schema context + request."""
        parts = []

        parts.append(f"CHART TYPE: {context.get('chart_type', 'bar')}")
        if context.get('gauge_style'):
            parts.append(f"GAUGE VARIANT: {context['gauge_style']}")
        if context.get('kpi_style'):
            parts.append(f"KPI VARIANT: {context['kpi_style']}")
            if context['kpi_style'] == 'sparkline':
                metric_note = ''
                if context.get('sparkline_metric'):
                    metric_note = (
                        f" The user selected '{context['sparkline_metric']}' as the "
                        f"sparkline metric column. Use this column for the trend."
                    )
                parts.append(
                    "SPARKLINE NOTE: Include a 'sparkline_data' column using "
                    "STRING_AGG(metric_value::text, ',' ORDER BY year) "
                    "to provide trend data as a CSV string. "
                    "CRITICAL: The CTE that computes yearly trend data for the sparkline "
                    "must NOT filter by %(year)s — it needs ALL years to show the full "
                    "trajectory. Only the current_year and prior_year CTEs should filter "
                    "by year. For pre-computed rate columns (ending in _pct, _rate), "
                    "use SUM(numerator)/NULLIF(SUM(denominator),0) for aggregation, "
                    "not AVG(rate)." + metric_note
                )
            if context['kpi_style'] in ('progress', 'mini_gauge'):
                display_note = ''
                if context.get('value_display') == 'numeric':
                    display_note = (
                        " VALUE DISPLAY is set to NUMERIC — the value will be "
                        "shown as the actual number (e.g. 2.36) not as a percentage. "
                        "Return raw metric values, not pre-multiplied by 100."
                    )
                parts.append(
                    "PROGRESS/GAUGE NOTE: Include a 'target' column representing "
                    "the benchmark value. For state benchmarks, compute the rate "
                    "across ALL providers in the selected state (not just the "
                    "selected HHA). For peer benchmarks, compute across similar "
                    "providers. The SQL should return: value (selected HHA's "
                    "metric) and target (benchmark to compare against). "
                    "ALSO include a 'benchmark_label' column with a human-readable "
                    "label for the benchmark (e.g., 'State Avg (Illinois)', "
                    "'National Avg', 'Peer Group'). This label is shown in the "
                    "annotation text (e.g., '-0.15 vs State Avg (Illinois)')." + display_note
                )
        parts.append(f"EXPECTED COLUMN FORMAT: {context.get('expected_columns', '')}")
        parts.append('')

        # Primary table
        pt = context.get('primary_table', {})
        if pt:
            parts.append(f"PRIMARY TABLE: {pt['table_name']}")
            parts.append('COLUMNS:')
            for c in pt.get('columns', []):
                parts.append(self._format_column_line(c))
            parts.append('')

        # Related tables
        for rt in context.get('related_tables', []):
            parts.append(f"RELATED TABLE: {rt['table_name']} "
                         f"(join: {rt['join_type'].upper()} ON {rt['join_from_column']} = {rt['join_to_column']})")
            parts.append('COLUMNS:')
            for c in rt.get('columns', []):
                parts.append(self._format_column_line(c))
            parts.append('')

        # Page filters
        pf = context.get('page_filters', [])
        if pf:
            parts.append('AVAILABLE FILTER PARAMETERS:')
            for f in pf:
                ms = ' [MULTISELECT — use IN]' if f['multiselect'] else ''
                vis = '' if f['is_visible'] else ' [HIDDEN — SQL context only]'
                param = f['param']
                parts.append(f"  - %({param})s  label=\"{f['label']}\"{ms}{vis}")
                # Show helper params for multiselect filters
                for h in f.get('helpers', []):
                    parts.append(f"      helper: %({h})s")
            parts.append('')

        parts.append(f"USER REQUEST: {user_prompt}")

        return '\n'.join(parts)

    @staticmethod
    def _format_column_line(c):
        """Format one column line for the prompt with Layer 2+3 metadata."""
        role = c.get('role', 'dimension')
        line = f"  - {c['name']} ({c['type']}, {role})"

        # Layer 2: warnings and paired columns
        if c.get('never_avg'):
            line += ' ⚠️ NEVER AVG'
        if c.get('paired_with'):
            line += f' → paired with {c["paired_with"]}'

        # Layer 3: business description
        if c.get('description'):
            line += f'\n      "{c["description"]}"'
        if c.get('domain_notes'):
            line += f'\n      NOTE: {c["domain_notes"]}'

        return line

    # ── Generate SQL ───────────────────────────────────────────────────

    def generate_sql(self, context, user_prompt):
        """Generate SQL from natural language using Claude.

        Returns: {sql, x_column, y_columns, explanation, warnings}
        """
        if not self._api_key:
            raise ValueError(
                'AI SQL Generator is not configured. '
                'Set dashboard_builder.ai_api_key and dashboard_builder.ai_endpoint '
                'in Settings → Technical → System Parameters.')

        client = self._get_client()
        user_message = self._build_user_message(context, user_prompt)

        _logger.info('AI SQL Generate: chart=%s, prompt=%s',
                     context.get('chart_type'), user_prompt[:100])

        message = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[GENERATE_SQL_TOOL],
            tool_choice={'type': 'tool', 'name': 'generate_sql'},
            messages=[
                {'role': 'user', 'content': user_message},
            ],
        )

        # Extract structured tool_use response
        for block in message.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                if block.name == 'generate_sql':
                    result = block.input
                    _logger.info('AI SQL Generate: success, sql=%s',
                                 result.get('sql', '')[:200])
                    return result

        raise ValueError('AI did not return structured SQL output. '
                         'Please try rephrasing your request.')

    # ── Fix SQL (self-healing) ─────────────────────────────────────────

    def fix_sql(self, context, original_sql, error_message):
        """Send a failed SQL + error back to Claude for correction.

        Returns: {sql, x_column, y_columns, explanation, warnings}
        """
        client = self._get_client()
        user_message = self._build_user_message(
            context,
            f"Fix this SQL query that failed with an error.\n\n"
            f"ORIGINAL SQL:\n{original_sql}\n\n"
            f"ERROR:\n{error_message}\n\n"
            f"Generate a corrected version that fixes the error."
        )

        _logger.info('AI SQL Fix: error=%s', error_message[:200])

        message = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[GENERATE_SQL_TOOL],
            tool_choice={'type': 'tool', 'name': 'generate_sql'},
            messages=[
                {'role': 'user', 'content': user_message},
            ],
        )

        for block in message.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                if block.name == 'generate_sql':
                    result = block.input
                    _logger.info('AI SQL Fix: success')
                    return result

        raise ValueError('AI could not fix the SQL. Try editing it manually.')

    # ── Refine SQL (iteration) ─────────────────────────────────────────

    def refine_sql(self, context, previous_sql, refinement_prompt):
        """Modify existing SQL based on a refinement request.

        Returns: {sql, x_column, y_columns, explanation, warnings}
        """
        client = self._get_client()
        user_message = self._build_user_message(
            context,
            f"Modify this existing SQL query based on the refinement request.\n\n"
            f"CURRENT SQL:\n{previous_sql}\n\n"
            f"REFINEMENT REQUEST: {refinement_prompt}\n\n"
            f"Generate the updated SQL that incorporates the requested changes."
        )

        _logger.info('AI SQL Refine: request=%s', refinement_prompt[:100])

        message = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[GENERATE_SQL_TOOL],
            tool_choice={'type': 'tool', 'name': 'generate_sql'},
            messages=[
                {'role': 'user', 'content': user_message},
            ],
        )

        for block in message.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                if block.name == 'generate_sql':
                    result = block.input
                    _logger.info('AI SQL Refine: success')
                    return result

        raise ValueError('AI could not refine the SQL. Try editing it manually.')

    # ── Intent-based generation (new pipeline) ─────────────────────────

    def generate_intent(self, context, user_prompt):
        """Generate structured intent from natural language using Claude.

        Instead of raw SQL, returns a structured dict describing WHAT to
        compute (measures, dimensions, conditions). The SqlAssembler then
        builds the correct SQL with proper WHERE clauses.

        Returns: dict matching GENERATE_SQL_INTENT_TOOL schema.
        """
        if not self._api_key:
            raise ValueError(
                'AI SQL Generator is not configured. '
                'Set dashboard_builder.ai_api_key and dashboard_builder.ai_endpoint '
                'in Settings -> Technical -> System Parameters.')

        client = self._get_client()
        user_message = self._build_intent_user_message(context, user_prompt)

        _logger.info('AI Intent Generate: chart=%s, prompt=%s',
                     context.get('chart_type'), user_prompt[:100])

        message = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=INTENT_SYSTEM_PROMPT,
            tools=[GENERATE_SQL_INTENT_TOOL],
            tool_choice={'type': 'tool', 'name': 'generate_sql_intent'},
            messages=[
                {'role': 'user', 'content': user_message},
            ],
        )

        for block in message.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                if block.name == 'generate_sql_intent':
                    result = block.input
                    _logger.info('AI Intent Generate: success, mode=%s, measures=%d',
                                 result.get('mode', '?'),
                                 len(result.get('measures', [])))
                    return result

        raise ValueError('AI did not return structured intent output. '
                         'Please try rephrasing your request.')

    def refine_intent(self, context, previous_intent, refinement_prompt):
        """Modify existing intent based on a refinement request.

        Returns: dict matching GENERATE_SQL_INTENT_TOOL schema.
        """
        client = self._get_client()
        user_message = self._build_intent_user_message(
            context,
            'Modify this existing query intent based on the refinement request.\n\n'
            'CURRENT INTENT:\n%s\n\n'
            'REFINEMENT REQUEST: %s\n\n'
            'Generate the updated intent that incorporates the requested changes.'
            % (json.dumps(previous_intent, indent=2), refinement_prompt)
        )

        _logger.info('AI Intent Refine: request=%s', refinement_prompt[:100])

        message = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=INTENT_SYSTEM_PROMPT,
            tools=[GENERATE_SQL_INTENT_TOOL],
            tool_choice={'type': 'tool', 'name': 'generate_sql_intent'},
            messages=[
                {'role': 'user', 'content': user_message},
            ],
        )

        for block in message.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                if block.name == 'generate_sql_intent':
                    result = block.input
                    _logger.info('AI Intent Refine: success')
                    return result

        raise ValueError('AI could not refine the intent. Try editing it manually.')

    def fix_intent(self, context, previous_intent, error_message):
        """Fix an intent that produced an error.

        Returns: dict matching GENERATE_SQL_INTENT_TOOL schema.
        """
        client = self._get_client()
        user_message = self._build_intent_user_message(
            context,
            'Fix this query intent that produced an error.\n\n'
            'CURRENT INTENT:\n%s\n\n'
            'ERROR:\n%s\n\n'
            'Generate a corrected intent that fixes the error.'
            % (json.dumps(previous_intent, indent=2), error_message)
        )

        _logger.info('AI Intent Fix: error=%s', error_message[:200])

        message = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=INTENT_SYSTEM_PROMPT,
            tools=[GENERATE_SQL_INTENT_TOOL],
            tool_choice={'type': 'tool', 'name': 'generate_sql_intent'},
            messages=[
                {'role': 'user', 'content': user_message},
            ],
        )

        for block in message.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                if block.name == 'generate_sql_intent':
                    result = block.input
                    _logger.info('AI Intent Fix: success')
                    return result

        raise ValueError('AI could not fix the intent. Try editing it manually.')

    def _build_intent_user_message(self, context, user_prompt):
        """Build user message for intent mode — same schema context, no filter clause instructions."""
        parts = []

        parts.append('CHART TYPE: %s' % context.get('chart_type', 'bar'))
        if context.get('gauge_style'):
            parts.append('GAUGE VARIANT: %s' % context['gauge_style'])
        if context.get('kpi_style'):
            parts.append('KPI VARIANT: %s' % context['kpi_style'])
            if context['kpi_style'] == 'sparkline':
                metric_note = ''
                if context.get('sparkline_metric'):
                    metric_note = ' Use column "%s" for the sparkline trend.' % context['sparkline_metric']
                parts.append(
                    'SPARKLINE NOTE: Use mode="cte" with a CTE that computes '
                    'a trend CSV via STRING_AGG(metric::text, \',\' ORDER BY year). '
                    'The trend CTE needs ALL years (not filtered by year). '
                    'For pre-computed rates, use SUM(num)/NULLIF(SUM(den),0).' + metric_note
                )
            if context['kpi_style'] in ('progress', 'mini_gauge'):
                display_note = ''
                if context.get('value_display') == 'numeric':
                    display_note = ' Return raw metric values, not pre-multiplied by 100.'
                parts.append(
                    'PROGRESS/GAUGE NOTE: Include a measure with alias "target" '
                    'representing the benchmark. Also include a measure with alias '
                    '"benchmark_label" as a string label for the benchmark.' + display_note
                )
        parts.append('EXPECTED COLUMN FORMAT: %s' % context.get('expected_columns', ''))
        parts.append('')

        # Primary table
        pt = context.get('primary_table', {})
        if pt:
            parts.append('PRIMARY TABLE: %s' % pt['table_name'])
            parts.append('COLUMNS:')
            for c in pt.get('columns', []):
                parts.append(self._format_column_line(c))
            parts.append('')

        # Related tables
        for rt in context.get('related_tables', []):
            parts.append('RELATED TABLE: %s (join: %s ON %s = %s)' % (
                rt['table_name'], rt['join_type'].upper(),
                rt['join_from_column'], rt['join_to_column'],
            ))
            parts.append('COLUMNS:')
            for c in rt.get('columns', []):
                parts.append(self._format_column_line(c))
            parts.append('')

        # Minimal filter context — just tell the AI what's available
        # (not HOW to use them — the assembler handles that)
        pf = context.get('page_filters', [])
        if pf:
            parts.append('AVAILABLE PAGE FILTERS (handled automatically by the system):')
            for f in pf:
                vis = '' if f['is_visible'] else ' [HIDDEN]'
                parts.append('  - %s%s' % (f['param'], vis))
            parts.append('')

        parts.append('USER REQUEST: %s' % user_prompt)

        return '\n'.join(parts)

    # ── Suggest queries (schema-aware) ─────────────────────────────────

    def suggest_queries(self, context):
        """Generate 10 schema-aware query suggestions for the chart type + table.

        Returns: {suggestions: ["Show total_admits as bars by year...", ...]}
        """
        if not self._api_key:
            return {'suggestions': []}

        client = self._get_client()
        user_message = self._build_user_message(
            context,
            'Generate 10 useful query suggestions for this chart type and data table. '
            'Use actual column names from the schema. Be specific and practical. '
            'Each suggestion should describe a concrete visualization an analyst would want.'
        )

        _logger.info('AI Suggest: chart=%s, source=%s',
                     context.get('chart_type'),
                     context.get('primary_table', {}).get('table_name', ''))

        try:
            message = client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=[SUGGEST_TOOL],
                tool_choice={'type': 'tool', 'name': 'suggest_queries'},
                messages=[
                    {'role': 'user', 'content': user_message},
                ],
            )

            for block in message.content:
                if hasattr(block, 'type') and block.type == 'tool_use':
                    if block.name == 'suggest_queries':
                        result = block.input
                        _logger.info('AI Suggest: %d suggestions generated',
                                     len(result.get('suggestions', [])))
                        return result

        except Exception as e:
            _logger.warning('AI Suggest failed: %s', e)

        return {'suggestions': []}
