# POSTERRA PLATFORM — ARCHITECTURE CONTEXT
## For Cowork Sessions — Load This File First

**Generated from:** claude.ai architecture session (March 2026)  
**Purpose:** Full architectural context for continuing Posterra platform development in Cowork  
**Covers:** Multi-app platform design, auth/scoping architecture, data strategy, SKILL.md phase changes

---

## 1. WHAT IS POSTERRA

Posterra is a **multi-app healthcare analytics SaaS platform** built on:
- **Odoo 19 Community Edition** — backend, config, auth, admin UI
- **React + ECharts 5** — frontend dashboard rendering
- **PostgreSQL** — config models, reference data, audit log, session store
- **ClickHouse** (planned Phase 9) — analytics queries at scale
- **Redis** — caching, PgBouncer — connection pooling
- **Azure** — deployment target (Container Apps, PostgreSQL Flexible Server, Redis Cache)

The core philosophy: **admin configures everything from the Odoo backend, no code needed for new apps, pages, widgets, or user access.**

---

## 2. THE THREE APPS (AND BEYOND)

The platform hosts multiple independent apps, each with separate branding, login, and data scope. All share the same platform stack.

### App 1: Posterra (HHA Analytics) — Active
- Serves Home Health Agencies (HHAs)
- 13 dashboard pages: Overview, Hospitals, SNFs, Physicians, Competitive Intel, Case Mix, Portfolio Command Center, Leaderboard, Market Threats, Strategy, Reports, Admits, Referral Sources
- **Data:** `hha_base_data` (25M rows, ALL HHAs in US market — intentional for competitive intelligence)
- **Reference table:** `hha_provider` (CCN, DBA, Brand Name, State, County, City — CMS public data)
- **Scoping:** `hha_ccn = ANY(:entity_ids)` passed as query param — NOT RLS (market benchmarks need cross-tenant data)
- **Provisioning:** Domain hint (elaracaring.com → suggest Elara CCNs) + admin confirms

### App 2: ACO Builder — Planned
- Serves Accountable Care Organizations
- **Data:** `aco_data` (shared table, multiple ACOs)
- **Reference table:** `aco_reference`
- **Scoping:** `aco_id = ANY(:entity_ids)` — same pattern as Posterra
- **Provisioning:** Manual (no domain matching — ACO membership not derivable from email)
- No domain hint — admin picks ACO IDs directly

### App 3: Hospital Dashboard — Future
- Serves individual hospitals with their own uploaded claims data
- **Data:** `hospital_claims` partitioned by `org_id` (single ClickHouse table, NOT separate tables per client)
- **Scoping:** `org_id` RLS — physical partition IS the isolation
- **Provisioning:** Direct table — admin selects client record, system assigns org_id
- Multiple data roles per client: claims, quality, staffing, financial

### Future Apps (same platform, new data + widget configs)
- SNF Analytics (`snf_data` — same pattern as Posterra)
- Hospice Analytics
- IRF / LTACH Analytics
- Physician Group Analytics
- MA Plan Analytics
- Population Health / HEDIS
- Revenue Cycle Analytics
- Behavioral Health

---

## 3. THE THREE DATA CATEGORIES

Every table in the platform falls into one of three categories. This determines how scoping works.

| Category | Example | Scoping | Why |
|----------|---------|---------|-----|
| **Market data** | `hha_base_data`, `aco_data` | Query param filter (`hha_ccn = ANY(:entity_ids)`) | Competitive benchmarks intentionally need ALL rows. RLS would break market share calculations. |
| **Reference data** | `hha_provider`, `aco_reference` | No filter — fully public within app | CMS public data. Any logged-in user can look up any HHA's name/address. |
| **Client-owned data** | `hospital_claims` | `org_id` RLS + physical partition | Client uploaded it. Belongs exclusively to them. No cross-tenant value. |

**The `org_id` pattern** (Stripe/Slack universal pattern) applies ONLY to client-owned data. It does not apply to market data or reference data. This is the key distinction from generic multi-tenancy advice.

---

