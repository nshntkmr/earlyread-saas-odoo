# EarlyRead Care Management — Product & Technical Design

**Status:** Draft v1.1 — 2026-07-11 (v1.1 adds §2b framework decisions + §2c Azure service map)
**Goal:** A standalone care-management product ("EarlyRead Care Management") that replicates RoundingWell's six capability blocks — Workflows, Actions, Worklists, Forms, Automations, Dashboards — built OUTSIDE Odoo, usable first by an NP-driven podiatry ACO group (~80K patients, athenahealth EHR, ACO REACH + MA), and sellable as its own SaaS later.

---

## 1. Why standalone (and the licensing question, briefly)

- **Not legal advice**, but for context: Odoo Community is LGPL-3.0. Custom modules that sit on top of CE without modifying core are common commercial practice; the license risk people worry about mostly concerns redistributing modified core or using Enterprise code without a license. So Posterra as it stands today is normal practice.
- A **standalone product removes all ambiguity** — no LGPL questions, no Enterprise upsell pressure, no coupling to Odoo's ORM/release cycle.
- It's also the better *product* call: care management is an operational app NPs live in all day (tasks, forms, timelines). It doesn't need ERP machinery. A lean purpose-built stack is easier to host, hire for, certify (SOC 2 / athenahealth Marketplace), and sell independently.
- Posterra stays exactly where it's strong: **the analytics layer**. EarlyRead CM produces operational data; Posterra dashboards consume it (Section 10).

## 2. Stack

| Layer | Choice | Why |
|---|---|---|
| Backend API | **Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + Pydantic** | Team already writes Python daily (Odoo). FastAPI gives OpenAPI docs for free, async where needed, no framework lock-in. |
| Database | **PostgreSQL 16** (own database, NOT the Odoo DB) | One `tenant_key` column everywhere (same string-tenant philosophy as `saas.app.app_key`). |
| Background worker | Same codebase, separate process. **Postgres-as-queue** (`SELECT … FOR UPDATE SKIP LOCKED` on the `event` table) + APScheduler for cron triggers | No Redis/Celery/Kafka to start. At 80K patients the event volume is thousands/day — Postgres handles this trivially. Swap later only if proven necessary. |
| Frontend | **React 18 + Vite** SPA | Same toolchain as the portal/designer. Reuse component patterns (grids, drawers, filter bars) where practical. React Query for server state. |
| Auth | **JWT (HS256)**, same env-first secret pattern as Posterra (`EARLYREAD_JWT_SECRET`). Tenant resolved from subdomain (`<tenant>.earlyread.<base-host>`) — same model as Posterra. | Enables SSO between Posterra and EarlyRead later by sharing issuer/secret. |
| Files | Azure Blob (or S3-compatible) for attachments; DB stores URI + metadata only | Never store PHI files in the DB. |
| Deploy | Docker containers (api, worker, web). Rides the planned AKS from Phase-4 infra, or a single VM to start. | |

**Explicitly avoided for v1:** microservices, Kafka/RabbitMQ, Redis, GraphQL, a separate rules-engine service, FHIR server. Boring, few moving parts, one maintainer can run it.

## 2b. Framework decisions per block ("what engine do we actually use?")

Two strategies exist in the market; we choose per-block composition (B):

- **Path A — healthcare substrate:** adopt **Medplum** (Apache-2.0, TypeScript, FHIR-native: Task, CarePlan, Questionnaire, Subscriptions, Bots, React components, self-hostable on Azure, HIPAA/SOC2-oriented). Buys ~60% of the platform; costs: TS backend (team is Python), FHIR data-model learning curve, automations written as TS "Bots". Worth a 1-week spike ONLY if FHIR-native storage becomes a sales requirement.
- **Path B — composed stack (CHOSEN):** own domain core on FastAPI/Postgres; proven libraries for mechanics; **buy the two commodity UIs** (form builder, calendar). Note: RoundingWell itself is a custom Backbone/Marionette app (its engineers co-maintained Marionette.js) — this product category is domain code + libraries, not an off-the-shelf engine.

