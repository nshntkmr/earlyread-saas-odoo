# Posterra AI Assist — MCP Service

Exposes the Odoo AI gateway (`/api/v1/ai/*`) as an [MCP](https://modelcontextprotocol.io)
server so internal users can chat with Posterra data from **Claude Desktop**
or **ChatGPT Desktop**. The desktop client's own model does the reasoning
and summarizing; this service is a thin, stateless, credential-less proxy —
all enforcement (SELECT-only validation, per-app source visibility, tenant
scoping, row caps, rate limits, audit logging) happens in Odoo.

## Prerequisites

1. The target `saas.app` has **AI Assist Enabled** checked (Applications
   admin form).
2. The schema sources you want queryable have **AI Assist Opt-in** checked
   (Schema Source form — only offered for Non-PHI sources).
3. An admin issued you an API key: Settings → Users → your user →
   **Generate AI Assist Key** (scope `posterra_ai`; shown once).

## Tools exposed

| Tool | What it does |
|---|---|
| `list_sources()` | Tables available in the configured app |
| `get_schema(source_id)` | Columns, roles, descriptions, join relations, SQL dialect notes |
| `query_data(source_id, sql, limit)` | Validated read-only SQL → columns + rows (≤500) |
| `ask_data(source_id, question)` | Server-side NL→SQL fallback (501 if the server has no LLM configured) |

## Claude Desktop (stdio, local)

Install the package once (`pip install -e .` in this directory, or use
`uv`), then add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "posterra-humana": {
      "command": "posterra-mcp",
      "env": {
        "ODOO_BASE_URL": "https://<your-odoo-host>",
        "POSTERRA_API_KEY": "<key from the admin wizard>",
        "POSTERRA_APP_KEY": "ulh-humana-ma"
      }
    }
  }
}
```

One connector = one (user, app) context. For a second app, add a second
entry with a different `POSTERRA_APP_KEY`.

## ChatGPT Desktop / remote clients (streamable HTTP)

Run the service (Docker image or `posterra-mcp --http`) behind the ingress,
e.g. `https://ai.<domain>/mcp`, and configure a custom connector pointing at
that URL with headers:

```
X-API-Key: <key>
X-App-Key: ulh-humana-ma
```

> Note: verify your ChatGPT Desktop version supports custom headers on MCP
> connectors. If it doesn't, use the stdio mode via a local launcher, or
> wait for the per-user URL-token frontend (tracked as an open item).

## Local dev

```bash
pip install -e ".[dev]"
cp .env.example .env               # point ODOO_BASE_URL at localhost:8069
posterra-mcp                       # stdio
posterra-mcp --http --port 8808    # HTTP at http://localhost:8808/mcp
npx @modelcontextprotocol/inspector posterra-mcp   # interactive testing
pytest                             # unit tests (mocked gateway)
```

## Failure behavior (by design)

- Key revoked / user archived / app disabled / source opted out → the next
  tool call returns the gateway's 401/403 message; nothing is cached here.
- Bad SQL → the gateway's validator/driver message is returned as the tool
  result so the desktop model can correct and retry.
- Rate limit → 429 message with the reset time.