## 4. THE FIVE ODOO MODELS (AUTH + SCOPING)

### 4.1 `saas.app` — One record per app

```python
class SaaSApp(models.Model):
    _name = 'saas.app'

    name             = fields.Char(required=True)        # "Posterra"
    app_key          = fields.Char(required=True)        # "posterra" — URL prefix
    logo             = fields.Binary()
    primary_color    = fields.Char()
    entity_type      = fields.Selection([
        ('hha_ccn', 'HHA CCN (Posterra)'),
        ('aco_id',  'ACO ID (ACO Builder)'),
        ('org_id',  'Org ID (Hospital Dashboard)'),
    ], default='hha_ccn')
    provisioning_strategy = fields.Selection([
        ('domain_hint',  'Domain Hint (suggest from email)'),
        ('manual',       'Manual Assignment'),
        ('direct_table', 'Direct Table (one table per client)'),
    ], default='manual')

    # ── Scope resolution config (drives provisioning UI) ──────────────
    scope_ref_table       = fields.Char()   # "hha_provider"
    scope_result_col      = fields.Char()   # "HHA CCN" — becomes entity_ids values
    scope_display_col     = fields.Char()   # "HHA DBA" — shown in preview list
    scope_match_cols_json = fields.Text()   # JSON list of matchable columns
    # e.g. [{"col":"HHA DBA","label":"DBA Name"},
    #        {"col":"HHA Brand Name","label":"Brand Name"},
    #        {"col":"HHA Name","label":"Legal Name"}]
```

**saas.app setup examples:**

```
# Posterra:
scope_ref_table:   "hha_provider"
scope_result_col:  "HHA CCN"
scope_display_col: "HHA DBA"
scope_match_cols:  [HHA DBA, HHA Brand Name, HHA Name]

# ACO Builder:
scope_ref_table:   "aco_reference"
scope_result_col:  "aco_id"
scope_display_col: "aco_name"
scope_match_cols:  [aco_name, parent_org, aco_type]

# Hospital Dashboard:
scope_ref_table:   ""  (blank — uses client picker)
scope_result_col:  "org_id"
```

### 4.2 `saas.app.user.scope` — One record per user per app

```python
class SaaSAppUserScope(models.Model):
    _name = 'saas.app.user.scope'

    user_id      = fields.Many2one('res.users', required=True, ondelete='cascade')
    app_id       = fields.Many2one('saas.app',  required=True, ondelete='cascade')

    # Provisioning fields (how entity_ids were resolved)
    match_column = fields.Char()        # "HHA DBA"
    match_value  = fields.Char()        # "Elara Caring"
    match_mode   = fields.Selection([
        ('exact', 'Exact'),
        ('starts_with', 'Starts with'),
        ('contains', 'Contains'),
    ], default='exact')

    # Resolved result — written by action_resolve(), admin can manually edit
    entity_ids   = fields.Json(default=list)  # ['047114','677660','197161',...]
    entity_count = fields.Integer(compute='_compute_entity_count', store=True)

    # Hospital-specific
    client_id    = fields.Many2one('saas.app.client', ondelete='set null')

    role         = fields.Selection([
        ('viewer', 'Viewer'), ('manager', 'Manager'), ('admin', 'Admin'),
    ], default='viewer')
    is_active    = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_user_app', 'UNIQUE(user_id, app_id)',
         'One scope record per user per app.'),
    ]

    def action_resolve(self):
        """Query scope_ref_table to resolve entity_ids. Returns preview rows."""
        self.ensure_one()
        app = self.app_id
        if not app.scope_ref_table:
            raise UserError('App not configured for reference-table resolution.')

        col, value, mode = self.match_column, self.match_value, self.match_mode

        if mode == 'exact':
            where = f'LOWER("{col}") = LOWER(%(val)s)'
        elif mode == 'starts_with':
            where = f'LOWER("{col}") LIKE LOWER(%(val)s) || \'%%\''
        else:
            where = f'LOWER("{col}") LIKE \'%%\' || LOWER(%(val)s) || \'%%\''

        sql = f'''
            SELECT "{app.scope_result_col}" AS entity_id,
                   "{app.scope_display_col}" AS display_name
            FROM   {app.scope_ref_table}
            WHERE  {where}
              AND  "{app.scope_result_col}" IS NOT NULL
            ORDER  BY "{app.scope_display_col}"
        '''
        self.env.cr.execute(sql, {'val': value})
        rows = self.env.cr.dictfetchall()
        self.entity_ids = [r['entity_id'] for r in rows]
        return rows   # returned to JS for preview display
```