| Block | Market options evaluated | Decision for EarlyRead | Why |
|---|---|---|---|
| **Workflows** | Temporal (MIT, durable execution, Python SDK — Netflix/Stripe-grade); Camunda 7 BPMN (**CE EOL Oct 14 2025 — repo archived, no security patches**); Camunda 8/Zeebe (source-available, NOT OSS, heavy); Flowable (Apache-2.0 but Java); SpiffWorkflow (Python BPMN, LGPL, niche); `transitions`/`python-statemachine` (MIT FSM libs); XState (MIT statecharts, TS) | **DB-defined playbooks (JSONB) executed by a thin interpreter built on `transitions` (MIT)**. Temporal reserved for Phase-4 integration pipelines (or Azure Durable Functions as managed alt) | Clinical playbooks are human-paced, admin-configurable state machines (days/weeks per step, ~10³ transitions/day) — the hard part is the domain model + config UI, not distributed execution. BPMN engines: wrong weight, Java, and the only true-OSS one (C7) just died. Temporal shines when steps are machine calls needing retries — that's Phase 4 ingestion, not the care pathway |
| **Actions** | No off-the-shelf "task engine" library exists — Jira/Asana/RoundingWell all own this. FHIR **Task** resource as schema blueprint; Camunda human tasks (only if BPMN) | **Own `action` table; state rules enforced by the same `transitions` FSM; field names aligned to FHIR Task** (status, owner, for/patient, basedOn/workflow) for painless future interop | It's ~2 tables + endpoints; adopting an engine for this imports complexity without removing work |
| **Worklists** | AG Grid (Community MIT; Enterprise paid — already used/known in Posterra); TanStack Table (headless, MIT); FullCalendar (core MIT, premium plugins paid); Schedule-X (MIT) | **AG Grid Community** for list views + **FullCalendar** for the Schedule/agenda view; React Query for data; claims via conditional UPDATE (`WHERE owner_user_id IS NULL`) | Reuse Posterra grid competence; worklists are queries + grid + calendar, deliberately not a "framework" |
| **Forms** | **SurveyJS** (renderer OSS/free; **Survey Creator commercial: one-time per-developer $579 Basic / $1,039 PRO, royalty-free, multi-tenant SaaS self-host allowed**); Form.io (renderer MIT, server OSL/commercial); react-jsonschema-form (Apache-2.0, no visual builder); JSONForms (MIT, minimal builder); FHIR Questionnaire + SDC prepopulation w/ LHC-Forms (NLM, OSS) | **SurveyJS: renderer + buy 1–2 Creator licenses.** Store our own `form_template.schema` as the SurveyJS JSON + a prefill-bindings overlay; keep answers JSONB mappable to FHIR QuestionnaireResponse later | ~$1–2K one-time kills the single biggest schedule risk (visual form builder = months). Conditional visibility, expressions, scoring, drag-drop builder all proven. FHIR SDC stays open as an export path, not a v1 dependency |
| **Automations** | Rule condition evaluators: GoRules ZEN engine (OSS rules engine, Rust core + Python bindings, decision-table React editor), json-logic (tiny, portable), Python `business-rules` (stale); Buses: Postgres outbox → Azure Service Bus; Event Grid; Runners: own SKIP LOCKED worker, Celery (BSD, needs Redis), Hatchet (MIT, Postgres-backed, young), Azure Durable Functions; iPaaS: n8n (Sustainable Use — internal ok, customer-facing embed needs commercial), Activepieces (open-core MIT), Windmill (AGPL core), Logic Apps (Azure-native, per-action cost) | **v1: own trigger→condition→action engine** — conditions as **json-logic** expressions (upgrade to GoRules ZEN if decision tables needed), Postgres outbox + SKIP LOCKED worker, APScheduler for cron. **Graduate the bus to Azure Service Bus** when volume/fan-out demands. Optionally run **n8n internally** for back-office ETL glue (never patient-facing) | Patient-facing automations need tenant isolation + audit ledger (`automation_run`) + PHI discipline — embedding a general iPaaS inside the product gets licensing- and compliance-awkward. The engine is small; the value is in OUR event vocabulary |
| **Dashboards** | (decided in §5/§10) | **Posterra** via ClickHouse sync; in-app counters only | Our differentiator already exists |
| **HL7/ADT ingest (Phase 4)** | **Mirth Connect — closed-source from 4.6 (Mar 2025); 4.5.2 = last OSS release**; Redox (SaaS, BAA — what RoundingWell uses); Azure Health Data Services (managed FHIR + MS OSS HL7v2→FHIR converter); HAPI FHIR (Java); Metriport (OSS) | **Redox or Azure Health Data Services** when we get there; do NOT build on OSS Mirth (dead end) | Verified license change; avoid adopting an engine that just lost its community |

