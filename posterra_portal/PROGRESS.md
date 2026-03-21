# Posterra Portal — Phase Progress Log

> Last updated: 2026-03-12
> Module: `posterra_portal` | Odoo 19.0
> Location: `C:\Users\nisha\Odoo_Dev\posterra_portal\`

---

## Phase 4 — White-Label Login + Strip Odoo Chrome ✅

### Checklist

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | `/my/posterra/login` — branded login page, no Odoo navbar/footer | ✅ | Standalone template at `views/login_templates.xml`, route at `controllers/portal.py` |
| 2 | `/my/posterra/overview` — no "Your Logo", "Home", "Contact us" header | ✅ | Removed via `base_layout` with `no_header=True`, `no_footer=True` |
| 3 | `/my/posterra/overview` — no "Useful Links", "About us" footer | ✅ | Removed via `no_footer=True`, `no_copyright=True` in `base_layout` |
| 4 | 404 trigger — branded error page (not Odoo default) | ✅ | `views/error_templates.xml` overrides all 5 Odoo error templates |
| 5 | Page source — no Odoo chrome in visible HTML | ✅ | Clean page title, Posterra favicon, no portal navbar or breadcrumbs |
| ⚠️ | `odoo.__session_info__` JS global still present in source | Known limitation | Unavoidable — required by Odoo JS runtime; not visible in rendered UI |

### Files Built

| File | What it does |
|---|---|
| `views/dashboard_templates.xml` — `base_layout` | Minimal shell calling `web.frontend_layout` with `no_header`, `no_footer`, `no_copyright`. Strips all Odoo chrome from every portal page. Sets Posterra favicon and page title. |
| `views/dashboard_templates.xml` — `dashboard` | Custom sidebar + content layout using `pv-*` CSS classes. No portal navbar, no breadcrumbs. Sidebar uses `app.app_key` / `app.name` dynamically (Phase 5 integration). |
| `views/login_templates.xml` — standalone `login` template | Fully independent branded login card: heartbeat icon, title, subtitle, email/password fields, error/success alerts, password toggle button, CSRF token. |
| `views/login_templates.xml` — `posterra_website_login_layout` | Strips Odoo website chrome from `/web/login` fallback (no_header / no_footer). |
| `views/login_templates.xml` — `login_layout_posterra` | Injects Posterra branding (heartbeat icon + "Posterra" + "Healthcare Analytics Portal") above the `/web/login` form via `xpath` on `//form[@role='form']`. |
| `views/error_templates.xml` | 5 branded error pages: 404, 403, 4xx (generic), http_error, 500. Dark gradient background, Posterra logo, large error code, "Go to Dashboard" button. |
| `controllers/portal.py` — `posterra_login` | Route `/my/<app_key>/login` (auth=none). GET renders branded login card; POST authenticates and redirects to `/my/<app_key>`. Unknown `app_key` falls back to `/web/login`. |
| `static/src/css/posterra.css` — `pv-login-*` | Login card styles: dark gradient body (`#0f1623 → #1a2744`), white card, brand section, form labels, submit button, password toggle, copyright footer. |
| `static/src/css/posterra.css` — `pv-error-*` | Error page styles: gradient background, 120px error code, white text, Posterra brand footer. |
| `static/src/img/favicon.png` | Posterra heartbeat favicon (32×32 PNG). Used in `base_layout`, login template, and error templates. |

---

## Phase 5 — saas.app Model + Multi-App URL Routing ✅

### Checklist

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | `saas.app` record for "Posterra" with colors and tagline | ✅ | Seed record: `app_key=posterra`, `primary_color=#0066cc`, `tagline=Healthcare Analytics Portal`. Logo uploadable via admin UI. |
| 2 | Second `saas.app` record for "ACO Builder" / "MSSP Portal" | ✅ | SKILL.md used "ACO Builder" as placeholder — project uses **MSSP Portal** (`app_key=mssp`, `access_mode=group`). |
| 3 | `/my/posterra/login` — Posterra branding | ✅ | Confirmed working: branded card, dark background, correct app name/tagline. |
| 4 | `/my/mssp/login` — MSSP branding | ✅ | Same template, different app context — `/my/mssp/login` loads MSSP Portal branding. |
| 5 | Pages are scoped: app A pages don't appear in app B sidebar | ✅ | `dashboard.page.app_id` Many2one scopes each page to one app; controller queries `[('app_id','=',app.id)]`. |
| 6 | Admin views: Configuration → Applications shows both app records | ✅ | `views/saas_app_views.xml` provides tree/form/menu under **Posterra → Configuration → Applications**. |

### Files Built

