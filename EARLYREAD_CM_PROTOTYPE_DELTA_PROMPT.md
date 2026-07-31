# PROMPT - EarlyRead Care Management prototype: DELTA build v2 (extend, don't rebuild)

You are **extending an existing prototype** of **EarlyRead Care Management** - a configurable care-operations platform (fictional org: Summit Foot & Ankle Partners; synthetic data only; obviously fictional names; no real client or patient names).

These screens **already exist. Do not rebuild, restyle, or rename them** - reuse their visual language, components, and seeded data for everything new: Worklist | Enrollment Funnel | Patients roster | Patient Workspace | Referrals | Clinical Approval Queue | Supervisor Console | Care-Management Activity Report | Admin Studio.

**Preserve all existing seeded names, template versions, and patients exactly as they are.** Where this prompt shows example names (e.g., "High-Risk Diabetic Foot Episode v1.3"), match the actual seeded values.

Keep these concepts separate everywhere: **Program** (patient participation) vs **Workflow template + version** (configuration) vs **Workflow instance** (running process) vs **Workflow assignment** (who coordinates the workflow) vs **Task assignment** (who does one unit of work).

## 1. Start Workflow & Assign - NEW, highest priority

Entry points: a **"+ Start workflow" button on the Patient Workspace header** and a row action on the Patients roster. A 4-step modal/stepper:

1. **Choose program & workflow template** - published templates only, shown as three distinct fields: Program ("High-Risk Diabetic Foot Program"), Template ("High-Risk Diabetic Foot Episode"), Version ("v1.3") + one-line description.
2. **Subject & duplicate check** - the subject is derived by workflow type, and the duplicate key follows it:
   - Transitions of Care: patient + discharge-event ID
   - Referral workflow: patient + referral ID
   - Care episode: patient + program + episode ID / start date
   - Enrollment: patient + program-enrollment ID
   An **exact open duplicate blocks creation** with: "An open [template] workflow already exists for this [subject]" + an **Open existing** button. **Open Existing closes the wizard and navigates directly to that Workflow Instance Detail, with the matching subject/episode highlighted - it creates NO workflow, task, assignment, patient-timeline event, "workflow started" audit event, or any other persisted record.** Do NOT treat all workflows of the same template for a patient as duplicates - a new discharge is a new episode. An **optional free-text note** is allowed for operational context; the identifying subject itself is never free text. (Automated/external race duplicates are out of scope here - they surface as the existing supervisor reconciliation exception.)
3. **Assignment - two separate sections:**
   - **A. Workflow coordination:** primary team, primary workflow owner, optional escalation owner.
   - **B. Initial generated-task routing:** the generated-task table must be populated **exclusively from the selected published template version** - do not hardcode task names into this wizard, and do not infer that any example row below belongs to High-Risk Diabetic Foot Episode v1.3:
     | Generated task | Requirement | Template default | Assignment |
     |---|---|---|---|
     | [actual task from the selected version] | [configured role/capability + discipline] | [configured person/pool] | [authorized override, or unchanged] |
     Medication Reconciliation may appear ONLY when it already exists in the selected published template (e.g., the seeded TOC template) - never add it to High-Risk Diabetic Foot Episode v1.3 to support the demo.
   Every people picker is eligibility-filtered per task: eligible people selectable with `Application role - discipline` chips; **ineligible people visible but disabled with the reason** ("Requires Nurse Practitioner", "License expired", "Outside program scope"). Never let one person absorb tasks their discipline doesn't permit.
   **Template routing is authoritative:** every generated task arrives **prefilled with the published template's routing destination**. An override is available only to authorized users, is limited to eligible people/pools, and requires a reason + audit entry. With no override, template routing stands.
   **Coordinator vs performer:** the primary workflow owner must be eligible to *coordinate* that program/workflow; each task owner must independently satisfy that task's role, capability, discipline, scope, and credential requirements. Being primary owner never makes someone eligible to perform every generated task - they monitor work they cannot own.
   - **Due-date override** (per task, optional) requires the `Override due date` permission, shows the calculated due date alongside the new one, keeps the business calendar + timezone visible, requires a reason, and writes an audit entry. It never silently replaces the template-calculated SLA.
