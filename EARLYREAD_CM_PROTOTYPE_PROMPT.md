# PROMPT — Build the EarlyRead Care Management UI Prototype

> Copy everything below this line into Claude (claude.ai with artifacts, or Claude Code) to generate the prototype.

---

You are building a **high-fidelity, clickable UI prototype** of **EarlyRead Care Management** — a configurable care-operations platform for risk-bearing specialty medical groups (value-based care). It turns patient eligibility, clinical events, and care-program rules into coordinated outreach, assessments, care plans, tasks, referrals, and follow-up. Its primary daily users are **care navigators and nurse practitioners (NPs)**; supervisors and clinical administrators use it for oversight and configuration.

This is a **synthetic-data product prototype** — not production software. It must tell the product story end-to-end in a demo.

## Hard rules

1. **Synthetic data only.** Invent all patients, clinicians, and organizations. Obviously fictional names (e.g., patient "Maria Delgado (TEST)", org "**Summit Foot & Ankle Partners**" — a fictional multi-state podiatry group). Never use real patient data or real client/company names.
2. **No backend.** Single-page React app, all state client-side (in-memory store + seeded data). Interactions mutate the store so the demo feels alive (completing a task updates worklists, timeline, and metrics).
3. **Desktop-first, responsive enough for a tablet.** Clean, calm, clinical aesthetic — information-dense but never cluttered. Accessible: strong contrast, visible focus rings, keyboard-friendly menus, WCAG 2.2 AA spirit.
4. **Every screen shows patient context clearly** (name, age, program badges) and **data freshness** where external data appears ("From EHR · updated 2d ago").
5. If the tool supports only one file, build it as **one React component with Tailwind classes**; otherwise a small Vite React app is fine.

## Product model & configurability requirements

This prototype represents a **configurable multi-tenant platform, not a podiatry-specific hardcoded application**. Podiatry is the seeded demonstration vertical — nothing podiatry-specific may be hardwired into components, statuses, or routing.

Keep these concepts visibly separate (they are different objects, never merged):
- **Program enrollment** — the patient's participation in a program
- **Workflow instance** — the operational process running for that patient
- **Care plan** — patient-specific goals and interventions
- **Action/task** — one unit of work
- **Referral** — a closed-loop service request
- **Follow-up** — a future checkpoint represented by an action
- **Assignment** — the person or team currently responsible for work
- **Template/version** — the configuration an instance was created from

**Roles:** the persona switcher simulates Microsoft Entra **application roles**. Show BOTH the application role and the clinical discipline/capability on each persona (e.g., "ClinicalPractitioner · Pharmacist"). Job title, discipline, team, payer, and location are NOT application roles — never present them as one.

**Make ONE workflow template genuinely configurable** (the others may be static): clone published version to draft → edit steps and action definitions → configure team/capability+discipline routing → configure due-date and follow-up rules → link a form or referral → validate → **simulate with a synthetic patient** (a lightweight modal walkthrough is acceptable) → submit for clinical review → **approve and publish under a different authorized persona** → show immutable published version history → existing workflow instances visibly remain on their original version.

**State:** central store + localStorage persistence, with a "Reset demo data" control. Every major state change must update the related worklist, patient timeline, workflow progress, program journey/funnel, metrics, and audit history together.

**Semantics:** consent recording is separate from outreach disposition. Form finalization makes the submitted version read-only; corrections create an amendment. Skipping work is recorded as "Not performed" with a required reason and a follow-up decision. **Activity minutes are operational documentation only — never automatically classified as billable.** Use generic "EHR" wording everywhere except where explicitly demonstrating an "athenahealth — simulated" integration; no real EHR calls occur.

## The fictional world (seed data)

