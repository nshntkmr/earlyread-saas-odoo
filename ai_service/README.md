# Posterra AI Assist — MCP Service

Exposes the Odoo AI gateway (`/api/v1/ai/*`) as an [MCP](https://modelcontextprotocol.io)
server so internal users can chat with Posterra data from **Claude Desktop**
(now) and **ChatGPT web** (once the OAuth 2.1 front-end lands; ChatGPT
Desktop when officially supported). The desktop client's own model does the reasoning
and summarizing; this service is a thin, stateless, credential-less proxy —
all enforcement (SELECT-only validation, per-app source visibility, tenant
scoping, row caps, rate limits, audit logging) happens in Odoo.

## Prerequisites

1. The target `saas.app` has **AI Assist Enabled** checked (Applications
   admin form).
2. The schema sources you want queryable are **explicitly assigned** to the
   app for AI (the app form's *AI Assist Schema Sources*, or the source
   form's *AI Assist Apps* — Non-PHI sources only; general dashboard
   availability does NOT imply chatbot availability).
3. You are in the **AI Assist Desktop User** group, and an admin issued you
   an API key: Settings → Users → your user → **Generate AI Assist Key**
   (scope `posterra_ai`; shown once, stored hashed).

## Tools exposed

| Tool | What it does |
|---|---|
| `list_sources()` | Tables assigned to the chatbot for the configured app |
| `get_schema(source_id)` | Columns, roles, descriptions, join relations, SQL dialect notes |
| `query_data(source_id, sql, limit)` | Validated read-only SQL → columns + rows (≤500) |

All tools are read-only (`readOnlyHint`). The gateway additionally enforces
a table allowlist (only tables advertised by `list_sources`, same
connection), blocks system tables and table functions, hard-caps rows, and
audits every query.

**Who may connect:** users must hold the *AI Assist Desktop User* (or
Posterra Admin) group. v1 queries are tenant-scoped to the app but NOT
narrowed to a user's provider scope — issue keys to internal analysts only.

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

Raw-JSON config is fine for the internal pilot; for wider rollout, package
this as a Claude Desktop extension (MCPB) with the API-key field marked
sensitive so Claude stores it in the OS credential store instead of a
plaintext config file.

## ChatGPT (web) / remote clients (streamable HTTP)

**Availability caveat:** OpenAI's custom-MCP support is currently documented
for **ChatGPT web** (developer mode / full MCP connectors), not ChatGPT
Desktop — treat the milestone as "ChatGPT web now; Desktop when officially
supported." OpenAI's documented contract for private MCP servers expects
**OAuth 2.1 bearer tokens** validated by the MCP server; the header-based
`X-API-Key`/`X-App-Key` scheme below works for clients that support custom
headers, and an OAuth 2.1 front-end on this service is the planned path for
clients that don't (tracked as an open item — do not build ChatGPT rollout
plans on custom headers).

Run the service (Docker image or `posterra-mcp --http`) behind the ingress,
e.g. `https://ai.<domain>/mcp`, and configure a connector pointing at that
URL with headers:

```
X-API-Key: <key>
X-App-Key: ulh-humana-ma
```

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
