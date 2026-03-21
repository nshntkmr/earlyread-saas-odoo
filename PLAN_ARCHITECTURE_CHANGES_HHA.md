# Posterra Architecture Changes — HHA App Focus

## Relationship to Other Plans

This plan covers the **broader architectural changes** from `POSTERRA_ARCHITECTURE_CONTEXT.md` that affect the HHA app (Posterra). These are structural changes to models, auth flow, data access, and SQL patterns.

**Prerequisite:** [PLAN_PROVIDER_FILTER_CASCADE_FIX.md](./PLAN_PROVIDER_FILTER_CASCADE_FIX.md) should be completed first. It fixes the immediate Provider → State cascade bug using the existing `dashboard.page.filter` system. The changes in this document build on top of that fix and can be shipped incrementally.

**What this plan does NOT cover:**
- ACO Builder app (planned, not active)
- Hospital Dashboard app (future)
- ClickHouse migration (Phase 9, triggered by scale)
- Widget Click-Actions (Phase 8)

---

## Current State vs Target State

| Concern | Current (What Exists Today) | Target (Architecture Context) |
|---------|---------------------------|-------------------------------|
| User → HHA access | `partner.hha_provider_id` (direct) or `partner.hha_scope_group_id.provider_ids` (scope group) → returns recordset of `hha.provider` | `saas.app.user.scope.entity_ids` → returns list of CCN strings |
| Runtime auth function | `_get_providers_for_user(user)` → `hha.provider` recordset | `_get_scope_for_user(user, app_key)` → `(entity_ids, entity_type)` tuple |
| Provider identity | Odoo record IDs (`hha.provider.id` = integer) | CCN strings (`"197161"`, `"047114"`) |
| Widget SQL params | `WHERE hha_id = %(hha_id)s::int` | `WHERE hha_ccn = ANY(%(entity_ids)s)` |
| `saas.app` model | `access_mode` (hha_provider / group), `access_group_xmlid` | + `entity_type`, `provisioning_strategy`, `scope_ref_table`, `scope_result_col`, `scope_display_col`, `scope_match_cols_json` |
| SQL execution | Direct `self.env.cr.execute()` in widget/section models | `DataService.execute()` abstraction |
| Audit trail | None | `portal.audit.log` — append-only HIPAA audit |
| `hha.scope.group` | Runtime auth source | Provisioning shortcut only — pre-populates scope form |
| Filter options source | ORM `_read_group()` on `hha.provider` Odoo model | SQL against `hha_provider` reference table (same data, different access path) |

---

## Implementation Phases

These phases are ordered by dependency. Each can be shipped and tested independently.

---

## Phase A: Verify Phase 4 Milestones (White-Label Login)

**Estimated effort:** 1–2 hours
**Dependencies:** None
**Files touched:** None (verification only)

Phase 4 (White-Label Login + Strip Odoo Chrome) appears largely complete based on the existing `login_templates.xml`, `error_templates.xml`, and the `posterra_login()` controller. But the milestone checklist from SKILL.md has not been formally verified.

### Checklist

```
☐ Visit /my/posterra/login — see branded login page, NO Odoo navbar/footer
☐ Visit /my/posterra/overview — NO "Your Logo", "Home", "Contact us" header
☐ Visit /my/posterra/overview — NO "Useful Links", "About us" footer
☐ Trigger a 404 error — see branded error page, not Odoo default
☐ View page source — no "odoo" string in visible HTML/meta tags
```

### Action

Log in as a portal user and manually check each item. Fix any Odoo chrome leaks found. This is purely a verification pass — no planned code changes unless issues are found.

---

## Phase B: `saas.app` Model Expansion

**Estimated effort:** 2–3 hours
**Dependencies:** None (can run in parallel with Phase A)
**Files touched:** `models/saas_app.py`, `views/saas_app_views.xml`, `security/ir.model.access.csv`

### B.1 Add 6 New Fields to `saas.app`

These fields configure how each app resolves user access and provisions scope records. For the HHA app they have specific values; for future apps they'll have different values.