## 2c. Azure service map

| Concern | Azure service | Notes |
|---|---|---|
| Compute (api, worker, web) | **Azure Container Apps** v1 → co-locate on the Phase-4 **AKS** cluster when it lands | ACA = managed K8s-lite, KEDA autoscale built in; don't run a raw VM |
| Database | **Azure Database for PostgreSQL Flexible Server** | PITR backups, private endpoint, `pg_cron` available |
| Events/queue | Postgres outbox v1 → **Azure Service Bus** (Standard) | **Event Grid** on Blob-created = trigger for "payer file landed" |
| Files/attachments + payer drops | **Azure Blob Storage** — enable the **native SFTP endpoint** | Payers/ACO conveners SFTP files straight into Blob; Event Grid fires ingest |
| Secrets | **Key Vault** → env injection | Same env-first pattern as Posterra (`EARLYREAD_JWT_SECRET`, DB creds) |
| Identity | Own JWT v1 (Posterra SSO parity) → **Entra External ID** when enterprise SSO is demanded | |
| SMS/voice/email outreach (Phase 3+) | **Azure Communication Services** | HIPAA-eligible under the Microsoft BAA (confirm in-scope list at signing) |
| Observability | **Application Insights + Azure Monitor** | Fixes the known APM gap from day 1; no PHI in traces |
| Edge/DNS | **Front Door** (already in use) | `*.earlyread.<base-host>` wildcard, same subdomain-tenant pattern |
| FHIR (only if needed) | **Azure Health Data Services** | Managed FHIR + HL7v2 converter; Phase 4+ decision |
| Compliance | Microsoft **BAA** covers in-scope services | Verify each service against the current in-scope list |

## 3. System shape

```
                     ┌──────────────────────────────────────────┐
   Snowflake roster  │  Ingest (Phase 4: athena API, ADT/Redox, │
   CSV/claims ─────▶ │  claims)  → writes patients + `event` rows│
                     └──────────────┬───────────────────────────┘
                                    ▼
   React SPA ──JWT──▶ FastAPI ──▶ PostgreSQL (tenant_key on every row)
   (worklists,            │            ▲
    patient 360,          │            │ outbox poll (SKIP LOCKED)
    forms, admin)         │        ┌───┴────────┐
                          │        │  Worker:   │──▶ start workflows,
                          │        │ Automations│    create actions,
                          │        │  + cron    │    notify, webhook
                          │        └────────────┘
                          ▼
              nightly/streaming sync ──▶ ClickHouse / Posterra schema source
                                         (Posterra = the Dashboards block)
```

One append-only **`event` table is the spine**: every meaningful thing (ADT received, form submitted, action completed, workflow state change) is an event. It serves three purposes at once — automation trigger queue (outbox), per-patient timeline, and the analytics feed to Posterra. This keeps the system honest: if it's not an event, it didn't happen.

## 4. Data model (core tables)

All tables carry `tenant_key TEXT NOT NULL`, `id` (uuid or bigint), `created_at/updated_at`. Names are indicative, not final DDL.

