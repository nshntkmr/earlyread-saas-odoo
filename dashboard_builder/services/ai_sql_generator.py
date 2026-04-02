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
3. For multiselect filters: ALWAYS use IN %(param)s, NEVER = %(param)s.
   A multiselect filter value is a tuple like ('FFS', 'MA') — the = operator cannot bind tuples.
4. Use [[AND col IN %(param)s]] for optional filter clauses.
   The [[...]] wrapper means: include this clause only when the param has a value.
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


# ── Chart type → expected column format ────────────────────────────────────
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
    'status_kpi':           'value, status_text',
    'table':                'col1, col2, col3, ...',
}


def _get_column_requirement_key(chart_type, gauge_style=None, line_style=None,
                                 donut_style=None, rag_layout=None):
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
                         donut_style=None, rag_layout=None):
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
        }

        # ── Primary table + columns ────────────────────────────────
        if source_id:
            Source = self.env['dashboard.schema.source'].sudo()
            source = Source.browse(int(source_id))
            if source.exists():
                context['primary_table'] = {
                    'table_name': source.table_name,
                    'display_name': source.name,
                    'columns': [{
                        'name': c.column_name,
                        'display_name': c.display_name,
                        'type': c.data_type,
                        'role': 'measure' if c.is_measure else 'dimension',
                    } for c in source.column_ids],
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
                            'columns': [{
                                'name': c.column_name,
                                'display_name': c.display_name,
                                'type': c.data_type,
                                'role': 'measure' if c.is_measure else 'dimension',
                            } for c in target.column_ids],
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
            } for f in filters if (f.param_name or f.field_name)]

        # ── Chart column requirements ──────────────────────────────
        req_key = _get_column_requirement_key(
            chart_type, gauge_style, line_style, donut_style, rag_layout)
        context['expected_columns'] = SQL_COLUMN_REQUIREMENTS.get(req_key, '')

        return context

    # ── Prompt building ────────────────────────────────────────────────

    def _build_user_message(self, context, user_prompt):
        """Build the user message with schema context + request."""
        parts = []

        parts.append(f"CHART TYPE: {context.get('chart_type', 'bar')}")
        if context.get('gauge_style'):
            parts.append(f"GAUGE VARIANT: {context['gauge_style']}")
        parts.append(f"EXPECTED COLUMN FORMAT: {context.get('expected_columns', '')}")
        parts.append('')

        # Primary table
        pt = context.get('primary_table', {})
        if pt:
            parts.append(f"PRIMARY TABLE: {pt['table_name']}")
            parts.append('COLUMNS:')
            for c in pt.get('columns', []):
                parts.append(f"  - {c['name']} ({c['type']}, {c['role']})")
            parts.append('')

        # Related tables
        for rt in context.get('related_tables', []):
            parts.append(f"RELATED TABLE: {rt['table_name']} "
                         f"(join: {rt['join_type'].upper()} ON {rt['join_from_column']} = {rt['join_to_column']})")
            parts.append('COLUMNS:')
            for c in rt.get('columns', []):
                parts.append(f"  - {c['name']} ({c['type']}, {c['role']})")
            parts.append('')

        # Page filters
        pf = context.get('page_filters', [])
        if pf:
            parts.append('AVAILABLE FILTER PARAMETERS:')
            for f in pf:
                ms = ' [MULTISELECT — use IN]' if f['multiselect'] else ''
                vis = '' if f['is_visible'] else ' [HIDDEN — SQL context only]'
                parts.append(f"  - %({{param}})s  label=\"{f['label']}\"{ms}{vis}"
                             .replace('{param}', f['param']))
            parts.append('')

        parts.append(f"USER REQUEST: {user_prompt}")

        return '\n'.join(parts)

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