- **Org:** Summit Foot & Ankle Partners — podiatry group in a value-based care program ("Summit Advantage") for diabetic patients at risk of foot ulcers and amputation. ~80,000 patients total; seed **~16 patients** across states TN, GA, FL.
- **Users (persona switcher in the top bar — no real login; each shows app role · discipline):**
  - **Dana Reyes** — `CareCoordinator` (navigator; outreach, enrollment)
  - **Priya Shah, NP** — `ClinicalPractitioner` · Nurse Practitioner (assessments, care plans)
  - **Marcus Webb, PharmD** — `ClinicalPractitioner` · Pharmacist (med reconciliation)
  - **Elena Volkov** — `Supervisor` (workload, exceptions, oversight)
  - **Sam Ortiz** — `ConfigurationAuthor` (templates, rules, audit)
  - **Dr. Alice Chen, DPM** — `ClinicalContentApprover` · Podiatrist (approves templates and clinical content — deliberately a different persona than the author)
- **Programs:** "Summit Advantage Enrollment", "High-Risk Diabetic Foot Program", "Transitions of Care".
- Seed patients spread across the enrollment funnel stages, plus: 2 with active wound-program workflows, 1 with a fresh hospital-discharge event (TOC), 1 with an expired-consent edge case, 1 pair flagged as a possible duplicate episode (for the supervisor exception demo).

## Core objects the UI works with (simplified)

- **Patient:** demographics, payer chips (Original Medicare / MA / ACO-attributed / Medicaid), program enrollments (status, dates), consents (**CCM consent and SMS consent are separate badges**, with policy version + date), risk level, care team (internal + external members with roles), assigned navigator/NP.
- **Workflow instance:** template name + version, current step, status (`active / waiting / paused / reconciliation_required / completed / cancelled`), progress indicator, subject ("Enrollment", "Episode: discharge 07/08", "Referral #R-114").
- **Action (task):** title, patient, owner (person) OR team pool (unclaimed), due date/time **with timezone label**, priority, routing chips (capability + discipline, e.g. "Clinical Practitioner · Pharmacist"), and **four small status tracks**: execution (open/in progress/performed/not performed), documentation (not started/draft/documented), compliance (n/a/review required/cleared), billing (n/a/not ready/ready). Comments + attachments.
- **Care plan:** status (draft/active), goals (description, baseline → target, due, status), activities linked to goals (each may spawn a task or referral), approved-by line, review-due date.
- **Referral:** to (specialty/org), status vocabulary `draft → ready_to_send → sent → acknowledged → scheduled → completed → result_received → closed` (+ `unable_to_complete`), days-open counter, closed-loop indicator.
- **Outreach attempt:** channel (phone), disposition (reached / no answer / bad number / declined / call back), consent-checked flag, note, next-attempt schedule. **Attempt 2 of 3** style counters.
- **Timeline event:** typed, human-readable entries (eligibility received, outreach attempt, consent recorded, form completed, care plan approved, referral sent, discharge alert received…), each with source + timestamp. Never raw JSON.
- **Form (assessment):** sections, required fields, some pre-filled values marked with a small "prefilled" tag, conditional fields, a score result (e.g., risk score), save-draft vs finalize.

## Screens (build in this order)

### P0 — the demo core
1. **Worklist Home** — three tabs: **My Work** (owned by me, sorted by due), **Team Pool** (unclaimed; "Claim" button moves it to My Work instantly), **Schedule** (grouped: Overdue / Today / This Week / Later). Filters: program, priority, patient search. Each row: patient, task, due (with "2 business days" chip on TOC contact tasks), routing chips, status dots.
2. **Patient Workspace** — header (name, age, payer chips, program badges, consent badges, risk chip, care team avatars) + panels: **Timeline** (newest first), **Open tasks**, **Active workflows** (with step progress), **Care plan** (goals with baseline→target bars), **Referrals**, **Forms history**, **External clinical snapshot** (conditions, meds, allergies — each row with "From EHR · updated Xd ago" freshness tag, read-only), link out: "Analytics 360 ↗" (dead link is fine).
3. **Action Drawer** (slide-over from any task): details, timer chip ("12:34 elapsed"), outreach disposition buttons when it's a call task, linked form launch, comments, complete/skip (skip requires a reason), and an **assignment block**: current owner, **Reassign** (eligibility-filtered people picker) and **Release to pool** — both require a reason — plus a visible **assignment history** ("Pool → Dana (claimed) → Marcus (reassigned by Elena: coverage)"). Completing a **documentation-required** task walks through: document → finalize → status tracks update.
4. **Form Filler** — the "Comprehensive Foot Risk Assessment (HRA)": ~4 sections, prefilled demographics, conditional wound questions, score computed at finalize, draft vs final.
5. **Enrollment Funnel Board** — kanban: Eligible → Outreach → Consented → Assessment Scheduled → Assessment Done → Care Plan Approved → Active. Cards move as demo actions complete; column counts + conversion strip on top.