```python
# ── Entity & scope configuration ─────────────────────────────────────
entity_type = fields.Selection([
    ('hha_ccn', 'HHA CCN (Posterra)'),
    ('aco_id',  'ACO ID (ACO Builder)'),
    ('org_id',  'Org ID (Hospital Dashboard)'),
], default='hha_ccn',
   help='What kind of entity IDs are stored in user scope records.\n'
        'Determines how widget SQL filters data.')

provisioning_strategy = fields.Selection([
    ('domain_hint',  'Domain Hint (suggest from email domain)'),
    ('manual',       'Manual Assignment'),
    ('direct_table', 'Direct Table (one table per client)'),
], default='manual',
   help='How the admin provisions user access.\n'
        'Domain hint = suggest entities from email domain.\n'
        'Manual = admin picks entities directly.\n'
        'Direct table = admin picks a client record (Hospital Dashboard).')

scope_ref_table = fields.Char(
    string='Reference Table',
    help='PostgreSQL table name used to resolve entity IDs during provisioning.\n'
         'Example: "hha_provider" for Posterra, "aco_reference" for ACO Builder.\n'
         'Blank for direct_table apps (use client picker instead).',
)

scope_result_col = fields.Char(
    string='Entity ID Column',
    help='Column in the reference table that produces entity_ids values.\n'
         'Example: "HHA CCN" for Posterra, "aco_id" for ACO Builder.',
)

scope_display_col = fields.Char(
    string='Display Name Column',
    help='Column in the reference table shown in the provisioning preview.\n'
         'Example: "HHA DBA" for Posterra, "aco_name" for ACO Builder.',
)

scope_match_cols_json = fields.Text(
    string='Matchable Columns (JSON)',
    help='JSON array of columns the admin can match against during provisioning.\n'
         'Example: [{"col":"HHA DBA","label":"DBA Name"},\n'
         '          {"col":"HHA Brand Name","label":"Brand Name"},\n'
         '          {"col":"HHA Name","label":"Legal Name"}]',
)
```

### B.2 Coexistence with `access_mode`

The existing `access_mode` field (`hha_provider` / `group`) and `access_group_xmlid` **stay for now**. They remain the runtime auth mechanism until Phase C replaces them with `saas.app.user.scope`. This avoids a big-bang migration.

The new fields are informational during Phase B — they configure the provisioning UI (Phase C) but don't change runtime behavior yet.

### B.3 Posterra App Record Configuration

After upgrade, admin sets these values on the Posterra `saas.app` record:

| Field | Value |
|-------|-------|
| entity_type | `hha_ccn` |
| provisioning_strategy | `domain_hint` |
| scope_ref_table | `hha_provider` |
| scope_result_col | `HHA CCN` |
| scope_display_col | `HHA DBA` |
| scope_match_cols_json | `[{"col":"hha_dba","label":"DBA Name"},{"col":"hha_brand_name","label":"Brand Name"},{"col":"hha_name","label":"Legal Name"}]` |