4. **Confirm** - summary card. On create: instance appears **pinned to its template version**, tasks land in the routed worklists/pools, timeline + audit record the start ("Started by Priya Shah - High-Risk Diabetic Foot Episode v1.3 - primary owner: Priya Shah").

## 2. Workflow Registry + Instance Detail - NEW (Care Operations -> Workflows)

- **Workflow Registry:** table of all instances - patient, program, template + version, subject/episode, status, current step, primary team/owner, next action, SLA state, start source (manual / automation / event), start date. Filters: **patient name/ID search**, program, template, status, owner, team/pool, current step, start source, exception state, started date range, overdue. Design the table to visibly anticipate pagination (it need not function).
- **Workflow Instance Detail:** step history, generated tasks with their assignments, linked forms, care plan, referrals, follow-ups, exceptions, timeline + audit trail; controls for **pause / resume / cancel-with-reason** and **workflow-level reassignment** (primary owner/team) - all permission-gated and audited.
  **Lifecycle semantics:** **Pause** suspends future steps and timers; existing open tasks show a "Workflow paused" warning and cannot be completed unless flagged independent/urgent. **Resume** restarts progression per the template's policy. **Cancel** requires a reason AND an impact preview; open tasks close with execution status **`cancelled`** ("Cancelled - parent workflow cancelled"), unless explicitly retained - this is distinct from `not_performed`, which stays reserved for a human Skip/Unable-to-perform action with a reason and follow-up decision. **Completed tasks, finalized documentation, forms, referrals, timeline events, and audit records are never deleted.** Cancelling a workflow does NOT end the patient's program enrollment - that is a separate, explicit action.

## 3. Reassignment & assignment history - NEW

- **Action drawer:** assignment block - current owner, **Reassign** and **Release to pool**, both with required reason. The destination selector has **two tabs: People | Team pools** (person->person, person->pool, pool->person, pool->eligible pool all valid). Release-to-pool returns the task to its configured default eligible pool unless an authorized user picks another eligible pool. Reassignment **preserves due date, SLA, status, documentation, attachments, comments, and activity records**. If a task carries draft documentation, release/reassign requires a **handoff note**. Visible assignment history - which must only ever show routing the permission rules would allow, e.g.: "Navigator Pool -> Dana (claimed) -> Navigator Pool (released by Elena: coverage redistribution)".
- **Supervisor Console -> Work Allocation (new tab):** selectable task list (task, patient, program, team/pool, current owner, routing requirement, due/SLA state) + team workload preview + **bulk assign / release / escalate** to eligible people or pools, with a confirmation dialog stating the count.

## 4. Claim, start & reassignment permissions - FIX everywhere, not only in new pickers

**Claiming:** a user may claim a task ONLY if: the task is unassigned AND the user belongs to its eligible pool AND has the required application role/capability AND the discipline matches AND org/location/program scope matches AND credential requirements are satisfied. Team Pool shows only pools the current persona is eligible to work from. (Application role, capability, discipline, team membership, and scope are related but distinct - do not conflate them as one "capability role.")

**Starting workflows** (the "+ Start workflow" button is hidden or disabled-with-explanation where not permitted):
- `CareCoordinator`: may start approved enrollment/outreach workflows within assigned program + org scope.
- `ClinicalPractitioner`: may start approved clinical workflows compatible with their discipline and scope.
- `Supervisor`: may start workflows within supervisory scope - but gains NO clinical task-performing permission from the role.
- `ConfigurationAuthor`, `ClinicalContentApprover`: cannot start patient workflows from those roles alone.
- `Auditor`: read-only everywhere - cannot start, claim, assign, pause, or cancel anything.