### P1 — oversight & story depth
6. **Start Workflow & Assign** — the manual workflow-creation flow. Entry points: a **"+ Start workflow" button on the Patient Workspace header** and a row action on the Patients roster. A 4-step modal/stepper:
   - **Choose program & template** — published templates only, each showing name + version + one-line description (e.g., "High-Risk Diabetic Foot Program · v3").
   - **Subject & duplicate check** — the subject is derived automatically (enrollment / episode / referral / patient + a **purpose picked from a controlled list**, never free text). If an open workflow already exists for the same subject, show a blocking notice: *"An open Transitions of Care workflow already exists for this episode"* with an **Open existing** button — starting a duplicate is impossible.
   - **Assignment** — radio choice: **assign to team pool** (dropdown of teams) OR **assign to an individual**. The people picker is filtered by the template's routing requirements and shows eligibility: eligible people selectable with `AppRole · Discipline` chips; ineligible people visible but disabled with the reason ("License expired", "Wrong discipline — requires Pharmacist", "Outside program scope"). Optional first-task due-date override (shows the business-day calculation hint).
   - **Confirm** — summary card; on create: workflow instance appears on the patient with its pinned template version, first tasks land in the chosen worklist, timeline + audit record the start ("Started by Priya Shah · template v3 · assigned to NP Team East").
