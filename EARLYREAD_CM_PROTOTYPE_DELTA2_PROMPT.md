# PROMPT - EarlyRead Care Management prototype: DELTA 2 (Template Studio + correctness fixes + data provenance)

You are **extending an existing prototype** of **EarlyRead Care Management** - a configurable specialty care-operations platform (fictional org: Summit Foot & Ankle Partners; synthetic data only; no real client or patient names). Land ALL new work in the **main interactive file** (the one containing Workflow Registry, Start Workflow wizard, reassignment, and the audit route) - not the static print/export copy.

**Do not rebuild or restyle existing screens.** Reuse their components, seed data, and visual language: Worklist | Enrollment Funnel | Patients | Patient Workspace | Referrals | Clinical Approval Queue | Supervisor Console (Work Allocation) | Activity Report | Admin Studio | Workflow Registry + Instance Detail | Start Workflow wizard | Audit route.

**Core concept guardrail:** a **workflow template** is an immutable, versioned blueprint; a **workflow instance** is one run of it for one patient. This delta adds the ability to *author templates*. **The Template Studio's published output MUST be startable by the existing Start Workflow wizard and produce identical runtime records** (same instance, task, routing, due-date, assignment-history, and audit shapes). If a template built in the Studio can't be started by the wizard, the delta has failed.

**Demo spine (protect these above all else if budget is tight):** (1) the 8 fixes in section 1; (2) Create Template -> validate -> simulate -> approve -> publish; (3) start an instance of that newly-created template via the existing wizard. Advanced step features (conditional branches, version compare) are secondary.

---

## 1. Correctness fixes (highest priority - the render exposed these)