### 4.3 `saas.app.client` — For Hospital Dashboard (direct_table only)

```python
class SaaSAppClient(models.Model):
    _name = 'saas.app.client'

    app_id       = fields.Many2one('saas.app', required=True, ondelete='cascade')
    name         = fields.Char(required=True)      # "St. Mary's Hospital"
    org_id       = fields.Integer(required=True)   # integer used in RLS
    table_prefix = fields.Char()                   # "hosp_42" → hosp_42_claims etc.
    is_active    = fields.Boolean(default=True)
    table_ids    = fields.One2many('saas.app.client.table', 'client_id')
```

### 4.4 `saas.app.client.table` — Table registry per client

```python
class SaaSAppClientTable(models.Model):
    _name = 'saas.app.client.table'

    client_id  = fields.Many2one('saas.app.client', required=True, ondelete='cascade')
    role       = fields.Char(required=True)   # 'claims', 'quality', 'staffing', 'financial'
    table_name = fields.Char(required=True)   # actual PostgreSQL/ClickHouse table name
    description = fields.Char()
    is_active  = fields.Boolean(default=True)
    loaded_at  = fields.Datetime()
```

Widget SQL uses `{{table:claims}}` placeholder. Controller resolves to real table name via this registry at runtime. Example: `hosp_42_claims`.

### 4.5 `portal.audit.log` — HIPAA requirement

```python
class PortalAuditLog(models.Model):
    _name = 'portal.audit.log'
    _order = 'timestamp desc'
    # Append-only — never update or delete rows

    timestamp   = fields.Datetime(default=fields.Datetime.now, index=True)
    user_id     = fields.Many2one('res.users', ondelete='set null')
    app_id      = fields.Many2one('saas.app',  ondelete='set null')
    endpoint    = fields.Char()      # '/api/v1/widget/42/data'
    widget_id   = fields.Integer()
    sql_params  = fields.Json()      # {state: 'TX', entity_ids_count: 63}
    row_count   = fields.Integer()
    client_ip   = fields.Char()
```

One INSERT before every API data response. Required for HIPAA Technical Safeguards when App 3 (Hospital) goes live.

---

## 5. LOGIN FLOW — 6 STEPS, SAME FOR ALL APPS

```
1. User hits /my/posterra/login (or /my/aco-builder/login etc.)
2. Odoo session auth — res.users.authenticate() → session cookie
3. Controller reads app_key from URL path → looks up saas.app record
4. Loads saas.app.user.scope WHERE user_id=:uid AND app_id=:app_id
5. SET LOCAL session variables:
       app.entity_ids = '{047114,677660,...}'
       app.entity_type = 'hha_ccn'
       app.org_id = ''  (or '42' for Hospital)
6. React app renders with scoped data
```

**If scope record not found → redirect to /web/login (no access)**

---

## 6. FILTER BAR ARCHITECTURE

Filters cascade left to right. All geographic filters sourced from `hha_provider` (reference table), NOT from `hha_base_data`.

```
PROVIDER → STATE → COUNTY → CITY → YEAR → PAYER → [Apply]
```

### Filter endpoints (Phase 6 — sourced from hha_provider):