| File | What it does |
|---|---|
| `models/saas_app.py` *(new)* | `saas.app` model: `app_key`, branding fields (logo, favicon, tagline, colors, custom CSS), `access_mode` (hha_provider / group), `access_group_xmlid`, `page_ids` One2many, `page_count` computed. |
| `models/dashboard_page.py` | Added `app_id` Many2one → `saas.app` (scopes each page to one app). `portal_type` kept but hidden from views (used in migration only). |
| `data/saas_apps_data.xml` *(new)* | Seed records (`noupdate=1`): **Posterra** (`hha_provider` mode) + **MSSP Portal** (`group` mode, requires `group_posterra_mssp_user`). |
| `__init__.py` — `post_init_hook` | Populates `app_id` on all existing pages from `portal_type` mapping (`hha`/`all` → Posterra, `mssp` → MSSP Portal). Safe to run on upgrade (only fills pages where `app_id` is still `False`). |
| `views/saas_app_views.xml` *(new)* | Admin tree + form views for `saas.app`. Form has: Identity tab, Branding tab (color pickers, logo), Access Control tab, Pages One2many. Menu: **Configuration → Applications**. |
| `views/page_views.xml` | Replaced `portal_type` field with `app_id` in list and form views. |
| `security/dashboard_access.xml` | Added ACL rows for `saas.app`: portal users get read-only; admin gets full CRUD. |
| `controllers/portal.py` — `app_dashboard` | Single generic route `/my/<app_key>/[page_key]/[tab_key]` replacing two hardcoded routes. Resolves app from URL → checks `access_mode` → loads pages by `app_id` → renders dashboard. |
| `controllers/portal.py` — `home()` | Redirects portal users to correct app: group-based apps first (MSSP), then HHA apps (Posterra). Fully driven by `saas.app` records — no hardcoded app keys. |
| `controllers/main.py` | `_get_portal_app_for_user(uid)` — replaces old HHA-only redirect helpers. Handles group-based apps (MSSP) first, then HHA-provider apps (Posterra), at login time. |
| `views/dashboard_templates.xml` | All links, titles, sign-out URL, sidebar brand use `app.app_key` / `app.name` dynamically. No hardcoded "posterra" strings in templates. |
| `models/__init__.py` | Added `from . import saas_app`. |
| `__manifest__.py` | Registered `views/saas_app_views.xml` and `data/saas_apps_data.xml`. |

### Bug Fixes Completed During Phase 5

| Fix | Root Cause | Resolution |
|---|---|---|
| **Settings OWL crash** (`TypeError: Cannot read properties of null (reading 'replaceAll')`) | `res_config_settings_views.xml` `<app>` element was missing `name` attribute — `SettingsFormCompiler.compileApp` called `node.getAttribute('name')` and got `null`. | Added `name="posterra_portal"` to `<app>` element; removed non-standard `data-string` attribute. |
| **`_login_redirect` AttributeError** | `PosterraPortal(CustomerPortal)` cannot access `Home._login_redirect` via `super()`. | Removed override in that class; redirect handled directly inside `posterra_login` route. |
| **`groups_id` field removed in Odoo 19** | `res.users.groups_id` is no longer a writable ORM field in Odoo 19. | Switched all group membership writes to `group.write({'user_ids': [(4/3, uid)]})` on `res.groups`. |
| **`users` field renamed in Odoo 19** | `res.groups.users` renamed to `user_ids` in Odoo 19 source. | Updated all group membership code to use `user_ids` field. |
| **MSSP Portal `access_mode` stuck as "HHA Provider"** | Seed data had `noupdate="1"`, so the wrong value loaded on first install and upgrades could not overwrite it. | Applied direct DB update: `UPDATE saas_app SET access_mode='group' WHERE app_key='mssp'`. Admin can also fix via **Configuration → Applications → MSSP Portal → Edit**. |
| **Wizard ACL missing** (`Access Error: You are not allowed to access 'Create Portal User Wizard'`) | `posterra.create.portal.user` and `hha.csv.import` transient models had zero `ir.model.access` rows — Odoo 19 requires explicit ACL for all models. | Added ACL rows for both wizard models in `security/dashboard_access.xml` for `group_posterra_admin`. |
| **Portal App Access UI** | No UI on Contact form to assign app access; admins had to manually edit security groups in Settings → Users. | Added `portal_app_ids` Many2many on `res.partner` + `write()` auto-sync of security groups + "Portal Access" smart button on Contact form + `app_ids` field in Create Portal User wizard. |

---

## Portal App Access UI — Feature Detail ✅

Added as part of Phase 5 stabilisation. Allows admins to manage which apps a contact can sign into directly from the Contact form.

### How it works

1. **`portal_app_ids` field** — Many2many on `res.partner` → `saas.app` via `res_partner_saas_app_rel` table.
2. **Auto-sync** — Whenever `portal_app_ids` changes on a partner, the `write()` override automatically:
   - Resolves which security groups are required by the new app list
   - Removes groups from the user that are no longer required
   - Adds groups for newly added apps
   - Only affects portal (`share=True`) users — internal users are never touched
3. **Smart button** — "Portal Access" button on Contact form opens the Create Portal User wizard pre-populated with the current contact.
4. **Wizard** — `app_ids` Many2many field in the wizard selects which apps to grant access to; wizard writes `portal_app_ids` on the partner, which triggers the auto-sync.

