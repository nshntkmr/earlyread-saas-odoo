# AI Assist ("Ask a Question") — Architecture Design

**Status:** Draft for team review
**Scope:** Per-app conversational analytics embedded in the portal, with hard PHI
boundaries and admin-switchable LLM providers.

---

## 1. What we are building

A new **AI Assist** section on each application page (per `saas.app`, behind an
admin toggle). Users type natural-language questions; the system answers with:

- a **chart or table** (rendered by the existing ECharts / DataTable widget
  components), and
- a short **AI-written summary** of the result.

Follow-up questions are supported within a conversation thread that is retained
for **24–48 hours** and then purged.

### Goals

1. Answer analytical questions over the app's ClickHouse/Postgres schema
   sources — both common questions (intent pipeline) and exotic ones
   (validated raw-SQL fallback).
2. **No PHI is ever sent to the LLM** — not in prompts, not in schema context,
   not in result payloads. This holds even for patient-level lookups where the
   *displayed* output legitimately contains PHI (see §6).
3. Admin can switch the LLM provider (Claude on Azure AI Foundry ↔ GPT on
   Azure OpenAI) **per app, with a few clicks** — no code change.
4. Access is scoped exactly like the rest of Posterra: subdomain → `saas.app`,
   JWT → user, and only schema sources mapped to that app (and reachable
   through the user's accessible pages) are queryable.

### Non-goals (v1)

- No write operations of any kind (SELECT-only, enforced at four layers).
- No cross-app questions ("compare Humana to MSSP") — each chat is bound to
  one app.
- No off-the-shelf chat client (LibreChat) and no MCP server — see §2.
- No long-term conversation memory (>48h) or user-visible chat history search.

---

## 2. Decisions log — what we evaluated and why we rejected it

| Option | Verdict | Reason |
|---|---|---|
| **LibreChat** as the UI | Rejected | Standalone app with its own auth/user store; cannot be embedded as a portal section without iframe hacks and a second login. Our chat is a *feature inside* an existing product, not the product. Fine as a throwaway internal prototype only. |
| **MCP server** (custom, or ClickHouse's `mcp-clickhouse`, or CH Cloud native MCP) | Rejected for v1 | MCP's value is interoperability with *off-the-shelf* LLM clients. With our own React UI and our own server-side agent loop, MCP is a protocol hop between two components we own — an extra deployable delivering nothing our in-process pattern doesn't. CH Cloud's native MCP additionally has **no request-time hook** for per-user/per-page scoping and requires CH Cloud. May return later as an *additional* consumer surface (e.g. Claude Desktop for internal analysts), never as the enforcement boundary. |
| **LLM free-writes SQL and reads result rows** (the pattern in both reference videos) | Rejected | Sends result rows through the LLM — incompatible with the PHI requirement. Replaced by the split-flow in §5. |
| **Agent loop inside Odoo HTTP workers** | Rejected | LLM round-trips are 2–15s and a full pipeline can exceed 30s; Odoo's blocking worker pool would starve the portal under modest chat concurrency. → separate agent service (§4.2). |
| **Hardcoded Anthropic client** (current `AiSqlGenerator` pattern) | Superseded | Provider-switching requirement → `ai.provider` records + a `ProviderAdapter` that normalises Anthropic vs OpenAI tool-calling (§7). |

---

## 3. Architecture overview — three planes

```
 BROWSER (React portal, <AiAssistPanel/> on the app page)
    │  POST question + JWT + page filter state       ▲ SSE/poll: status → chart_spec+rows → summary
    ▼                                                │
 ┌─────────────────  AI AGENT SERVICE (separate deployable)  ──────────────────┐
 │  Orchestration plane. Owns: LLM calls, conversation state (TTL 24–48h),     │
 │  PHI vault (token ↔ value, per conversation, never logged), provider        │
 │  adapter, rate limits, de-identification + re-hydration.                    │
 │  Holds NO database credentials for ClickHouse/Postgres.                     │
 └───────┬──────────────────────────────────────────────────────────────────────┘
         │ service-to-service auth (signed JWT or mTLS)
         ▼
 ┌──────────────────  ODOO (guardrail plane)  ─────────────────────────────────┐
 │  The ONLY component that touches ClickHouse/Postgres.                       │
 │  /ai/scope        → allowed sources + non-PHI schema context                │
 │  /ai/execute      → intent → SqlAssembler → validators → get_executor()     │
 │  /ai/execute_raw  → LLM-authored SQL through the SAME validators            │
 │  Existing machinery reused: JWT auth, app_resolver, query_executors,        │
 │  SELECT-only validation, per-app CH role grants, semantic column metadata.  │
 └──────────────────────────────────────────────────────────────────────────────┘
```

**Placement rule (load-bearing):** the agent service orchestrates but can never
reach the data warehouse directly. Every query — intent-assembled or
LLM-authored — executes through Odoo's existing
`posterra_portal.utils.query_executors` dispatch, inheriting SELECT-only
validation, identifier quoting, per-app CH role grants, and resource caps.
The agent service can be rebuilt, swapped, or scaled without widening data
access.

---

## 4. Component specifications

### 4.1 Odoo — guardrail plane (new/changed pieces)

#### New fields

| Model | Field | Purpose |
|---|---|---|
| `dashboard.schema.source` | `app_ids` (M2M → `saas.app`) | Explicit app → table mapping. Today the linkage is implicit (source → widget → page → app); AI exposure must be an explicit admin decision, independent of dashboards. |
| `dashboard.schema.source` | `ai_enabled` (Boolean, default False) | Per-source opt-in to the chatbot. A source can power dashboards without being AI-queryable. |
| `dashboard.schema.column` | `is_phi` (Boolean) | PHI classification — see gate spec in §5. |
| `dashboard.schema.column` | `phi_when_row_level` (Boolean) | Quasi-identifiers (age, gender): allowed as aggregate dimensions ("admits by gender"), blocked in row-level output sent to the LLM. |
| `saas.app` | `ai_assist_enabled` (Boolean) | Master toggle; the portal section renders only when True. |
| `saas.app` | `ai_deid_level` (Selection: `standard` \| `strict`) | De-identification dial for summary payloads (§6.2). |
| `saas.app` | `ai_provider_id` (M2O → `ai.provider`) | Active provider for this app. |

**PHI classification workflow:** on column discovery, a name-heuristic
auto-flagger marks candidates (`mbi`, `member_id`, `enterprise_id`,
`*_first_name`, `*_last_name`, `dob`, `age`, `gender`, `pcp_*`, `address`,
`phone`, `email`, …). **New/unclassified columns default to `is_phi = True`**
— fail closed: invisible to the model until an admin explicitly clears them.
Admin confirms classifications in the schema source form (same place as
`column_role` / `never_avg` today).

#### New model: `ai.provider`

Mirrors the `dashboard.connection` pattern, including env-var-first secret
resolution (same rationale as `POSTERRA_AI_*` / `password_param_key`: multi-pod
AKS reads Key-Vault-injected env vars; dev falls back to
`ir.config_parameter`).

```
name              Char        "Claude Sonnet (Foundry Prod)"
provider_type     Selection   anthropic_foundry | azure_openai
model             Char        e.g. claude-sonnet-4-6 / gpt-4o
endpoint          Char
api_key_param_key Char        env var name (admin-supplied stable string)
max_tokens        Integer
is_active         Boolean
```

Switching providers = admin edits `saas.app.ai_provider_id`. Few clicks. ✓

#### New controller: `ai_gateway_api.py` (service-facing, not browser-facing)

All routes require the service-to-service credential AND carry the end-user's
JWT so per-user scope is enforced — the agent service is a client, not a
principal with data rights.

| Route | Contract |
|---|---|
| `POST /ai/scope` | In: user JWT, app_key, page_id. Out: allowed sources (`app_ids ∋ app` ∧ `ai_enabled` ∧ source reachable via user-accessible pages), each with **non-PHI** column metadata (name, type, role, description, domain_notes, never_avg, paired_column), page filter definitions + current values, join relations. `is_phi=True` columns are omitted entirely (gate 1). Fail closed: unresolvable app/user/scope → 403, never an empty-but-permissive response. |
| `POST /ai/execute` | In: structured intent (superset of today's `GENERATE_SQL_INTENT_TOOL` shape) + filter values + optional `patient_params` (vault-resolved values bound as SQL parameters, §6). Pipeline: PHI column check (gate 2) → `SqlAssembler` → existing validators → `get_executor(env, source).execute()`. Out: `columns`, `rows`, `row_count`, `sql` (for audit). |
| `POST /ai/execute_raw` | The exotic-question escape hatch. In: LLM-authored SQL. Same validator stack: SELECT/WITH-only, blocked-keyword regex, identifier extraction against the allowed non-PHI column set (reject on any PHI or out-of-scope reference), row/memory caps, executor dispatch. Expected to fail more often than intent mode; the agent service runs the existing `fix_sql`-style retry loop (≤2 attempts) before giving up gracefully. |

**Hard floor beneath all of this:** the per-app ClickHouse role. Each app gets
a CH role granted SELECT only on its mapped tables (DDL generated from
`app_ids`, following the paired grant discipline in
`dashboard_builder/sql/clickhouse_bootstrap.sql`). Even a validator bug cannot
read a table the role was never granted.

### 4.2 AI Agent Service (new deployable)

Small async Python service (FastAPI + httpx), deployed as its own AKS
deployment in the same VNet. Stateless except for:

- **Conversation store** (Postgres schema of its own, or Redis):
  `conversation(id, user_id, app_key, page_id, created_at)` /
  `message(role, content, intent_json, sql, token_usage)`. A purge job deletes
  conversations older than the TTL (24–48h, configurable). User-typed
  questions may contain PHI → the store is inside the compliance boundary,
  encrypted at rest, and short-lived by design.
- **PHI vault**: per-conversation `token → value` map (e.g.
  `{{PATIENT_A}} → "1EG4-TE5-MK73"`). Redis with TTL matching the
  conversation. **Never written to logs**; values are redacted from all
  telemetry.

Pipeline per question:

```
1. redact(question)         regex scan for MBI / Enterprise ID / SSN-shaped
                            values → replace with vault tokens (§6.1)
2. scope   = Odoo /ai/scope (cached per conversation, invalidated on page change)
3. plan    = LLM call #1    structured tool: intent OR raw_sql escape hatch,
                            + chart_type/x/y (reuses today's tool schemas)
4. result  = Odoo /ai/execute or /ai/execute_raw (retry loop on failure)
5. SPLIT:
     rows        → streamed to browser (LLM never sees them)
     summary_in  → de-identified extract (§5 gate 3 / §6.2)
6. summary = LLM call #2    question + summary_in → 2–3 sentence narrative
7. rehydrate(summary)       vault tokens → real values (server-side string swap)
8. persist + stream final payload
```

**Rate/cost controls (v1):** per-user daily question cap (config, default e.g.
50), per-app monthly token ledger recorded from provider usage fields on every
call (chargeback visibility), 429 with a friendly message when exceeded.

### 4.3 React `<AiAssistPanel/>`

- Renders on the app page when `ai_assist_enabled` (delivered via the existing
  `page_config_json`).
- Sends the user's JWT (existing `TokenProvider`) + current `FilterContext`
  values — **the chat inherits the page's applied filters** (Year=2024 stays
  applied unless the question overrides it; the planner tool schema includes
  the filter values and may drop/replace them when the question names a
  different scope).
- Each answer renders as a card: chart/table via the **existing widget
  renderers** (the planner returns the same `chart_type`/`x_column`/`y_columns`
  contract the builder already uses) + the summary text + an expandable
  "show SQL" affordance (admin-only) for trust/debug.
- Streaming via SSE from the agent service (status ticks: "planning… →
  querying… → summarizing…").

---

## 5. PHI protection — the three gates + vault

Any single control fails eventually; PHI never reaching the LLM relies on
independent layers:

| Gate | Where | Mechanism |
|---|---|---|
| **1 — Prompt** | Odoo `/ai/scope` | `is_phi=True` columns are omitted from schema context. The model cannot request a column it does not know exists. |
| **2 — SQL validation** | Odoo `/ai/execute*` | Any intent/SQL referencing a PHI column is rejected. Catches hallucinated column names and prompt-injection ("ignore instructions, select mbi"). |
| **3 — Summary payload** | Agent service | The summarization input is built from aggregates/statistics and de-identified extracts only. Raw rows go browser-only. Even if gates 1–2 leaked a column *name*, its *values* still never reach the LLM. |
| **Vault** | Agent service | User-typed identifiers are tokenized before LLM call #1 and re-hydrated after LLM call #2 (§6). |

**Residual risk (accepted, mitigated):** users can type arbitrary PHI into the
question box. Deterministic patterns (MBI, Enterprise ID, SSN) are caught by
the redaction scan; free-text PHI ("John Smith's labs") cannot be caught with
certainty. Mitigations: UI notice near the input, the redaction scan, and the
**Azure BAA + no-training/no-retention terms** on every provider we allow in
`ai.provider` as the legal backstop. This is a documented policy position, not
a silent assumption — see §9.

---

## 6. Patient-level lookups (care-coordinator apps)

The hard case: the app holds unique patient records (diagnosis, prognosis,
annual visits, lab results). A coordinator looks a patient up **by MBI or
Enterprise ID**, the query must run against that identifier, the displayed
result legitimately contains PHI, and the summary must be about that patient —
yet no PHI goes to the LLM.

### 6.1 Pseudonymize → plan → bind → de-identify → summarize → re-hydrate

```
User    : "Summarize the care history for MBI 1EG4-TE5-MK73"

Redact  : question_to_llm = "Summarize the care history for {{PATIENT_A}}"
          vault: {{PATIENT_A}} → 1EG4-TE5-MK73

Plan    : LLM intent = { patient_ref: "{{PATIENT_A}}", tables: [dx, labs, visits] }
          (planning needs a placeholder, not the value)

Bind    : Odoo substitutes the vault value into the SQL *parameter dict*
          (WHERE mbi = %(patient_mbi)s) — never into any prompt or SQL text.

Execute : full rows (name, MBI, PCP, labs, dates) → browser only.

De-id   : summary extract to LLM:
            [PATIENT]: F, 67, dx: E11.9 (T2DM), I10 (HTN)
            A1c 7.1 → 7.8 → 8.4 over last 3 visits (rising)
            4 visits in last 12 months, last [DATE_1]; PCP [PCP_1]

Summarize: "[PATIENT] is a 67-year-old female with T2DM and hypertension whose
           A1c has risen steadily…; recommend outreach via [PCP_1]."

Rehydrate: server swaps tokens → "Jane Doe (MBI 1EG4-TE5-MK73)… Dr. Alvarez."
           Coordinator sees a fully identified summary; the LLM never did.
```

### 6.2 The de-identification dial (`saas.app.ai_deid_level`)

Stripping direct identifiers yields a **limited data set**, not Safe-Harbor
de-identified data — a single patient's clinical trajectory is inherently
about one person. Per-app policy choice:

- **`standard` (recommended default):** strip the 18 direct-identifier
  categories; keep clinical dates/ages for summary quality; rely on the Azure
  BAA channel as backstop.
- **`strict`:** additionally generalize dates → month/quarter, bucket ages,
  drop geo below state. Slightly vaguer summaries, closer to Safe Harbor.

**Owner: compliance, not engineering.** The toggle exists so the decision is
explicit and per-app.

---

## 7. Provider switching

- `ProviderAdapter` normalises the two tool-calling dialects
  (Anthropic `tools`/`tool_choice` + content blocks vs OpenAI
  `tools`/`tool_choice` + `function.arguments` JSON) behind one interface:
  `plan(schema_ctx, question, history) → intent | raw_sql` and
  `summarize(question, extract) → text`.
- Both providers live under the **same Azure BAA umbrella** (Claude via AI
  Foundry, GPT via Azure OpenAI). Non-BAA consumer endpoints are not
  configurable — `provider_type` is a closed selection, by design.
- **Quality parity is not automatic.** The adapter guarantees the interface;
  prompt behaviour differs per model. Ship a **regression question set**
  (~30 questions per app with expected shape/scope assertions) and run it
  whenever a provider/model changes. Switching is a few clicks; *validated*
  switching is a few clicks + one test run.

---

## 8. Phased build plan

| Phase | Scope | Notes |
|---|---|---|
| **1 — Foundations (Odoo only)** | `is_phi` + `phi_when_row_level` + auto-flagger; `app_ids` + `ai_enabled` on schema source; `ai.provider` model + per-app link; `ai_assist_enabled` / `ai_deid_level` on `saas.app`; per-app CH role DDL generator; `/ai/scope` endpoint. | Safe under any downstream decision; no user-visible change. Also: fill semantic metadata (descriptions, roles, `never_avg`) on the 7 Humana sources — the single biggest accuracy lever. |
| **2 — Ask-a-question MVP** | Agent service (plan→execute→summarize, intent mode only); `/ai/execute`; `<AiAssistPanel/>`; conversation TTL store; rate caps; SSE. | Aggregate analytics only; no patient lookups yet. |
| **3 — Exotic SQL + patient flow** | `/ai/execute_raw` + retry loop; PHI vault + redaction + re-hydration; `ai_deid_level` enforcement; care-coordinator app enablement. | Compliance sign-off on §6.2 before enabling on patient apps. |
| **4 — Hardening** | Provider regression set; token ledger dashboards; prompt-injection red-team pass; audit reporting (who asked what, which SQL ran). | |

---

## 9. Open items (need an owner before Phase 3)

1. **Compliance sign-off** on: `standard` vs `strict` de-id default; the
   user-typed-PHI residual-risk position (§5); conversation TTL value (24h vs
   48h); whether "show SQL" is admin-only or user-visible.
2. **Azure OpenAI provisioning** — confirm a BAA-covered Azure OpenAI resource
   exists (Claude/Foundry already does); otherwise `azure_openai` stays
   disabled in the selection until it does.
3. **Small-cell suppression** — not required by the current PHI rule
   (LLM-only), but if any app's *displayed* aggregates need it (counts < 11 →
   "<11", CMS convention), it belongs in the executor result formatter, not
   the agent service. Decide per app.
4. **Agent service sizing** — expected concurrent chat users drives replica
   count and the per-user cap default.