```
GET /api/v1/filters/providers
    → SELECT COALESCE("HHA DBA","HHA Name") || ' – ' || "HHA CCN" AS label, "HHA CCN" AS value
      FROM hha_provider WHERE "HHA CCN" = ANY(:user_ccns)

GET /api/v1/filters/states?ccns=[]
    → DISTINCT "HHA State Cd", "HHA State" WHERE "HHA CCN" = ANY(:ccns)

GET /api/v1/filters/counties?ccns=[]&states=[]
    → DISTINCT "HHA County" WHERE ccns + states filter

GET /api/v1/filters/cities?ccns=[]&states=[]&counties=[]
    → DISTINCT "HHA City" WHERE ccns + states + counties filter
```

### Params sent to every widget SQL:

```python
{
    'entity_ids': ('047114', '677660', ...),  # tuple for psycopg2 ANY()
    'year':       '2025',
    'ffs_ma':     'FFS',    # or '' for all
    'hha_state':  'TX',     # or '' for all
    'hha_county': '',
    'hha_city':   '',
}
```

### Standard widget SQL pattern:

```sql
SELECT hha_ccn, SUM(admits) AS total_admits
FROM hha_base_data
WHERE hha_ccn = ANY(%(entity_ids)s)
  AND year = %(year)s::int
  AND (%(ffs_ma)s = '' OR ffs_ma = %(ffs_ma)s)
  AND (%(hha_state)s = '' OR hha_state = %(hha_state)s)
GROUP BY hha_ccn
```

**Old pattern (deprecated):** `WHERE hha_id = %(hha_id)s::int` — replace with `hha_ccn = ANY(%(entity_ids)s)`

---

## 7. DATA SERVICE ABSTRACTION (Phase 6)

New file: `posterra_portal/services/data_service.py`

```python
class DataService:
    """
    All analytics SQL goes through here.
    PostgreSQL today → ClickHouse in Phase 9 by swapping _execute_backend().
    Zero changes to callers (API endpoints, widget data methods).
    """
    def __init__(self, env):
        self.env = env

    def execute(self, sql, params=None):
        self._validate_sql(sql)
        return self._execute_backend(sql, params or {})

    def _execute_backend(self, sql, params):
        # PostgreSQL (current)
        self.env.cr.execute(sql, params)
        cols = [d[0] for d in self.env.cr.description]
        return [dict(zip(cols, row)) for row in self.env.cr.fetchall()]
        # Phase 9: swap above 3 lines for clickhouse_driver call

    def _validate_sql(self, sql):
        # Existing _execute_sql safety logic moved here
        # Block DML/DDL, require SELECT/WITH first keyword
        pass
```

**Why this matters:** When you migrate to ClickHouse in Phase 9, you change ONE method. Every widget, every API endpoint, every filter query is unchanged.

---

## 8. CLICKHOUSE MIGRATION PLAN (Phase 9)

**Trigger:** ~200M rows OR P95 query latency > 500ms on materialized views.

**What moves to ClickHouse:**
- `hha_base_data` — primary analytics table
- `aco_data`
- `hospital_claims` (partitioned by org_id using ClickHouse native partitioning)
- All other analytics tables

**What stays in PostgreSQL forever:**
- All Odoo config models (`saas.app`, `saas.app.user.scope`, `dashboard.page`, etc.)
- `hha_provider`, `aco_reference` (reference/lookup tables)
- `portal.audit.log`
- Session store, Redis cache

**ClickHouse table structure for hha_base_data:**
```sql
CREATE TABLE hha_base_data (
    hha_ccn      String,
    year         UInt16,
    ffs_ma       String,
    admits       UInt32,
    hha_days     UInt32,
    hha_alwd     Decimal(12,2),
    -- ... all other columns
) ENGINE = MergeTree()
ORDER BY (hha_ccn, year)
```

**Hospital claims (partitioned by org_id — replaces per-client table anti-pattern):**
```sql
CREATE TABLE hospital_claims (
    org_id       UInt32,    -- partition key, RLS enforced via app.org_id session var
    drg          String,
    admits       UInt32,
    -- ... standard columns
    extra_fields JSON       -- client-specific proprietary fields
) ENGINE = MergeTree()
PARTITION BY org_id
ORDER BY (org_id, drg)
```

**No big bang:** DataService abstraction means this is a planned swap, not a crisis rewrite.

---