### Access assignment methods

**Method A — Portal Access button (recommended for new users)**
1. Open a Contact (Contacts → [partner])
2. Click **Portal Access** button (top-right button box)
3. In the wizard: select Partners, optionally set HHA Scope Group, select Portal Apps
4. Click **Create Users** — user is created (if needed), added to `base.group_portal`, and assigned the correct security groups

**Method B — Edit the Contact directly (for existing users)**
1. Open a Contact
2. Edit the **Portal App Access** field (many2many tags)
3. Add or remove apps → Save
4. Security groups on the linked user update automatically

---

## Admin-Configurable App Registry

The entire multi-app system is driven by **Posterra → Configuration → Applications**. No app keys or group names are hardcoded in controllers or templates.

| Field | Purpose |
|---|---|
| **App Key** | URL segment — e.g. `posterra` → `/my/posterra/` |
| **Access Mode** | `HHA Provider` (uses provider lookup) or `Security Group` (uses XML ID check) |
| **Required Group (XML ID)** | For Security Group mode — e.g. `posterra_portal.group_posterra_mssp_user` |
| **Primary Color** | Hex color used in login page branding |
| **Tagline** | Subtitle shown on login card |
| **Logo / Favicon** | Binary fields — upload via admin form |
| **Custom CSS** | Per-app CSS injected into every page for that app |
| **Pages** | One2many list of all `dashboard.page` records scoped to this app |

---

---

## Phase 6 — JSON API Endpoints ✅

### Checklist

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | `POST /api/v1/auth/login` — credentials → JWT access + refresh tokens | ✅ | Returns tokens + user info + app branding + pages list in one call |
| 2 | `GET /api/v1/page/<page_key>/config` — full page structure | ✅ | Returns tabs, filters with options, widget metadata, HHA selector, filter_dep_map |
| 3 | `GET /api/v1/widget/<id>/data` — single widget computed data | ✅ | Accepts filter params as query string; calls `get_portal_data()` unchanged |
| 4 | `GET /api/v1/filters/cascade` — dynamic filter options | ✅ | `filter_id + parent_value` → scoped options; identical to AJAX endpoint |
| 5 | `POST /api/v1/auth/refresh` — renew access token | ✅ | Refresh token → new access token (7-day TTL) |
| 6 | 401 on missing/invalid token | ✅ | All protected endpoints return `{"error":"...","status":401}` |

### Files Built

| File | What it does |
|---|---|
| `controllers/auth_api.py` *(new)* | JWT helpers (HS256, standard-library only). `POST /api/v1/auth/login` authenticates via SQL + `_crypt_context()` (Odoo 19 `auth='none'` workaround), returns token pair + user + app + pages. `POST /api/v1/auth/refresh` exchanges refresh token for new access token. |
| `controllers/widget_api.py` *(new)* | `GET /api/v1/page/<key>/config` — full page config. `GET /api/v1/widget/<id>/data` — widget data via `get_portal_data()`. `GET /api/v1/filters/cascade` — dynamic filter options. All require Bearer JWT. |
| `controllers/__init__.py` | Added `auth_api` and `widget_api` imports. |

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **SQL + `_crypt_context()` for auth** | Both `_login()` and `_check_credentials()` crash with "Expected singleton: res.users()" in Odoo 19 `auth='none'` routes. Direct SQL + passlib verify is identical security, zero ORM complications. |
| **Pages list in login response** | React gets sidebar navigation in one call — no hardcoded page keys, no extra round-trip |
| **`app.default_page_key`** | Admin-configurable default page; avoids React hardcoding which page to open first |
| **`nav_section_id.name`** | `dashboard.page` has `nav_section_id` Many2one (not `sidebar_section` string field) |
| **JWT secret in `ir.config_parameter`** | Auto-generated on first use, persisted to DB, survives service restarts |
| **Standard-library JWT** | No external PyJWT dependency — uses `hmac`, `hashlib`, `base64`, `json`, `time` |

### Odoo 19 API Issues Encountered & Solved

| Issue | Root Cause | Fix |
|---|---|---|
| `_login()` returns namedtuple | Odoo 19 returns `LoginResult(uid, auth_method, mfa)` not plain int | Switched to SQL + `_crypt_context()` approach entirely |
| `_check_credentials()` crashes | Rebuilds user recordset in new env → `res.users()` empty → `ensure_one()` fails | Same fix — SQL approach bypasses ORM |
| `session.authenticate()` crashes | `request.session.sid` is None in `auth='none'` → `_compute_session_token()` crashes | Same fix |
| `get_data(as_text=True)` returns empty | Odoo 19 consumes WSGI input stream before `auth='none'` code runs | Use `request.httprequest.get_json(force=True, silent=True)` + `.data` fallback |

---

## Next Phase

**Phase 7 — React Frontend**

See `SKILL.md` Phase 7 for the full specification.