**Reassignment policy (this prototype):**
| Action | Authorized |
|---|---|
| Claim eligible work | Eligible pool member |
| Release own task to its default pool | Current owner |
| Reassign task to another person / another eligible pool | Supervisor |
| Bulk reassign / release / escalate | Supervisor |
| Reassign workflow primary owner/team | Supervisor (or explicitly authorized coordinator) |
| Override due date | Supervisor only |
| View a task's assignment history | Current owner + Supervisor |
| View cross-team assignment history | Supervisor + Auditor |

**Acceptance tests (all must pass):**
- Dana (CareCoordinator) cannot claim an NP clinical task.
- Priya (NP) cannot claim a Pharmacist task; Marcus (Pharmacist) cannot claim an NP task.
- Sam (ConfigurationAuthor) and Dr. Chen (ClinicalContentApprover) cannot claim operational tasks on those roles alone.
- Elena (Supervisor) can reassign work but cannot perform clinical tasks solely as Supervisor.
- **Due-date override:** Priya cannot override a generated task's calculated due date; Elena (Supervisor) can - she sees the calculated date, enters a new date + reason, produces an audit event, and the original calculated due date/SLA stays visible in history.

## 5. Personas & roles

The persona switcher shows `Application role - discipline/function`. Add **Avery Brooks - `Auditor`** as a seventh persona alongside Dana (CareCoordinator), Priya (ClinicalPractitioner - NP), Marcus (ClinicalPractitioner - Pharmacist), Elena (Supervisor), Sam (ConfigurationAuthor), Dr. Chen (ClinicalContentApprover). Display personas as **`Application role - discipline/function`**; show a clinical discipline only where one applies (Supervisor, ConfigurationAuthor, and Auditor have none). **These are demo personas, not the complete role catalog** - the application role model also includes PlatformAdministrator, OrganizationAdministrator, and ReferralCoordinator; do not state or imply that only the demo roles exist.

**Auditor isolation:** Avery's navigation shows a **read-only Audit route only** - not the Admin Studio tab shell (which would leak Templates/Automation/Rules alongside it). Avery can search/filter audit events but has NO access to template editing, automation retry, patient actions, assignment changes, or workflow controls. Sam does not receive audit access solely as `ConfigurationAuthor`; Dr. Chen does not receive audit access solely as `ClinicalContentApprover`.

## 6. Seed addition

Add **Robert Ellis (TEST)** explicitly as a new synthetic patient: payer (MA), location (TN), program eligibility for High-Risk Diabetic Foot, risk level, care team, **Program Participation consent on file** (CCM and SMS consent are separate badges and are NOT inferred - Robert has neither unless the demo explicitly records them), **no active High-Risk Diabetic Foot workflow**. Do not alter existing patients.

## 7. Demo beat (wire end to end)

**Published-template integrity comes first: never modify a published template version to make this demo work.** Use only tasks that already exist in the actually-seeded published High-Risk Diabetic Foot Episode v1.3 - do not invent or add a "Medication reconciliation" step to v1.3 if it isn't already there.

As **Priya (NP)**: open Robert Ellis -> + Start workflow -> High-Risk Diabetic Foot Episode v1.3 -> duplicate check passes -> **workflow primary owner: Priya**; route each of v1.3's actual generated tasks to an eligible persona (e.g., a foot-risk/monitoring-type task -> Priya or Clinical Pool) -> on that task's picker, **Marcus (Pharmacist) appears disabled - "Requires Nurse Practitioner"** and **Dana appears disabled for any clinical task** -> confirm -> tasks land in the right worklists; the instance appears in the Workflow Registry. Separately, demonstrate **Marcus's Pharmacist eligibility using an existing Pharmacist-routed task** wherever one already exists (e.g., the existing Transitions of Care flow's Medication Reconciliation task, if present) - do not require it to exist on v1.3. Then as **Elena (Supervisor)**: Work Allocation tab -> bulk-release one overdue task to its pool with a reason -> assignment history shows the trail. Duplicate guard demo: starting a second Transitions of Care against Rivera's OPEN discharge event shows the blocking notice with Open Existing navigating straight to that Workflow Instance Detail; **a blocked attempt creates no workflow, no tasks, and no "workflow started" audit event**.