## 9. UPDATED PHASE SEQUENCE

```
PHASE 0   DB-Driven Pages, Tabs, Filters              ✅ COMPLETE
PHASE 1   Widget System (model + views + render)       ✅ COMPLETE
PHASE 4   White-Label Login + Strip Odoo Chrome        ← NEXT
PHASE 5   saas.app expansion (entity_type + strategy + scope config fields)
PHASE 5B  saas.app.user.scope + Provisioning UI (new phase ~3h)
PHASE 6   JSON API + DataService + Audit Log + Filter endpoints
PHASE 7   React Widget Grid + Provider Filter Bar
PHASE 8   Widget Click-Actions (drill + navigate)
PHASE 2   Seed Widgets + Validate All Types
PHASE 3   Performance & Polish
PHASE 9   ClickHouse Migration (post-MVP, triggered by scale)
```

---

## 10. PHASE-BY-PHASE CHANGES FROM TODAY'S SESSION

### Phase 5 — saas.app model (significant expansion)

**Add to existing `saas.app`:**
```python
entity_type           = fields.Selection([...])   # hha_ccn / aco_id / org_id
provisioning_strategy = fields.Selection([...])   # domain_hint / manual / direct_table
scope_ref_table       = fields.Char()
scope_result_col      = fields.Char()
scope_display_col     = fields.Char()
scope_match_cols_json = fields.Text()
```

**New models in Phase 5:**
- `saas.app.user.scope` — universal runtime auth record
- `saas.app.client` — paying client (Hospital Dashboard)
- `saas.app.client.table` — table registry per client

**Replace `_get_providers_for_user()`:**
```python
def _get_scope_for_user(user, app_key):
    app = request.env['saas.app'].sudo().search(
        [('app_key', '=', app_key)], limit=1)
    scope = request.env['saas.app.user.scope'].sudo().search([
        ('user_id', '=', user.id),
        ('app_id', '=', app.id),
        ('is_active', '=', True),
    ], limit=1)
    return (scope.entity_ids or []), app.entity_type
```

### Phase 5B — Provisioning UI (NEW PHASE)

Admin form for `saas.app.user.scope`:
- Select user + app → form adapts based on app's `provisioning_strategy`
- For reference-table apps (Posterra, ACO): shows Match Column (populated from `scope_match_cols_json`), Match Value, Match Mode, Resolve button
- Resolve button calls `action_resolve()` → shows preview list of resolved entities
- Admin confirms → `entity_ids` saved
- For direct_table apps (Hospital): shows Client picker from `saas.app.client` records instead

**Milestone:** Create scope for john.wick@elaracaring.com → app=Posterra → match on HHA DBA → "Elara Caring" → Contains → Resolve → see 63 CCNs → confirm → login as John → session has 63 CCNs.

### Phase 6 — JSON API (three additions)

1. **`services/data_service.py`** — DataService abstraction (see Section 7)
2. **Four new filter endpoints** — sourced from `hha_provider` (see Section 6)
3. **`portal.audit.log` model** — HIPAA append-only audit trail (see Section 5)

### Phase 7 — React Filter Bar (rewire)

- New Provider filter component (first in FilterBar)
- Calls `/api/v1/filters/providers` on mount with session CCNs
- State/County/City now call `hha_provider`-backed endpoints
- Widget SQL params change: `%(hha_id)s` → `%(entity_ids)s`

### Phase 9 — ClickHouse Migration (new, post-MVP)

- Zero code change beyond DataService `_execute_backend()` swap
- Triggered by scale, not by deadline
- PostgreSQL keeps config + auth + reference data forever

---

## 11. WHAT hha.scope.group BECOMES

`hha.scope.group` is NOT deleted. It becomes a **provisioning shortcut** that pre-saves match settings (column + value + mode). The create-user wizard can auto-populate the Phase 5B scope form from a scope group. Runtime auth reads `saas.app.user.scope.entity_ids` — scope groups just make provisioning faster.

---

## 12. SECURITY MODEL SUMMARY