**People & access**
- `app_user` — email, name, role (`np`, `care_manager`, `pharmacist`, `admin`, `read_only`), active. `team` + `team_member` — pools like "NP Pool – East".
- `audit_log` — append-only: entity_type, entity_id, verb, actor_id, before/after JSONB, at. Written by a SQLAlchemy hook on every mutation. **Day-1 feature, not a retrofit** (PHI system).

**Patients**
- `patient` — mrn, `external_ids JSONB` (`{"athena_id": …, "aco_member_id": …, "ma_member_id": …, "src_mbr_id": …}`), name, dob, sex, phones JSONB, address, primary_payer, program flags JSONB, risk_score, assigned_team_id. **Identity is NOT resolved in EarlyRead** (decided 2026-07-11): the client's Snowflake warehouse already masters patient identity across MRN / ACO member ID / MA member ID and feeds the existing Patient 360. EarlyRead hydrates `patient` + `external_ids` from that mastered Snowflake record via a sync job (CSV as fallback); the dedup report remains only as a safety net. Edge case to confirm: mastered-roster refresh cadence — a TOC event for a patient not yet in the sync needs a provisional-patient path (Phase 4 concern while ADT is manual).
- `consent` — patient_id, type (`ccm`, `sms`, …), status, obtained_at, method. (Feeds CCM billing.)

**Workflows (Block 1)**
- `care_program` — key, name (e.g. `toc`, `diabetic_foot`, `hra`).
- `workflow_template` — program_id, **version**, status (`draft`/`published`), `definition JSONB` (states, steps, per-step auto-created actions with owner role + due offset, forms attached, transition rules). Publishing creates a new version; **in-flight instances pin their version** — editing a playbook never mutates patients mid-flight.
- `workflow_instance` — patient_id, template_id + template_version, current_state, status (`active`/`completed`/`cancelled`), started_by (`automation:<rule>` or `user:<id>`), context JSONB (e.g. discharge facility). State transitions emit events.

**Actions (Block 2)**
- `action` — patient_id (nullable for admin chores, normally set), workflow_instance_id + step_key (nullable — standalone tasks allowed), title, description, **owner_user_id OR owner_team_id** (team + null user = unclaimed pool task), due_at, priority, state (`open`/`in_progress`/`done`/`skipped`/`cancelled`), completed_by/at, form_template_id (nullable — "complete this form" tasks).
- `action_comment`; `attachment` (polymorphic entity_type/entity_id → blob URI).