7. **Supervisor Console** (Elena): team workload bars, unassigned/overdue counts, SLA breaches, **bulk reassign** (select several tasks → move to person/pool with a required reason + confirmation), **Exceptions queue** — include one "Duplicate episode — reconciliation required" card that opens a side-by-side of two workflows (tasks/notes from both) with "Select canonical" + reason; and one "Credential review — documentation preserved, billing held" card (Marcus's expired-license edge case).
8. **Clinical Approval Queue** (NP/physician): care plans awaiting approval — view, approve (records approver + timestamp), or return with comments.
9. **Referral Worklist:** all referrals by status with days-open, overdue closures highlighted, "record result" action closing the loop.
10. **TOC event demo:** a banner/inbox item "Discharge alert received — Rivera, J. (TEST) · Mercy General · 07/10" that (on click) shows the auto-created workflow + 2-business-day contact clock task.

### P2 — admin flavor (static/lightweight is fine)
11. **Admin Studio** (Sam + Dr. Chen): list of workflow templates / form templates / automation rules with version + status (draft/approved/published) and a visible lifecycle strip: Draft → Validate → Simulate → Clinical review → Publish → Retire. **One template — "Transitions of Care" — implements the full configurability flow** from the Product-model section (clone → edit steps/routing/due rules → validate → simulate → Dr. Chen approves & publishes → immutable version history; the running TOC instance stays on its original version, visibly labeled). Other templates are read-only detail views.
12. **Automation failures** panel (one failed run with retry button) and **Audit viewer** (filterable table: who did what to which record when — seeded with the demo's own actions if easy, otherwise static).
13. **Activity report** (billing-adjacent, careful wording): per-patient care-management minutes this month, consent on file, "Review report for billing specialists — this system does not determine billability" footnote.

## The golden-path demo script (make this flow actually work)

1. Switch to **Dana (Navigator)** → Worklist → Team Pool → **claim** "Enrollment outreach — Maria Delgado (TEST)".
2. Open the task → outreach attempt: disposition "Reached" → record **CCM consent (policy v3)** → enrollment status becomes "Consented" → funnel card moves.
3. Schedule-assessment task appears; mark scheduled ("in athenahealth" note is fine — this system does not book appointments).
4. Switch to **Priya (NP)** → My Work → open "Initial assessment — Maria Delgado" → launch HRA form → prefilled fields visible → finalize → score shows "High risk — diabetic foot" → timeline updates.
5. Care plan drafts from the "High-Risk Diabetic Foot" template (goals: "Ulcer-free at 12 weeks", "Monthly foot checks"; activities: monitoring task + podiatry referral) → Priya edits a goal → submits for approval → approves (policy allows NP approval) → funnel card reaches "Care Plan Approved".
6. Referral "Vascular evaluation" moves draft → sent; a follow-up task appears.
7. Switch to **Elena (Supervisor)** → console shows the completed flow in metrics; open the duplicate-episode exception → resolve it.
8. Open **Activity report** → Maria shows logged minutes + consent ✓.
9. *(Workflow-creation beat)* As **Priya**, open patient "Robert Ellis (TEST)" → **+ Start workflow** → choose "High-Risk Diabetic Foot Program v3" → duplicate check passes → assign the monitoring task to **Marcus (Pharmacist)** via the eligibility-filtered picker (note one disabled ineligible person with reason shown) → confirm → task appears in Marcus's My Work; then as **Elena**, reassign one overdue task back to the pool with a reason — assignment history shows the trail.

Seed everything else in mid-flight states so every screen looks lived-in from the first render.

## Visual language

- Neutral background, white cards, one accent color (teal/blue family), status colors used sparingly and consistently (green=done/healthy, amber=due soon/review, red=overdue/exception, gray=n/a).
- Dense tables with generous row height; chips/badges over paragraphs; icons + text labels (never icon-only for actions).
- Header bar: product name "EarlyRead Care Management", org "Summit Foot & Ankle Partners", persona switcher, global patient search.
- Every destructive or state-changing action confirms or is instantly undoable; skip/cancel always asks for a reason.

## Explicitly OUT of scope (do not build)

Real authentication · EHR integration (the external snapshot is seeded data with freshness tags) · automated SMS/email · AI features · billing determination or claims · appointment scheduling · patient-facing views · mobile app. If a control implies one of these, render it disabled with a tooltip ("Available after EHR integration").

## Done when

- All P0 screens work with the golden-path script end to end; P1 screens render with seeded interactions; P2 at least renders — with the ONE configurable template flow working (clone → edit → simulate → cross-persona approve → publish → version history; running instance stays on its old version).
- **Start Workflow & Assign works end to end** (template picker with versions → subject + blocking duplicate check → eligibility-filtered assignment to pool or person → instance created with pinned version), and **Reassign / Release-to-pool with reasons + assignment history** work from the action drawer and supervisor bulk action.
- The persona switcher changes worklists and permissions visibly (Dana can't approve care plans; Sam can author but not approve templates; only Dr. Chen approves; Elena sees the console) and displays app role · discipline on every persona.
- State persists in localStorage; "Reset demo data" restores the seed; every state change ripples to worklists, timeline, funnel, metrics, and audit history together.
- Finalized forms are read-only (corrections = amendments); skips are "Not performed" with reason + follow-up decision; consent and outreach disposition are recorded separately; activity minutes never labeled billable.
- Every list has realistic seeded variety (overdue items, unclaimed pool items, mixed statuses).
- No real names, no lorem ipsum — everything reads like a real care-management day; generic "EHR" wording except the one "athenahealth — simulated" tag.
