"""Unit tests: header forwarding, error passthrough, payload shaping.

The Odoo gateway is mocked with respx — no Odoo needed.
"""

import httpx
import pytest
import respx

from app import odoo_client
from app.odoo_client import GatewayError, gateway

BASE = "http://odoo.test"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(odoo_client.settings, "odoo_base_url", BASE)
    monkeypatch.setenv("POSTERRA_API_KEY", "test-key")
    monkeypatch.setenv("POSTERRA_APP_KEY", "ai-test-app")


@pytest.mark.asyncio
@respx.mock
async def test_headers_forwarded():
    route = respx.get(f"{BASE}/api/v1/ai/scope").mock(
        return_value=httpx.Response(200, json={"sources": []}))
    data = await gateway("GET", "/api/v1/ai/scope")
    assert data == {"sources": []}
    sent = route.calls.last.request
    assert sent.headers["x-api-key"] == "test-key"
    assert sent.headers["x-app-key"] == "ai-test-app"


@pytest.mark.asyncio
@respx.mock
async def test_gateway_error_passthrough():
    respx.post(f"{BASE}/api/v1/ai/query").mock(
        return_value=httpx.Response(
            400, json={"error": "SQL rejected: DML not allowed"}))
    with pytest.raises(GatewayError, match="DML not allowed"):
        await gateway("POST", "/api/v1/ai/query",
                      json_body={"source_id": 1, "sql": "DELETE FROM x"})


@pytest.mark.asyncio
async def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("POSTERRA_API_KEY")
    with pytest.raises(GatewayError, match="Missing credentials"):
        await gateway("GET", "/api/v1/ai/scope")


@pytest.mark.asyncio
@respx.mock
async def test_query_data_tool_returns_error_dict():
    """query_data must surface gateway errors as a result dict (so the
    desktop model self-corrects), not as an exception."""
    from fastmcp import FastMCP
    from app.tools import register_tools

    respx.post(f"{BASE}/api/v1/ai/query").mock(
        return_value=httpx.Response(400, json={"error": "Query failed: x"}))
    mcp = register_tools(FastMCP("test"))
    from fastmcp import Client
    async with Client(mcp) as client:
        res = await client.call_tool(
            "query_data", {"source_id": 1, "sql": "SELECT bad"})
        payload = res.data if hasattr(res, "data") else res
        assert "Query failed" in str(payload)
