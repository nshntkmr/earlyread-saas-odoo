"""MCP tools — 1:1 mapping onto the Odoo AI gateway.

The desktop client's own model (Claude / GPT) is the reasoning engine: it
reads the schema via list_sources/get_schema, authors SQL, runs it through
query_data, and summarizes the rows itself. The Odoo gateway enforces
everything that matters (SELECT-only validation, source visibility,
tenant scoping via SQL_tenant_id, row caps, rate limits, audit logging) —
these tools are deliberately thin.
"""

from .odoo_client import GatewayError, gateway


_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False,
              "openWorldHint": False}


def register_tools(mcp):

    @mcp.tool(annotations=_READ_ONLY)
    async def list_sources() -> dict:
        """List the data tables (schema sources) available to you in this
        Posterra app, with names and descriptions. Call this first to see
        what data exists, then call get_schema(source_id) before writing
        any SQL against a table."""
        return await gateway("GET", "/api/v1/ai/scope",
                             params={"detail": "summary"})

    @mcp.tool(annotations=_READ_ONLY)
    async def get_schema(source_id: int) -> dict:
        """Get the full schema for one source: columns with types, roles,
        business descriptions and domain notes, join relations to other
        available sources, and SQL dialect notes for the source's engine.

        IMPORTANT rules to respect when writing SQL:
        - Columns marked never_avg are pre-computed rates — never AVG()
          them; compute SUM(numerator)/NULLIF(SUM(denominator),0) instead.
        - Follow the sql_dialect_notes exactly (ClickHouse has no
          date_trunc; Snowflake and Postgres differ on functions too).
        """
        return await gateway("GET", f"/api/v1/ai/schema/{int(source_id)}")

    @mcp.tool(annotations=_READ_ONLY)
    async def query_data(source_id: int, sql: str, limit: int = 200) -> dict:
        """Run a read-only SQL query against one source and get columns +
        rows back. SELECT/WITH only — the server validates the SQL, allows
        only tables advertised by list_sources/get_schema (same connection),
        enforces tenant scoping and row caps (max 500 rows), and logs every
        query. If the query fails, read the error message, fix the SQL, and
        try again. Always call get_schema(source_id) first."""
        try:
            return await gateway(
                "POST", "/api/v1/ai/query",
                json_body={"source_id": int(source_id), "sql": sql,
                           "limit": int(limit)})
        except GatewayError as exc:
            # Return the server's message as the tool result so the model
            # can self-correct instead of treating it as a hard failure.
            return {"error": str(exc)}

    return mcp