**Note on column names:** The `hha_provider` table is an Odoo model, so column names in the database are the ORM field names (`hha_dba`, `hha_brand_name`, etc.), NOT the quoted display names from CMS data. The `scope_ref_table` value should be `hha_provider` (the Odoo model's `_table` value). If the scope resolution SQL queries the table directly (which it does in `action_resolve()`), the column names must match the actual PostgreSQL column names.

### B.4 Admin View Changes

Add a new tab "Scope Configuration" to the `saas.app` form view:

```xml
<page string="Scope Configuration" name="scope_config">
    <group>
        <group string="Entity Type">
            <field name="entity_type"/>
            <field name="provisioning_strategy"/>
        </group>
        <group string="Reference Table">
            <field name="scope_ref_table"
                   placeholder="e.g. hha_provider"
                   invisible="provisioning_strategy == 'direct_table'"/>
            <field name="scope_result_col"
                   placeholder="e.g. HHA CCN"
                   invisible="provisioning_strategy == 'direct_table'"/>
            <field name="scope_display_col"
                   placeholder="e.g. HHA DBA"
                   invisible="provisioning_strategy == 'direct_table'"/>
            <field name="scope_match_cols_json"
                   invisible="provisioning_strategy == 'direct_table'"
                   widget="ace"
                   options="{'mode': 'json'}"/>
        </group>
    </group>
</page>
```

### B.5 Testing Checklist

```
☐ Upgrade module — no errors, 6 new fields visible on saas.app form
☐ Open Posterra app record → Scope Configuration tab visible
☐ Set all 6 fields for Posterra → save without errors
☐ Existing access_mode/access_group_xmlid still works — login flow unchanged
☐ Portal still loads — no regressions
```

---

## Phase C: `saas.app.user.scope` Model + Provisioning UI

**Estimated effort:** 4–6 hours
**Dependencies:** Phase B (scope config fields on saas.app)
**Files touched:** NEW `models/saas_app_user_scope.py`, NEW `views/saas_app_user_scope_views.xml`, `models/__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`

This is the **biggest single change**. It introduces the universal per-user-per-app scope record that will eventually replace `_get_providers_for_user()`.

### C.1 New Model: `saas.app.user.scope`

```python
class SaaSAppUserScope(models.Model):
    _name = 'saas.app.user.scope'
    _description = 'User App Scope'
    _rec_name = 'user_id'
    _order = 'user_id asc, app_id asc'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade',
                               string='User')
    app_id = fields.Many2one('saas.app', required=True, ondelete='cascade',
                              string='Application')

    # ── Provisioning config (how entity_ids were resolved) ───────────
    match_column = fields.Char(string='Match Column')
    match_value = fields.Char(string='Match Value')
    match_mode = fields.Selection([
        ('exact', 'Exact'),
        ('starts_with', 'Starts with'),
        ('contains', 'Contains'),
    ], default='exact', string='Match Mode')

    # ── Resolved result ──────────────────────────────────────────────
    entity_ids = fields.Json(default=list,
        help='List of entity IDs this user can access.\n'
             'For Posterra: list of HHA CCN strings.\n'
             'Written by Resolve button, admin can manually edit.')
    entity_count = fields.Integer(
        compute='_compute_entity_count', store=True,
        string='Entity Count')

    # ── Role & status ────────────────────────────────────────────────
    role = fields.Selection([
        ('viewer', 'Viewer'),
        ('manager', 'Manager'),
        ('admin', 'Admin'),
    ], default='viewer')
    is_active = fields.Boolean(default=True)

    # ── Hospital-specific (Phase 5 Hospital Dashboard) ────────────────
    # client_id = fields.Many2one('saas.app.client', ondelete='set null')

    _sql_constraints = [
        ('unique_user_app', 'UNIQUE(user_id, app_id)',
         'One scope record per user per app.'),
    ]

    @api.depends('entity_ids')
    def _compute_entity_count(self):
        for rec in self:
            ids = rec.entity_ids or []
            rec.entity_count = len(ids) if isinstance(ids, list) else 0

    def action_resolve(self):
        """Query the app's reference table to resolve entity_ids.

        Uses match_column + match_value + match_mode from this record
        and scope_ref_table + scope_result_col from the app record.

        Returns preview rows for the UI.
        """
        self.ensure_one()
        app = self.app_id
        if not app.scope_ref_table or not app.scope_result_col:
            raise UserError(
                'App "%s" is not configured for reference-table resolution. '
                'Set Reference Table and Entity ID Column on the app record.' % app.name)

        col = self.match_column
        value = self.match_value
        mode = self.match_mode

        if not col or not value:
            raise UserError('Match Column and Match Value are required.')

        # Build WHERE clause based on match mode
        if mode == 'exact':
            where = f'LOWER("{col}") = LOWER(%(val)s)'
        elif mode == 'starts_with':
            where = f'LOWER("{col}") LIKE LOWER(%(val)s) || \'%%\''
        else:  # contains
            where = f'LOWER("{col}") LIKE \'%%\' || LOWER(%(val)s) || \'%%\''

        display_col = app.scope_display_col or app.scope_result_col

        sql = f'''
            SELECT "{app.scope_result_col}" AS entity_id,
                   "{display_col}" AS display_name
            FROM   "{app.scope_ref_table}"
            WHERE  {where}
              AND  "{app.scope_result_col}" IS NOT NULL
            ORDER  BY "{display_col}"
        '''
        self.env.cr.execute(sql, {'val': value})
        rows = self.env.cr.dictfetchall()

        self.entity_ids = [r['entity_id'] for r in rows]
        return rows
```

### C.2 Provisioning Form View

The form adapts based on the app's `provisioning_strategy`. For Posterra (domain_hint/manual), it shows match fields + Resolve button. The Match Column dropdown is populated from `scope_match_cols_json`.

```xml
<record id="view_saas_app_user_scope_form" model="ir.ui.view">
    <field name="name">saas.app.user.scope.form</field>
    <field name="model">saas.app.user.scope</field>
    <field name="arch" type="xml">
        <form string="User App Scope">
            <header>
                <button name="action_resolve" type="object"
                        string="Resolve Entities" class="btn-primary"
                        icon="fa-search"/>
            </header>
            <sheet>
                <group>
                    <group string="Assignment">
                        <field name="user_id"/>
                        <field name="app_id"/>
                        <field name="role"/>
                        <field name="is_active"/>
                    </group>
                    <group string="Match Configuration">
                        <field name="match_column"
                               placeholder="e.g. hha_dba"/>
                        <field name="match_value"
                               placeholder="e.g. Elara Caring"/>
                        <field name="match_mode"/>
                    </group>
                </group>
                <group string="Resolved Entities">
                    <field name="entity_ids" widget="json"
                           nolabel="1" colspan="2"/>
                    <field name="entity_count"/>
                </group>
            </sheet>
        </form>
    </field>
</record>
```

### C.3 Menu Item

```xml
<menuitem id="menu_user_scope"
          name="User Scope"
          parent="menu_posterra_config"
          action="action_saas_app_user_scope"
          sequence="20"/>
```

### C.4 What Happens to `hha.scope.group`

`hha.scope.group` is **NOT deleted**. It becomes a provisioning shortcut:

- Admin creates a scope group with match settings (column + value + mode)
- When creating a `saas.app.user.scope` record, the admin can pick a scope group to pre-populate the match fields
- Runtime auth will eventually read from `saas.app.user.scope.entity_ids`, not from `hha.scope.group.provider_ids`
- During the transition period, both systems coexist

### C.5 Migration Strategy for Existing Users

Existing Posterra users have access via `partner.hha_provider_id` or `partner.hha_scope_group_id`. These need to be migrated to `saas.app.user.scope` records.

**Migration script (run once after Phase C deployment):**

```python
# For each portal user with HHA access, create a scope record
for partner in env['res.partner'].search([
    '|',
    ('hha_provider_id', '!=', False),
    ('hha_scope_group_id', '!=', False),
]):
    user = partner.user_ids[:1]
    if not user:
        continue

    app = env['saas.app'].search([('app_key', '=', 'posterra')], limit=1)
    if not app:
        continue

    # Skip if scope record already exists
    existing = env['saas.app.user.scope'].search([
        ('user_id', '=', user.id),
        ('app_id', '=', app.id),
    ], limit=1)
    if existing:
        continue

    # Resolve CCNs from existing access
    if partner.hha_provider_id:
        ccns = [partner.hha_provider_id.hha_ccn]
        match_col = 'hha_ccn'
        match_val = partner.hha_provider_id.hha_ccn
        match_mode = 'exact'
    elif partner.hha_scope_group_id:
        ccns = partner.hha_scope_group_id.provider_ids.mapped('hha_ccn')
        match_col = partner.hha_scope_group_id.match_column or 'hha_dba'
        match_val = partner.hha_scope_group_id.match_value or ''
        match_mode = partner.hha_scope_group_id.match_mode or 'exact'
    else:
        continue

    env['saas.app.user.scope'].create({
        'user_id': user.id,
        'app_id': app.id,
        'match_column': match_col,
        'match_value': match_val,
        'match_mode': match_mode,
        'entity_ids': [c for c in ccns if c],
        'role': 'viewer',
        'is_active': True,
    })
```

### C.6 Testing Checklist

```
☐ Upgrade module — saas.app.user.scope model created, menu visible
☐ Create scope record: user=john.wick, app=Posterra, match_column=hha_dba,
  match_value="Elara Caring", match_mode=contains
☐ Click "Resolve Entities" → entity_ids populated with ~63 CCNs
☐ entity_count shows 63
☐ Save → record persists, unique constraint enforced (one scope per user per app)
☐ Create duplicate for same user+app → validation error
☐ Existing login flow still works (hha.scope.group / partner.hha_provider_id untouched)
☐ Run migration script → scope records created for all existing users
```

---

## Phase D: Switch Runtime Auth to `saas.app.user.scope`

**Estimated effort:** 3–4 hours
**Dependencies:** Phase C (scope model exists and is populated)
**Files touched:** `controllers/portal.py`, `controllers/main.py`, `controllers/widget_api.py`

This is the **cutover** — runtime auth switches from `_get_providers_for_user()` to `_get_scope_for_user()`. The old function stays as a fallback during transition.

### D.1 New Function: `_get_scope_for_user()`

```python
def _get_scope_for_user(user, app):
    """Load the user's scope record for this app.

    Returns:
        (entity_ids, entity_type) tuple.
        entity_ids is a list of strings (CCNs for Posterra).
        entity_type is a string ('hha_ccn', 'aco_id', 'org_id').
        Returns ([], '') if no scope found.
    """
    scope = request.env['saas.app.user.scope'].sudo().search([
        ('user_id', '=', user.id),
        ('app_id', '=', app.id),
        ('is_active', '=', True),
    ], limit=1)
    if scope and scope.entity_ids:
        return (scope.entity_ids, app.entity_type or 'hha_ccn')
    return ([], '')
```

### D.2 Transition Strategy — Dual Path with Fallback

During transition, the controller tries `_get_scope_for_user()` first. If no scope record exists, it falls back to `_get_providers_for_user()` and converts the result to CCN strings.

```python
def _resolve_user_access(user, app):
    """Resolve user access, with fallback to legacy system.

    Tries saas.app.user.scope first (new system).
    Falls back to hha.scope.group / partner.hha_provider_id (legacy).

    Returns:
        entity_ids: list of CCN strings
        provider_recordset: hha.provider recordset (for geo data, sidebar, etc.)
    """
    # New system first
    entity_ids, entity_type = _get_scope_for_user(user, app)
    if entity_ids:
        # Look up provider records from CCNs (needed for geo data, display name, etc.)
        providers = request.env['hha.provider'].sudo().search([
            ('hha_ccn', 'in', entity_ids)
        ])
        return entity_ids, providers

    # Legacy fallback
    providers = _get_providers_for_user(user)
    if providers:
        entity_ids = [p.hha_ccn for p in providers if p.hha_ccn]
        return entity_ids, providers

    return [], request.env['hha.provider'].browse()
```

### D.3 Controller Changes (`app_dashboard`)

Replace the access check section (lines 256–325) to use `_resolve_user_access()`:

**Before:**
```python
providers = _get_providers_for_user(request.env.user)
if not providers and not is_superadmin:
    return request.redirect('/my')
```

**After:**
```python
entity_ids, providers = _resolve_user_access(request.env.user, app)
if not entity_ids and not providers and not is_superadmin:
    return request.redirect('/my')
```

The rest of the controller (HHA selector, geo data, filter options) continues to use the `providers` recordset — no immediate change needed there. The `entity_ids` are used for `sql_params`.

### D.4 SQL Params Change

**Before** (current `portal.py` lines 470–487):
```python
sql_params = dict(filter_values_by_name)
sql_params.update({
    'hha_state': ctx_state,
    'hha_county': ctx_county,
    'hha_city': ','.join(ctx_cities),
    'hha_id': current_hha_id,
    'hha_name': selected_provider.hha_brand_name or ... if selected_provider else '',
})
```

**After:**
```python
sql_params = dict(filter_values_by_name)
sql_params.update({
    'hha_state': ctx_state,
    'hha_county': ctx_county,
    'hha_city': ','.join(ctx_cities),
    # NEW — entity_ids as tuple for psycopg2 ANY()
    'entity_ids': tuple(active_ccns),  # narrowed by Provider selection
    # LEGACY — keep for backward compat with existing widget SQL
    'hha_id': current_hha_id,
    'hha_name': selected_provider.hha_brand_name or ... if selected_provider else '',
})
```

Where `active_ccns` is:
- When Provider = "All" → `entity_ids` (all user's CCNs)
- When Provider = specific → `[selected_provider.hha_ccn]` (single CCN)

### D.5 Login Flow Changes (`main.py`)

The login redirect uses `_has_posterra_access()` which calls `_get_providers_for_user()`. Update to also check `saas.app.user.scope`:

```python
def _has_posterra_access(self, uid):
    user = request.env['res.users'].sudo().browse(uid)
    # New system
    app = request.env['saas.app'].sudo().search(
        [('app_key', '=', 'posterra'), ('is_active', '=', True)], limit=1)
    if app:
        entity_ids, _ = _get_scope_for_user(user, app)
        if entity_ids:
            return True
    # Legacy fallback
    return bool(_get_providers_for_user(user))
```

### D.6 Testing Checklist

```
☐ User with ONLY scope record (no legacy access) → can log in, sees dashboard
☐ User with ONLY legacy access (no scope record) → still works (fallback)
☐ User with BOTH → scope record takes precedence
☐ User with neither → redirected to /my
☐ sql_params includes entity_ids as tuple
☐ Widget SQL with %(entity_ids)s works alongside %(hha_id)s
☐ Provider filter cascade still works (uses providers recordset)
☐ Admin can deactivate scope record → user loses access immediately
```

---

## Phase E: DataService Abstraction

**Estimated effort:** 3–4 hours
**Dependencies:** None (can run in parallel with Phases B–D)
**Files touched:** NEW `services/__init__.py`, NEW `services/data_service.py`, `models/dashboard_widget.py`, `models/dashboard_page_section.py`

### E.1 New File: `services/data_service.py`

```python
import logging
import re

_logger = logging.getLogger(__name__)

# SQL safety: only SELECT and WITH are allowed as the first keyword
_ALLOWED_FIRST_KEYWORDS = {'select', 'with'}
_BLOCKED_KEYWORDS = {
    'insert', 'update', 'delete', 'drop', 'alter', 'truncate',
    'create', 'grant', 'revoke', 'exec', 'execute',
}


class DataService:
    """Abstraction layer for all analytics SQL execution.

    PostgreSQL today → ClickHouse in Phase 9 by swapping _execute_backend().
    Zero changes to callers (widget data methods, API endpoints).
    """

    def __init__(self, env):
        self.env = env

    def execute(self, sql, params=None):
        """Execute a read-only analytics query and return rows as dicts.

        Args:
            sql: SQL string with %(param)s placeholders
            params: dict of parameter values

        Returns:
            list[dict] — one dict per row, keys = column names

        Raises:
            ValueError: if SQL contains DML/DDL keywords
        """
        self._validate_sql(sql)
        return self._execute_backend(sql, params or {})

    def _execute_backend(self, sql, params):
        """PostgreSQL execution (current backend).

        Phase 9: replace these 3 lines with clickhouse_driver call.
        """
        self.env.cr.execute(sql, params)
        cols = [d[0] for d in self.env.cr.description]
        return [dict(zip(cols, row)) for row in self.env.cr.fetchall()]

    def _validate_sql(self, sql):
        """Block DML/DDL — only SELECT and WITH allowed."""
        stripped = sql.strip()
        if not stripped:
            raise ValueError('Empty SQL query')

        # Check first keyword
        first_word = re.split(r'\s', stripped, maxsplit=1)[0].lower()
        if first_word not in _ALLOWED_FIRST_KEYWORDS:
            raise ValueError(
                f'SQL must start with SELECT or WITH, got: {first_word}')

        # Scan for blocked keywords (outside of string literals)
        # Simple approach: lowercase and check word boundaries
        lower_sql = stripped.lower()
        for kw in _BLOCKED_KEYWORDS:
            if re.search(rf'\b{kw}\b', lower_sql):
                raise ValueError(f'Blocked SQL keyword found: {kw}')
```

### E.2 Integration into Widget Model

**Current** (`dashboard_widget.py` — `_execute_sql()` method):
```python
def _execute_sql(self, sql, params):
    # ... validation logic ...
    self.env.cr.execute(sql, params)
    cols = [d[0] for d in self.env.cr.description]
    return [dict(zip(cols, row)) for row in self.env.cr.fetchall()]
```

**After:**
```python
from ..services.data_service import DataService

def _execute_sql(self, sql, params):
    ds = DataService(self.env)
    return ds.execute(sql, params)
```

The existing `_execute_sql()` method becomes a thin wrapper. All validation logic moves into `DataService._validate_sql()`. This avoids changing every caller.

### E.3 Integration into Page Section Model

Same pattern — `dashboard_page_section.py`'s SQL execution calls through DataService.

### E.4 Testing Checklist

```
☐ Widget with valid SELECT SQL → renders correctly (no regression)
☐ Widget with INSERT attempt → blocked by DataService validation
☐ Widget with DROP TABLE → blocked
☐ Error messages include the blocked keyword for admin debugging
☐ Page sections still render their SQL queries
☐ Performance: no measurable overhead from the abstraction layer
```

---

## Phase F: `portal.audit.log` Model

**Estimated effort:** 2–3 hours
**Dependencies:** None (can run in parallel)
**Files touched:** NEW `models/portal_audit_log.py`, `controllers/widget_api.py`, `models/__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`

### F.1 New Model

```python
class PortalAuditLog(models.Model):
    _name = 'portal.audit.log'
    _description = 'Portal Audit Log'
    _order = 'timestamp desc'
    _log_access = False  # Disable Odoo's write_date/write_uid — we manage our own

    timestamp = fields.Datetime(
        default=fields.Datetime.now, index=True, readonly=True)
    user_id = fields.Many2one(
        'res.users', ondelete='set null', readonly=True)
    app_id = fields.Many2one(
        'saas.app', ondelete='set null', readonly=True)
    endpoint = fields.Char(readonly=True)
    widget_id = fields.Integer(readonly=True)
    sql_params = fields.Json(readonly=True)
    row_count = fields.Integer(readonly=True)
    client_ip = fields.Char(readonly=True)
```

### F.2 Integration into Widget API

In `widget_api.py`, add one INSERT before every data response:

```python
def _write_audit_log(self, user, app, endpoint, widget_id=None,
                     sql_params=None, row_count=0):
    """Append-only HIPAA audit entry."""
    try:
        request.env['portal.audit.log'].sudo().create({
            'user_id': user.id,
            'app_id': app.id,
            'endpoint': endpoint,
            'widget_id': widget_id or 0,
            'sql_params': {
                k: v for k, v in (sql_params or {}).items()
                if k != 'entity_ids'  # don't log full CCN list, just count
            } | ({'entity_ids_count': len(sql_params.get('entity_ids', []))}
                 if sql_params else {}),
            'row_count': row_count,
            'client_ip': request.httprequest.remote_addr,
        })
    except Exception:
        _logger.warning('Audit log write failed', exc_info=True)
```

### F.3 Admin View

Read-only list view under a new menu: **Posterra → Audit Log**. Filterable by user, app, date range.

### F.4 Testing Checklist

```
☐ Fetch widget data via API → audit log record created
☐ Audit log shows: user, app, endpoint, widget_id, params, row count, IP
☐ entity_ids NOT stored in audit (only count) — avoid logging PHI
☐ Audit log records are read-only in the admin UI
☐ Failed audit write does NOT block the API response
```

---

## Phase G: Widget SQL Migration (`hha_id` → `entity_ids`)

**Estimated effort:** 2–3 hours
**Dependencies:** Phase D (entity_ids in sql_params)
**Files touched:** All widget SQL queries (via Odoo backend, not code files)

### G.1 The Pattern Change

**Old pattern:**
```sql
WHERE hha_id = %(hha_id)s::int
```

**New pattern:**
```sql
WHERE hha_ccn = ANY(%(entity_ids)s)
```

### G.2 Scope

This affects every `dashboard.widget` record's `query_sql` field and every `dashboard.page.section` record's `query_sql` field. These are stored in the database, not in code files.

### G.3 Migration Approach

Option 1: SQL update script
```sql
UPDATE dashboard_widget
SET query_sql = REPLACE(query_sql, 'hha_id = %(hha_id)s::int', 'hha_ccn = ANY(%(entity_ids)s)')
WHERE query_sql LIKE '%hha_id = %(hha_id)s::int%';
```

Option 2: Manual review and update via admin UI (recommended for first pass — verify each query).

### G.4 Backward Compatibility

During transition, `sql_params` includes BOTH `hha_id` and `entity_ids`. Old widgets using `%(hha_id)s` still work. New widgets use `%(entity_ids)s`. This allows gradual migration without breaking anything.

### G.5 Testing Checklist

```
☐ Widget with new %(entity_ids)s pattern → renders correctly
☐ Widget with old %(hha_id)s pattern → still renders (backward compat)
☐ Widget with invalid SQL → error card, not 500
☐ Page sections with entity_ids pattern → render correctly
```

---

## Dependency Graph

```
Phase A (Verify Phase 4)     ──────────────────────────────────────────┐
                                                                        │
Phase B (saas.app fields)    ──→ Phase C (user.scope model)            │
                                    │                                    │
                                    ↓                                    │
                              Phase D (runtime auth cutover) ──→ Phase G (SQL migration)
                                                                        │
Phase E (DataService)        ──────────────────────────────────────────┤
                                                                        │
Phase F (audit.log)          ──────────────────────────────────────────┘
                                                                        │
                              ┌─────────────────────────────────────────┘
                              ↓
                    All phases complete → legacy _get_providers_for_user()
                    can be deprecated (but keep as dead code for safety)
```

**Parallelism opportunities:**
- Phases A, B, E, F can all run in parallel
- Phase C depends on B
- Phase D depends on C
- Phase G depends on D

---

## Cross-References

| This Plan | Filter Cascade Plan | Relationship |
|-----------|--------------------|-|
| Phase D: `_resolve_user_access()` returns `entity_ids` + `providers` | Filter cascade uses `providers` for `provider_ids` in `get_options()` | Filter cascade continues to use provider record IDs for option scoping. `entity_ids` (CCN strings) are for widget SQL. The two systems serve different purposes. |
| Phase D: `sql_params['entity_ids']` | Filter cascade: `sql_params['hha_id']` | Both are present during transition. Widgets can use either. |
| Phase B: `saas.app` gains scope config fields | Filter cascade: `saas.app` unchanged | No conflict. Scope config fields are informational for provisioning UI. |
| Phase G: Widget SQL changes | Filter cascade: widget SQL unchanged | Filter cascade fix doesn't touch widget SQL. Phase G migrates widget SQL independently. |

---

## What Gets Deprecated (Not Deleted)

After all phases are complete and verified:

| Item | Status | Notes |
|------|--------|-------|
| `_get_providers_for_user()` | Deprecated | Keep as dead code. `_resolve_user_access()` falls back to it. Remove after 2 release cycles. |
| `partner.hha_provider_id` | Deprecated | Still readable. New users provisioned via `saas.app.user.scope` only. |
| `partner.hha_scope_group_id` | Deprecated | Scope groups become provisioning shortcuts. Runtime reads `user.scope.entity_ids`. |
| `hha.scope.group` model | Stays | Becomes provisioning helper. Not deleted. |
| `access_mode` on `saas.app` | Deprecated | Replaced by `entity_type` + `saas.app.user.scope` existence check. Keep for backward compat. |
| `sql_params['hha_id']` | Deprecated | Keep alongside `entity_ids` during transition. Remove after all widget SQL migrated. |

---

## Total Estimated Effort

| Phase | Effort | Can Parallelize With |
|-------|--------|---------------------|
| A: Verify Phase 4 | 1–2h | B, E, F |
| B: saas.app fields | 2–3h | A, E, F |
| C: user.scope model + UI | 4–6h | E, F (after B) |
| D: Runtime auth cutover | 3–4h | (after C) |
| E: DataService | 3–4h | A, B, C, F |
| F: audit.log | 2–3h | A, B, C, E |
| G: Widget SQL migration | 2–3h | (after D) |
| **Total** | **17–25h** | |

With maximum parallelism (two developers or two sessions), critical path is: B → C → D → G = **11–16 hours**.