| Threat | Mitigation | Layer |
|--------|-----------|-------|
| User sees other tenant's rows (market data) | Server-side validation that requested CCNs are subset of session entity_ids | Application |
| User sees other tenant's PHI (hospital data) | `org_id` RLS policy on hospital_claims | Database |
| PHI access audit trail | `portal.audit.log` — one INSERT per API call | Database |
| Raw SQL injection | `_validate_sql()` in DataService — blocks DML/DDL | Application |
| Session bleed between tenants | `SET LOCAL app.entity_ids` — scoped to transaction, auto-resets | Database |
| No access to any app | `saas.app.user.scope` record required — redirect to login if absent | Application |

---

## 13. KEY ARCHITECTURAL DECISIONS (LOCKED)

1. **Domain matching is provisioning-only, never runtime.** Fires once when creating scope record. Runtime reads `entity_ids` from scope record — domain is never consulted again.

2. **`org_id` applies only to client-owned data.** `hha_base_data` is market data — `org_id` RLS would break competitive benchmarking. Param filter is correct there.

3. **One MV per data grain (~16 MVs for Posterra).** Not one MV per widget. Widget SQL is simple SELECT against pre-aggregated MV.

4. **DataService abstraction from Phase 6.** All analytics SQL goes through `DataService.execute()`. Enables Phase 9 ClickHouse swap with zero caller changes.

5. **Hospital Dashboard uses single partitioned table, NOT per-client tables.** `hospital_claims PARTITION BY org_id` — one schema, N physical partitions. Avoids ALTER TABLE × 500 migration nightmare.

6. **`scope_match_cols_json` on `saas.app` makes provisioning config-driven.** New app type = new `saas.app` record with different ref table and match columns. Zero code for fourth app type.

7. **React owns the content area, QWeb owns the shell.** Sidebar, header, login = QWeb. Filter bar, tab bar, widget grid = React. Never mix.

8. **ECharts 5 for all charts.** No ApexCharts, no Chart.js. One library, 14 widget types.

---

## 14. FILE STRUCTURE ADDITIONS (New files from today's decisions)

```
posterra_portal/
├── models/
│   ├── saas_app.py                    ← EXPAND: add scope config fields
│   ├── saas_app_user_scope.py         ← NEW Phase 5: user scope model
│   ├── saas_app_client.py             ← NEW Phase 5: client + client.table models
│   └── portal_audit_log.py            ← NEW Phase 6: HIPAA audit log
├── services/
│   └── data_service.py                ← NEW Phase 6: DataService abstraction
├── controllers/
│   ├── portal.py                      ← CHANGE: _get_providers_for_user → _get_scope_for_user
│   └── widget_api.py                  ← CHANGE: use DataService + write audit log + new filter endpoints
├── views/
│   ├── saas_app_views.xml             ← EXPAND: add scope config fields to form
│   ├── saas_app_user_scope_views.xml  ← NEW Phase 5B: provisioning form with Resolve button
│   └── saas_app_client_views.xml      ← NEW Phase 5: client + table registry views
└── security/
    └── ir.model.access.csv            ← ADD: rows for new models
```

---

## 15. HOW TO START EACH COWORK SESSION

Always begin with:
> "Read POSTERRA_ARCHITECTURE_CONTEXT.md, then read SKILL.md. We are working on Phase [N]. [specific task]."

The SKILL.md file has the detailed implementation prompts per phase. This file has the architectural decisions that override or extend SKILL.md where they differ.

**Where SKILL.md and this file differ — this file wins:**
- `hha_id` param → replaced by `entity_ids` param
- `_get_providers_for_user()` → replaced by `_get_scope_for_user()`
- `saas.app` model → gains 6 new scope config fields
- `hha.scope.group` → provisioning shortcut only, not runtime auth
- Hospital isolation → single partitioned table, NOT `hosp_42_claims` naming

---

*End of context document. Total decisions captured: auth architecture, 3-app model, 3 data categories, 5 Odoo models, login flow, filter bar, DataService abstraction, ClickHouse plan, phase sequence, security model.*
