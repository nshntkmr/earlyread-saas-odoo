"""Thin async client for the Odoo AI gateway.

Credential resolution per request:
  1. HTTP headers on the incoming MCP request (remote streamable-http
     deployments: the desktop client sends X-API-Key / X-App-Key).
  2. POSTERRA_API_KEY / POSTERRA_APP_KEY env vars (stdio deployments: the
     desktop client's ``mcpServers.env`` block).

One configured connector == one (user, app) tenant context. The service
holds no credentials of its own and keeps no state between requests, so
revocation/disablement on the Odoo side is effective on the next call.
"""

import os

import httpx

from .config import settings


class GatewayError(Exception):
    """Raised with the Odoo gateway's own error message so the desktop
    model can read it and self-correct (bad SQL → fix and retry)."""


def _credentials() -> tuple[str, str]:
    api_key, app_key = "", ""
    try:
        # Lazy import — only resolvable inside a FastMCP request context.
        from fastmcp.server.dependencies import get_http_headers
        headers = get_http_headers() or {}
        api_key = headers.get("x-api-key", "")
        app_key = headers.get("x-app-key", "")
    except Exception:
        pass
    api_key = api_key or os.environ.get("POSTERRA_API_KEY", "")
    app_key = app_key or os.environ.get("POSTERRA_APP_KEY", "")
    if not api_key or not app_key:
        raise GatewayError(
            "Missing credentials: set POSTERRA_API_KEY and POSTERRA_APP_KEY "
            "in the MCP connector config (stdio) or send X-API-Key / "
            "X-App-Key headers (remote).")
    return api_key, app_key


async def gateway(method: str, path: str, json_body: dict | None = None,
                  params: dict | None = None) -> dict:
    api_key, app_key = _credentials()
    url = settings.odoo_base_url.rstrip("/") + path
    headers = {"X-API-Key": api_key, "X-App-Key": app_key}
    async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds) as client:
        try:
            resp = await client.request(
                method, url, headers=headers, json=json_body, params=params)
        except httpx.HTTPError as exc:
            raise GatewayError(f"Odoo gateway unreachable: {exc}") from exc
    try:
        data = resp.json()
    except ValueError:
        raise GatewayError(
            f"Odoo gateway returned non-JSON (HTTP {resp.status_code})")
    if resp.status_code >= 400:
        raise GatewayError(
            data.get("error") or f"Gateway error (HTTP {resp.status_code})")
    return data
