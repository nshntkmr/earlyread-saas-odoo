"""Posterra AI Assist MCP server.

Transports:
  - stdio (default for local/desktop use): the desktop client launches the
    process; credentials come from the connector's env block.
  - streamable HTTP (`--http`): for the shared remote deployment behind the
    Azure ingress; credentials arrive as X-API-Key / X-App-Key headers on
    each request.

The server is stateless and credential-less — see odoo_client.py.
"""

import argparse
import logging

from fastmcp import FastMCP

from .config import settings
from .tools import register_tools

logging.basicConfig(level=settings.log_level)

mcp = FastMCP(
    "Posterra AI Assist",
    instructions=(
        "Query Posterra healthcare-analytics data for the configured app. "
        "Workflow: list_sources → get_schema(source_id) → author SELECT "
        "SQL following the dialect notes → query_data. Respect never_avg "
        "column warnings. All access is tenant-scoped and audited "
        "server-side."
    ),
)
register_tools(mcp)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request):
    from starlette.responses import PlainTextResponse
    return PlainTextResponse("ok")


def main():
    parser = argparse.ArgumentParser(prog="posterra-mcp")
    parser.add_argument("--http", action="store_true",
                        help="Serve streamable HTTP instead of stdio")
    parser.add_argument("--stdio", action="store_true",
                        help="Serve stdio (default)")
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="http", host="0.0.0.0", port=args.port,
                path="/mcp")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