1. **Start-workflow-without-a-patient bug.** The "+ Start workflow" button in the Workflow Registry opens the wizard with no patient selected, but the wizard has no patient step. **Add a patient search/select as step 0 whenever the wizard is launched without a patient context** (Registry, or any population-level entry point); when launched from a Patient Workspace, prefill and skip step 0. Supervisors start work from population queues, so keep the Registry button - just give it the patient picker.
2. **Enforce full eligibility, not just role + discipline.** Claiming/routing/assignment eligibility must check **application role AND clinical discipline AND team membership AND org/location/program scope AND active credential** (per the task's credential policy). Ineligible reasons must name the *actual failing check*, e.g. "Not a member of NP Team East", "Outside TN program scope", "Pharmacist license expired 2026-05" - not a generic "ineligible".
3. **Assignment events must not enter the clinical timeline.** Reassign / release / claim update **assignment history + audit only**. They must NOT post to the patient's clinical timeline (which is for clinical events: discharge, assessment, care-plan approval, referral). Fix wherever the current build routes them into the timeline.
4. **Release-to-pool scope.** A **task owner may release only to the task's configured default pool.** Only a **Supervisor** may move a task to a *different* eligible pool or across pools. Remove the multi-pool picker from the owner's release action; keep it for Supervisors.
5. **Due-date override in the Start Workflow wizard.** Add the same Supervisor-gated due-date override that exists in the task drawer to the wizard's per-task routing step: shows calculated date, requires new date + reason, writes audit, keeps original SLA visible. Non-supervisors see it read-only/disabled.
6. **Duplicate-resolution uses `cancelled`, not "not performed".** In the duplicate-episode reconciliation path, the discarded workflow's open tasks close with execution state **`cancelled`** ("Cancelled - duplicate episode merged"). `not_performed` stays reserved for a human Skip/Unable-to-perform with reason + follow-up.
7. **Bulk assignment must surface skips.** The bulk assign/release/escalate confirmation must state eligibility counts before applying, e.g. **"7 selected - 5 eligible, 2 will be skipped"**, and list which tasks skip and why. No silent skipping.
8. **Audit route isolation (still leaking).** The Audit Log must NOT appear inside Admin Studio for Sam (`ConfigurationAuthor`) or Dr. Chen (`ClinicalContentApprover`). Audit is reachable **only** by Avery (`Auditor`) on the dedicated read-only Audit route. Remove the Audit tab from Admin Studio's shell entirely; personas without the Auditor capability have no audit access.

## 2. Template Catalog - NEW (Admin Studio -> Templates)

A catalog of all workflow templates (not just TOC). Each row: name, code, workflow type, program, latest published version, draft-in-progress indicator, status (draft / published / retired), running-instance count, last modified. Actions, permission-gated to `ConfigurationAuthor` for authoring and `ClinicalContentApprover` for approval:
- **Create Template** (blank) -> opens the builder in section 3.
- **Clone** any template (any version) into a new draft.
- **Open** -> version list with the existing clone-to-draft / edit / validate / simulate / submit / approve / publish flow (reuse it).
- **Compare versions** (secondary) -> side-by-side field-level diff of two selected versions.
- **Retire / supersede** -> mark retired: blocks new starts, keeps running instances on their pinned version, records who/when/why.

## 3. Create / Edit Template - NEW (the studio)

A structured, form-based builder (NOT a drag-drop visual graph IDE - that is a later production feature). Same draft->publish governance and version-pinning as the existing TOC flow. Steps:

1. **Identity** - name, code, description, program, **workflow type** (episode / enrollment / transition / longitudinal / referral), applicable patient populations + payer types (Original Medicare / MA / ACO-attributed / Medicaid).
2. **Entry & eligibility** - manual vs automated start; **trigger** (manual / ADT / claim / appointment / scheduled - only manual actually fires in the prototype, others are configured + labeled "simulated"); eligibility rule list (field + operator + value across payer / program / diagnosis / facility / risk / attribution); exclusion rules; **duplicate key** (per workflow type, matching the wizard's keys) + cooldown period.
3. **Steps** - an ordered, editable list. Each step: **type** (task / form / outreach / care-plan activity / referral / approval / wait), name, **dependency** ("starts after step N complete"), optional **conditional** ("on outcome = X -> go to step N / skip"), completion + cancellation behavior. Keep it a structured list with inline configuration, not a canvas.
4. **Routing** (per step) - required application role, clinical discipline, team or default pool, **credential policy**, and fallback/assignment rule. This is the routing the Start Workflow wizard will prefill.
5. **Timing** (per step) - due-date calculation (offset + business calendar + timezone), escalation thresholds, pause/exception behavior.
6. **Validation & simulation** - validation detects unreachable steps, missing routing, circular dependencies, impossible SLAs, and no start/approval path; **simulate** runs the draft against a synthetic patient (reuse the existing simulate modal; allow testing against Robert Ellis).
7. **Governance** - submit for clinical approval; **Dr. Chen (not Sam) approves and publishes an immutable version**; retire/supersede older versions; **running instances stay pinned to their original version**.

## 4. Data Sources & Provenance - NEW (read-only, simulated)

A screen making the system-of-record boundaries explicit. No real integration - everything labeled simulated; no real EHR calls.
- **Source legend:** **athenahealth (simulated)** = clinical system of record (problems, meds, allergies, encounters, discharge/ADT) - read into EarlyRead, plus planned write-back; **Posterra Patient 360** = analytics / claims / risk / attribution - read-only; **EarlyRead** = operational system of record (workflows, tasks, outreach, consent, assignments) - authoritative here.
- **Per-patient provenance table** (on Patient Workspace + this screen): each clinical/data element -> source, last-refreshed, freshness chip (fresh / aging / stale), direction (read-only vs write-back), sync status.
- **System integration status panel:** simulated feeds (ADT, roster, claims, appointments) each with last-run, status, record count - all clearly synthetic.
- **Write-back queue:** items EarlyRead would push to athenahealth (e.g., visit-summary PDF, care-plan update) with status chips ("Not yet integrated" / "Simulated - queued"). Never claim a real write occurred.

## 5. Acceptance - loop closure, permissions, persistence, regression

- **Loop closure (the headline test):** As **Sam** -> Create Template -> "Wound Surveillance Episode" (longitudinal) -> add ~3 steps (a monitoring task -> NP; a foot-check form -> NP; a vascular referral) with routing + timing -> validate -> simulate against Robert Ellis -> submit. As **Dr. Chen** -> approve + publish v1.0. As **Priya** -> Start Workflow -> the new "Wound Surveillance Episode" appears in the published-template list -> start it for a patient -> **the wizard shows exactly the steps/routing Sam configured** -> instance created in the Registry, pinned to v1.0, with identical runtime records to any other started workflow.
- **Permissions:** Sam can author but not approve/publish; only Dr. Chen approves; a published version cannot be edited (only cloned to a new draft); retired templates cannot be started but running instances survive; Avery reaches Audit and nothing else; Sam/Dr. Chen have no Audit access.
- **Fixes verified:** Registry Start-workflow now asks for a patient; ineligible pickers name the real failing check; reassignment does not touch the clinical timeline; owners release only to the default pool; wizard has a Supervisor-gated due-date override; duplicate resolution shows `cancelled`; bulk assign shows the eligible/skip counts.
- **Persistence:** create + publish a template, refresh -> it persists and is startable; **Reset Demo Data** restores the canonical post-delta seed (incl. Robert Ellis, the seven personas, existing templates + this delta's additions) and removes runtime mutations.
- **Regression:** every pre-existing screen and the delta-1 flows still work and are visually unchanged except the additions above.

## Binding rules

Synthetic data only; job title / discipline / team / payer / location are never application roles; published template versions are immutable; running instances never silently change version; activity minutes are operational documentation, never labeled billable; generic "EHR" wording except the "athenahealth - simulated" tag; strong contrast, visible focus rings, keyboard-friendly; ASCII-safe punctuation.

---

## Deferred - do NOT build in this delta (roadmap only)
1. **Care-plan template builder** (reusable problems/goals/interventions/measures/review-frequency) - build the workflow Template Studio so this same builder pattern extends to care plans later; do not build it now.
2. Innovaccer-style layers: AI (summaries/ambient documentation/suggested plans), advanced analytics, referral intelligence (triage/matching/leakage), automated patient engagement, real EHR write-back. These come AFTER the generic template model is proven - do not add them on top of a non-configurable foundation.
3. Production concerns (real DB/API, workflow engine, Entra enforcement, concurrency, immutable audit store) belong in the production spec, not the prototype.