## 8. Event-specific state propagation (replaces any "update everything" rule)

| Event | Updates |
|---|---|
| Workflow started | Workflow Registry, Patient Workspace, routed worklists, operational timeline, metrics, audit |
| Task reassigned / released | Old + new worklists, assignment history, workload metrics, audit (NOT the enrollment funnel; NOT the patient clinical timeline) |
| Enrollment completed | Funnel/journey, patient enrollment, timeline, metrics, audit |
| Duplicate blocked | No state mutation |
| Workflow paused/cancelled | Registry + detail, related open tasks, timeline, metrics, audit |

## 9. Verify present - add ONLY where missing (do not duplicate)

TOC discharge-alert inbox item with "2 business days" contact-clock chip | four status tracks on tasks (execution/documentation/compliance/billing) + "Credential review - documentation preserved, billing held" exception card | duplicate-episode reconciliation exception (side-by-side, select canonical + reason, duplicate cancelled never deleted) | finalized forms read-only with amendments; skip = "Not performed" + reason + follow-up decision; consent recorded separately from outreach disposition | Admin Studio: ONE template full lifecycle (clone -> edit -> validate -> simulate -> Dr. Chen approves, not Sam -> publish -> immutable version history; running instances stay on their original version) | automation-failures panel + Audit viewer (Avery's home) | central store + localStorage + "Reset demo data".

## 10. Binding rules

Synthetic data only; job title/discipline/team/payer/location are never application roles; activity minutes are operational documentation, never labeled billable; generic "EHR" wording except one "athenahealth - simulated" tag; strong contrast, visible focus rings, keyboard-friendly; ASCII-safe punctuation in all generated copy.

## Done when

- Start Workflow works from both entry points with the two-level assignment (workflow owner vs per-task routing), working duplicate keys per workflow type, and permissioned/audited due-date override.
- Workflow Registry + Instance Detail exist with pause/resume/cancel-with-reason and workflow-level reassignment.
- Reassign/Release support people AND pools, preserve task state, and show assignment history; Work Allocation bulk actions work with confirmation.
- All claim-permission acceptance tests in section 4 pass; the Start-workflow button is hidden/disabled per the section-4 role rules (verify as Avery: read-only everywhere); due-date override and cross-person reassignment are Supervisor-gated.
- Pause/resume/cancel behave per the section-2 lifecycle semantics (cancel shows impact preview; nothing completed or finalized is ever deleted; enrollment survives workflow cancellation).
- The section-7 demo beat runs without dead ends; blocked duplicates mutate nothing.
- Every "verify present" item exists exactly once; no existing screen visually regressed.
- **Persistence:** start Robert's workflow, refresh the browser, and confirm the workflow, its assignments, and its audit events persist. Reassign a task, refresh, and confirm the new owner and assignment history persist. Click **Reset Demo Data** and confirm it restores the **canonical post-delta seed** - Robert Ellis (TEST), the seven personas, existing published templates, and the original seeded workflows/tasks - while removing all workflows, assignments, audit events, status changes, and other runtime mutations created during the demo.
- **Regression:** the pre-existing enrollment golden path still works end to end, and the existing Referrals, Clinical Approval Queue, Supervisor exception cards, Admin Studio, automation runs, and Activity Report screens still open and behave as before - unchanged except for the additions explicitly specified above.

---

## Next deltas (do NOT build now - roadmap only)
1. Care Plan editor (current approval task only opens documentation) + ad-hoc task/follow-up creation + Referral detail/create.
2. Program enrollment & consent manager, patient-level outreach history, completed-form detail + amendment flow.
3. Teams/pools/capability routing configuration, program & consent-policy configuration, integration/event monitor, dedicated Auditor experience.
