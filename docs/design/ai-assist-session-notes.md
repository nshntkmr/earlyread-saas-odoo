# AI Assist — Session Handoff Notes (2026-07-30)

Continuation notes for the AI-chatbot / graph-DB evaluation work. Read together
with `docs/design/ai-assist-architecture.md` (the main design doc, same branch).

**Branch:** `claude/festive-carson-6f2gel` (rebased onto `origin/main` @ 400db60).

---

## 1. What was decided (settled — do not re-litigate)

### Chatbot architecture ("AI Assist / Ask a Question")
- Evaluated two reference architectures (YouTube: LibreChat + MCP + ClickHouse
  Cloud + Claude Sonnet; and the ClickHouse-Cloud-native-MCP variant from the
  CH NYC meetup talk). **Both rejected as-is.**
- Final architecture = three planes (full spec in the design doc):
  1. **React `<AiAssistPanel/>`** embedded as a new section on the app page
     (no LibreChat — it can't be embedded in the portal).
  2. **Separate AI Agent Service** (FastAPI, own AKS deployment) — owns LLM
     calls, conversation store (TTL 24–48h), PHI vault, provider adapter,
     rate caps. Holds NO warehouse credentials. (No MCP server — pointless
     hop when we own both UI and loop.)
  3. **Odoo = guardrail plane** — the ONLY component touching
     ClickHouse/Postgres/Snowflake, via existing `query_executors`.
     Endpoints: `/ai/scope`, `/ai/execute` (intent), `/ai/execute_raw`
     (exotic-SQL escape hatch, same validators).
- **PHI rule: "LLM must never see PHI"** (browser MAY show rows the user is
  entitled to). Three gates: (1) PHI columns omitted from schema context;
  (2) SQL referencing PHI columns rejected; (3) summary payload =
  de-identified aggregates only, raw rows go browser-only.
- **Patient-lookup dilemma solved** via pseudonymize → plan → bind-at-SQL-param
  → de-identify → summarize → **re-hydrate** (server swaps vault tokens back
  into the LLM output). Per-app `ai_deid_level: standard|strict` dial —
  compliance owns the choice.
- **Provider switching per app** (Claude on Azure AI Foundry ↔ GPT on Azure
  OpenAI) via `ai.provider` records + a ProviderAdapter normalising the two
  tool-calling dialects. Both under Azure BAA. Needs a regression question-set
  to validate quality on switch.
- Chat inherits the page's current filter state; question can override.
- Multi-turn yes, retention only 24–48h; per-user daily cap + per-app token
  ledger.
- User answered all design questions (see design doc §2 + git history of this
  conversation): separate server ✓, LLM-only PHI rule ✓, exotic questions
  wanted ✓, per-app provider ✓, explicit app_ids mapping ✓.

### Graph DB (Neo4j) evaluation — researched, recommendation delivered
- Three research passes run (graph-vs-SQL, zero-ETL alternatives,
  GraphRAG/tenancy/HIPAA). Verdict:
  - **Bucket 1 (chatbot accuracy):** the "KG triples text-to-SQL accuracy"
    benchmark (data.world 16.7%→54.2%→72.5%) is evidence for a *semantic
    layer*, which Posterra already has (AI Column Intelligence). No graph DB
    needed.
  - **Bucket 2 (graph algorithms — FWA rings, cohort similarity):** use
    **ephemeral projections** (Neo4j Graph Analytics for Snowflake native
    app — no license, runs inside Snowflake governance) when a real need
    appears. No standing graph DB.
  - **Bucket 3 (interactive multi-hop cyclic traversal, e.g. referral
    leakage):** only this needs a graph engine. CH recursive CTEs genuinely
    can't traverse cycles (open CH RFC #107067). Candidate: PuppyGraph
    (zero-ETL over CH+Snowflake) — BUT **no independent evidence exists**
    (all benchmarks vendor-sourced; zero G2/Capterra reviews; seed-stage
    vendor), and its static-JDBC-user model conflicts with the per-query
    `SQL_tenant_id` row-policy contract (would return zero rows via
    `app_user`, or need policy-exempt user = leak risk). Recommendation:
    **no graph component now**; if a bucket-3 feature becomes real, run a
    1–2-week PuppyGraph PoC with pre-written pass/fail criteria (tenancy,
    p95 < 2s, schema-change survival) before considering a curated Neo4j
    subgraph (Aura Business Critical; BAA tier must be confirmed with Neo4j;
    nightly dbt rebuild, never CDC).
- If Neo4j ever happens: Enterprise-tier features are mandatory for
  multi-tenant PHI (DB-per-tenant, RBAC, hot backup — all Enterprise-only).

## 2. Key discovery: `origin/main` already implements much of Phase 1

Found late in the session — the deployed environment is ahead of where the
design doc assumed:

- `dashboard.schema.source.app_ids` (M2M → saas.app, "Available in Apps") —
  **exists** (`posterra_portal/models/dashboard_builder_ext.py`).
- `data_classification` on schema source: `non_phi | phi_masked | phi_direct` —
  **exists, source-level only. No column-level PHI flag** (the design doc's
  gates 1/3 assumed per-column granularity → this is the main remaining gap).
- **Snowflake engine + executor exist** (`posterra_portal/utils/query_executors/snowflake.py`)
  with a hospital-PHI security profile: write-once `saas.app.org_id`,
  `single_organization`, `dashboard.connection.tenant_scope_app_id`,
  four-condition org guard before any SQL, PHI audit logging, fail-closed
  source rules (PHI source app_ids must equal exactly the connection's app).
- AI Column Intelligence tab + bulk-fill script pattern
  (`posterra_portal/scripts/fill_inhome_column_intelligence.py`).

**Consequence:** `ai-assist-architecture.md` §4.1/Phase-1 is partially stale —
it must be updated to CONSUME `data_classification` + hospital-PHI profile
instead of proposing new `is_phi` source fields. Genuine remaining new work:
column-level PHI granularity, `ai.provider` model, agent service, panel,
`/ai/*` endpoints, per-app CH role DDL generator.

## 3. Immediate next step (blocked on the user)

User must run the inventory dump on their Windows Odoo host (this cloud
sandbox has no DB access):

```bat
cd "C:\Program Files\Odoo 19.0.20251113\server"
..\python\python.exe odoo-bin shell -c odoo.conf -d <db> < <repo>\posterra_portal\scripts\dump_schema_inventory.py > %USERPROFILE%\Desktop\schema_inventory.txt
```

Script committed on this branch: `posterra_portal/scripts/dump_schema_inventory.py`
(read-only; prints all sources w/ engine, apps, classification, AI-fill rate;
full column dump per app-scoped source; all connections w/ security profile).

With the output, deliver: table-by-table review of everything mapped to
`ulh-humana-ma` (CH + Snowflake) — classification corrections, AI-enablement,
column-intelligence fill priorities — and the design-doc reconciliation (§2).

**Specific flag to check first:** `ul_humana_star_gaps_patient` (35 cols,
ClickHouse-01, app `ulh-humana-ma`) is marked **Non-PHI** despite the
`_patient` suffix and a free-text `ADDITIONAL_GAP_INFORMATION` column.
Visible columns look aggregate (COMPLIANT_CNT / ELIGIBLE_CNT by
CONTRACT_NAME / COV_MONTH) but all 35 must be reviewed — misclassification
here would wave contents through to the LLM under the planned gates.

## 4. Known app data inventory (from screenshots — incomplete)

App `ulh-humana-ma`, connection ClickHouse-01 (all seen in admin UI):
`mer_data` (7), `mer_driver_by_category` (7), `utilization_snapshot` (7),
`UL_HUMANA_KPI_Member_FLOW` (9), `UL_HUMANA_POT` (10),
`ul_humana_retention_data` (16), `UL_HUMANA_Interaction_data` (11),
`ul_humana_star_gaps_patient` (35, Non-PHI?). Aggregated marts; domains
cluster as: cost/MER, utilization, member engagement (→ candidate scoped
agents). Snowflake sources: unknown until dump runs.

## 5. Branch state

- `claude/festive-carson-6f2gel`, rebased on origin/main (400db60), pushed.
  Commits: design doc (`docs/design/ai-assist-architecture.md`), inventory
  script, these notes. No PR opened (user hasn't asked).
- The graph-DB research findings live only in the conversation + §1 above;
  a fuller `docs/design/graph-db-evaluation.md` was offered but not requested.