**Worklists (Block 3)** — *no new tables.* Three canonical API queries over `action`:
- **Owned By me:** `owner_user_id = me AND state IN (open, in_progress)` ordered by due_at.
- **Shared pool:** `owner_team_id IN my_teams AND owner_user_id IS NULL` + a **Claim** endpoint (atomic `UPDATE … WHERE owner_user_id IS NULL` — two NPs can't claim the same task).
- **Schedule:** same rows grouped into Overdue / Today / This Week / Later.
- `saved_worklist` (name + filters JSONB per user/role) — phase 2 nicety.

**Forms (Block 4)**
- `form_template` — key, name, **version**, `schema JSONB`: fields (key, label, type: text/number/select/multiselect/date/boolean/scale/section), required, `visible_if` (simple condition expressions), **`prefill` bindings** (`"patient.dob"`, `"last_submission.med_review.med_list"`, `"context.discharge_facility"`), scoring rules (for HRA).
- `form_submission` — patient_id, template_id + version, workflow_instance_id / action_id (nullable), answers JSONB, **prefill_snapshot JSONB** (what the NP saw pre-filled — audit requirement), score, submitted_by/at, status (`draft`/`final`), amends_id (corrections = new immutable row).

**Automations (Block 5)**
- `automation_rule` — name, trigger_type (`adt.discharge`, `form.submitted`, `action.completed`, `workflow.state_changed`, `patient.created`, `file.imported`, `schedule.cron`), `conditions JSONB` (field comparisons against event payload + patient attributes), `actions JSONB` (ordered list: `start_workflow`, `create_action`, `notify`, `set_patient_flag`, `webhook`), active, run_order.
- `event` — type, patient_id (nullable), payload JSONB, occurred_at, source, processed_at. **Append-only spine** (outbox + timeline + analytics feed).
- `automation_run` — rule_id, event_id, status, error, at. **Unique (rule_id, event_id)** = idempotency; a crashed worker can't double-fire a rule. This ledger is also the debugging UI ("why did/didn't this rule fire?").

**CCM revenue capture (Block 6.5 — small table, pays for the build)**
- `time_entry` — patient_id, user_id, action_id (nullable), minutes, category, note, at. UI: auto-start timer on action open, editable on complete. Monthly rollup view → CCM billing report (per patient: total minutes, consent on file, one-biller-per-month flag).

## 4b. Care-plan layer — inspired by Microsoft Care Management, aligned to FHIR (added 2026-07-11)

**Decision: adopt the shape, not the product.** Microsoft Cloud for Healthcare's Care Management (Dynamics 365/Dataverse) is ruled out as a platform for the same reason Odoo was (§1): per-seat licensing stacked on Dynamics base licenses (RoundingWell-tier annual spend at 100+ users — verify current pricing) and it can't become OUR sellable product. But its data model is the industry-standard rendering of FHIR's care-coordination resources — and it independently confirms the exact gap Codex's review surfaced (care plans as first-class). Three sources now converge on the same missing layer: Codex, FHIR, Microsoft.

| Microsoft concept | EarlyRead entity | FHIR analog | Notes |
|---|---|---|---|
| Care teams | `care_team` (patient_id) + `care_team_member` (user_id, role_on_team, period) | CareTeam | Distinct from worklist pools: this is WHO clinically owns the patient. Drives "my patients" scoping and timeline attribution |
| Care plans | `care_plan` (patient_id, template_id+version, status `draft/active/completed/revoked`, period, focus conditions JSONB, reviewed_by/at) | CarePlan | The physician-review step = a status transition with audit |
| Goals | `care_plan_goal` (care_plan_id, description, measure/target JSONB, due, status `proposed/active/achieved/abandoned`) | Goal | Progress notes ride the `event` spine |
| Activities | existing `action.care_plan_goal_id` (nullable FK) | CarePlan.activity → Task | **Activities ARE actions** — no second task engine; a goal's activities appear in the same worklists/timeline |
| Care-plan templates | `care_plan_template` (versioned JSONB: goals + activity templates per condition, e.g. "High-risk diabetic foot plan") | PlanDefinition | Same versioned-template pattern as workflow/form templates |
| Patient clinical timelines | existing `event` spine; later merge clinical events (encounters, dx from Snowflake/athena) into the same stream | — | Microsoft validates the unified-timeline UX we already designed |
| Dynamics security roles | `role_permission` matrix (role × entity × operation) + record scope (`own patients / team / all`) | — | Table-driven RBAC, editable without deploys |

**Phase placement:** `care_plan` + goals + one generic template land in **MVP-1** (enrollment must end in an approved care plan); condition-specific templates + goal progress tracking in **MVP-2** (wound program); `care_team` thin in MVP-1, role-matured in MVP-2; RBAC matrix in Phase 0.

## 5. The six blocks → implementation summary

| Block | Implementation | Admin configures via |
|---|---|---|
| Workflows | `workflow_template` (versioned JSONB definition) + `workflow_instance` state machine | Template editor (JSON editor v1 → visual builder later, same evolution as your widget Builder) |
| Actions | `action` + comments + attachments + audit | Created by workflow steps, automations, or manually |
| Worklists | Three canonical queries + claim semantics + saved views | Zero config for the 3 core views |
| Forms | `form_template` (versioned schema + prefill bindings) + immutable submissions | Form builder (field list UI — reuse Builder UX patterns) |
| Automations | `automation_rule` + `event` outbox + worker + `automation_run` ledger | Rule builder: trigger picker → condition rows → action list |
| Dashboards | **Posterra.** Sync `event`/`action`/`form_submission`/`time_entry` to ClickHouse (or expose EarlyRead PG as a `dashboard.connection`); build program dashboards with the existing Builder. In-app: only small counters (My open tasks, overdue). | Existing Posterra Builder |

Everything above is **config-driven** (templates, rules, bindings are DB records interpreted at runtime) — same no-hardcoding philosophy as Posterra. A new clinical program = new records, zero code.

## 6. One-patient walkthrough (how the blocks click together)

Maria, 67, diabetic, ACO REACH-attributed.

1. **Wed 06:10** — Nightly ADT file lands → ingest writes `event(type=adt.discharge, patient=Maria, payload={facility: "St. Mary's", dx: …})`.
2. **06:11** — Worker picks up the event. Rule **"TOC on discharge"** (conditions: payer = ACO REACH, program enrolled) matches → `start_workflow(toc v3)` → instance created in state *Outreach*; step config auto-creates `action("48-hour post-discharge call", owner_team=NP Pool, due=Fri 18:00)`. `automation_run` logged.
3. **Thu 09:00** — NP Dana opens **Schedule worklist** → sees the call under *Today* → **claims** it (atomic — no double-claim).
4. Dana calls Maria; opens the attached **Post-Discharge Assessment form** — facility pre-filled from the event context, med list pre-filled from Maria's last med-review submission. She marks "confused about insulin dosing."
5. **On final submit** → `event(form.submitted)` → rule "Med-risk flag" matches the answer → creates `action("Medication reconciliation", owner_role=pharmacist, due=+2d)` and transitions the workflow to *Med Review*. The action screen timer logged **9 minutes** to `time_entry`.
6. **Maria's Patient 360 timeline** now shows: discharge event → workflow started → call completed (Dana, 9 min) → form (score 14) → med-rec task open. Anyone covering for Dana sees the whole story.
7. **Month-end** — CCM report: Maria 22 min, consent ✓, eligible biller = supervising NP → billing export.
8. **Posterra dashboard** (existing Builder): TOC completion within 48h by NP, calls per discharge, CCM minutes captured vs billed — per program, per month.

## 7. API surface (v1 sketch)

```
POST /auth/token                          GET  /patients?search=&filters
GET  /patients/{id}                       GET  /patients/{id}/timeline
GET  /worklists/owned|shared|schedule     POST /actions  PATCH /actions/{id}
POST /actions/{id}/claim|complete|skip    POST /actions/{id}/comments
GET/POST /workflow-templates (+ /publish) POST /workflow-instances (+ /transition)
GET/POST /form-templates                  GET/POST /form-submissions
GET/POST /automation-rules                GET  /automation-runs?rule_id=&event_id=
POST /ingest/roster (CSV)                 POST /events (internal/webhook)
GET  /reports/ccm?month=                  GET  /admin/users|teams|programs
```

## 8. Screens (React SPA)

1. **Worklist home** — tabs: My Work / Team Pool / Schedule; filters (program, priority, patient search); claim/complete inline. *The NP's all-day screen — optimize this above everything.*
2. **Patient workspace (thin, operational)** — thin header (demographics, payer, consent badges, care team) + operational panels only: timeline (from `event`), active workflows with step progress, open actions, forms history, outreach history. **Deliberately does NOT duplicate the existing Posterra Patient 360 dashboard** (Member 360 drawer / patient analytics already built and in client use) — it deep-links or embeds it for claims, utilization, risk, and gap history. Identity join requirement: `patient.external_ids` carries the dashboard's member key (e.g. `src_mbr_id`) from day 1 so the two views always resolve to the same person.
3. **Action drawer** — details, timer, comments, attachments, linked form, complete/skip.
4. **Form filler** — prefilled, conditional visibility, draft/final.
5. **Admin studio** — program list, workflow template editor, form builder, automation rule builder, users/teams, automation-run log viewer.
6. **Mini stats strip** — counts only; real analytics live in Posterra.

## 9. Compliance posture (day 1, not later)

- `audit_log` on every mutation; `event` append-only; form submissions immutable.
- RBAC enforced server-side per endpoint; tenant isolation enforced in a query layer (every query filtered by `tenant_key` — mirror Posterra's discipline).
- No PHI in application logs. TLS everywhere. Encrypted storage (Azure-managed).
- BAA-capable hosting (Azure covers this). SOC 2 is a later, paid exercise — but the audit/access patterns above are what auditors check.

## 10. Posterra integration

- **Analytics:** simplest v1 = nightly job pushing `event`, `action`, `form_submission`, `time_entry` (flattened) into ClickHouse `gold.earlyread_*` tables → register as schema sources → build dashboards with the existing Builder. (Alternative: a `PostgresRemoteExecutor` for `dashboard.connection` → EarlyRead PG directly; CH route is less new code in Posterra.)
- **SSO:** shared JWT issuer/secret so a Posterra user deep-links into EarlyRead (and vice versa: "Open in EarlyRead" from a Posterra patient row).
- **Patient 360 division of labor (decided 2026-07-11):** the existing Posterra Patient 360 (analytics: claims history, utilization, risk, star/care gaps — batch data, read-only) is the **"knowing" view** and is NOT rebuilt in EarlyRead. EarlyRead's patient workspace (tasks, workflows, forms, outreach, consent, time — live, transactional) is the **"doing" view**. Connect them: (a) "Open in EarlyRead" from Posterra patient rows via URL convention + SSO deep-link; (b) "View analytics" from the EarlyRead patient header → Posterra Patient 360 filtered to that member (optionally iframe-embedded); (c) EarlyRead events → ClickHouse lets the Posterra Patient 360 ADD care-management widgets (enrollment status, last outreach, open task count) with zero new plumbing.

## 11. Phased build

| Phase | Weeks (1 senior dev + Claude Code) | Delivers | Demo moment |
|---|---|---|---|
| 0 — Foundation | 1 | Repo, Docker, auth/JWT, tenancy, `app_user`/`team`, `patient` hydrated via **Snowflake mastered-roster sync** (CSV fallback), audit hook | Log in, see the real mastered patient list |
| 1 — Actions + Worklists + Patient 360 | 3–4 | `action` CRUD, claim semantics, 3 worklists, comments/attachments, Patient 360 v1 + timeline (manual events) | **NP runs a real day in it — spreadsheets retired** |
| 2 — Forms + Workflows | 4–5 | Form templates + prefill + submissions; workflow templates/instances; step→action generation; admin editors (JSON-first) | Post-discharge playbook end-to-end, manually triggered |
| 3 — Automations + CCM | 3–4 | Event worker, rule builder, `automation_run` ledger, notifications, `time_entry` + CCM monthly report | The Maria walkthrough, untouched by hands |
| 4 — Integrations | ongoing | athena API pull (patients/appointments/problems), ADT via Redox or SFTP, claims/roster feeds, ClickHouse sync → Posterra dashboards; athenahealth **Marketplace certification track (incl. write-back — the wedge RoundingWell lacks)** | Live hospital-discharge → task, same-day |

Credible RoundingWell-core parity: **~4 months**. First demo: **~5–6 weeks**.

## 11b. AI agent roadmap — assistive-first, human-in-the-loop (added 2026-07-11)

**Foundation:** reuse the Posterra AI plumbing (Claude via Azure AI Foundry, env-first keys — same pattern as the AI SQL Assistant). **Architectural rule: an agent is just another API client.** It calls the same FastAPI endpoints under a scoped token acting on behalf of a user (`audit_log.actor = agent:<name>`, `on_behalf_of = <user>`), so tenant isolation, RBAC, and audit come free. Agents **draft**, humans **approve** — no autonomous clinical action. The `event` timeline is every agent's context feed (another payoff of the spine).

| Wave | Agent | What it does | Guardrail |
|---|---|---|---|
| **AI-0** (ships with MVP-1) | Pre-call brief | Summarizes timeline + last forms + open gaps into a 5-bullet brief inside the action drawer (kills the 10-min chart review before every call) | Read-only |
| **AI-0** | Post-call scribe | NP's rough notes → structured disposition + athena-ready note text (paste until write-back exists) + suggested next actions | NP edits/approves; nothing auto-sent |
| **AI-1** (MVP-2) | Care-plan drafter | HRA answers + conditions + `care_plan_template` → draft goals/activities | Approval = the `care_plan` review transition (§4b) |
| **AI-1** | Admin authoring copilot | Natural language → draft workflow/form/rule JSON (same pattern as Posterra's AI SQL assistant, different target schema) | Admin review + JSON-schema validation before save |
| **AI-2** (MVP-3) | Worklist prioritizer | Ranks today's tasks (TCM clocks, SLA proximity, risk signals) and explains why | Advisory ordering only |
| **AI-2** | Billing-readiness checker | Audits TCM/CCM criteria per patient-month ("contact ✓ day 1, visit ✓ day 6, med rec ✗ → 99496 not yet billable") | Flags only; never auto-bills |
| **AI-3** (Phase 4+) | Patient SMS outreach agent | Reminders, pre-visit form collection via Azure Communication Services; conversational follow-up | Consent + opt-out flags, clinical-keyword escalation to a human; voice agents much later |

**Explicitly NOT doing:** HCC coding suggestions (OIG-sensitive — needs a compliance owner first), AI clinical triage/risk scoring (stays rule-based and clinician-owned), agents writing to athena unattended. Microsoft analogs (Copilot Studio agents, Healthcare agent service) exist but tie to Dynamics/Bot Framework; Foundry + Claude on our own API gives the same capability with full control. Measure every agent: time saved per task, acceptance rate of drafts, edit distance — kill agents nobody accepts.

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Builder rabbit hole** — visual workflow/form/rule builders can eat months | v1 admin editors are structured JSON forms with validation + preview; visual builders phase in later (exactly how Posterra's Builder evolved) |
| **Automation correctness** (double-fires, lost events, ordering) | Outbox pattern; `SKIP LOCKED`; unique (rule_id, event_id); `automation_run` ledger surfaced in admin UI |
| **Template edits breaking in-flight patients** | Versioned templates; instances pin version; publish = new version |
| **Patient identity mismatches** (MRN vs ACO member ID vs MA ID) | `external_ids JSONB` + dedup report + manual merge tool; defer real MPI |
| **PHI/compliance gap kills a deal later** | Audit log + RBAC + tenant filter discipline from Phase 0; no PHI in logs |
| **Double documentation** (same complaint RoundingWell gets) | Near-term: honest positioning + fast forms. Real fix: athena write-back via Marketplace app (Phase 4) — the differentiator |
| **Scope: rebuilding dashboards in-app** | Hard rule: analytics live in Posterra; EarlyRead shows counters only |

## 13. Open decisions (need Nishant's call)

1. **Repo location** — recommend a **separate repo** (`earlyread-care`) to keep the product (and its story) fully independent of the Odoo tree; a top-level folder in Odoo_Dev works for week 1 if faster.
2. **Backend confirm** — FastAPI/Postgres as above, or do you want Node/NestJS? (Everything in §4–7 survives either; effort estimates assume Python.)
3. **SSO now or later** — share the Posterra JWT secret/issuer from day 1 (cheap now, fiddly later)?
4. **Hosting** — ride Phase-4 AKS plan, or standalone Azure VM/App Service first?
5. **Product naming** — "EarlyRead Care Management" as the suite name; tenant subdomain scheme `<tenant>.earlyread.<host>`?
6. **Analytics landing zone** — EarlyRead operational events sync to ClickHouse (Posterra-native, current §10 plan), to the client's **Snowflake** (their warehouse owns all data — and Patient 360 reads from it), or both? Related facts to confirm: how Patient 360 reads Snowflake today (direct connection vs ETL), and the mastered-roster refresh cadence.
