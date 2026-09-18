# PLAN — Sparsh Follow Up build

Advisor: Fable 5.1, 18-Sep-2026. Returned verbatim below; the orchestrator
verified every file claim before builders were spawned (see PLAN-REVIEW-LOG.md).

Task: build the Sparsh Follow Up doctype, controller, patch, reports and landing
tiles implementing Dr. Nayanjeet's ten decisions of 18-Sep-2026.

---

## Recommended approach

Build **`Sparsh Follow Up`** as a new submittable doctype **inside `patient_reach`**
(module "Patient Reach", path `patient_reach/patient_reach/doctype/sparsh_follow_up/`),
with a Python controller, Script Reports in the same app, and the five landing tiles
applied as data through the existing `apply_workspace.py` route. One release: tag →
pin → image → migrate.

Why inside `patient_reach` and not a new app:

1. The follow-up is not free-standing. It Links to `Ticket` (`baseline_ticket`),
   fetches `prevention_level` and `effort_to` from it, and needs a `before_cancel`
   guard **on Ticket** so an intake with follow-ups cannot be cancelled underneath
   them. That guard can only live where Ticket's `doc_events` already live.
2. Decision 6 (stress cleanup) is a **Ticket data patch**. It has to ship in
   `patient_reach/patches.txt` regardless. A separate app would still force a
   coordinated `patient_reach` release; two pins, two images, one logical change.
3. The approved mockup states the form lives "Inside Patient Reach, shipped as part
   of the application"; the recovered original was already module "Patient Reach".
   Moving it elsewhere reopens an approved point.
4. Vendor coexistence is handled by file placement, not repo boundary: everything
   new is in **new directories**. The only edits to files the vendor also touches
   are three small appendable hunks: one `doc_events` key in `hooks.py`, one line
   in `patches.txt`, one transaction in `api.get_data`.
5. CI already installs erpnext → health → patient_reach on Python 3.14 /
   Frappe v16.33.0. A new app would need that pipeline rebuilt first.

**Strongest alternative rejected: a separate `sai_sparsh_followup` app.** Cleaner
vendor separation, but: `required_apps = ["patient_reach"]` plus a cross-app Link to
Ticket, a Ticket patch that cannot live there, a fourth repo and pin, and the
precedent of `sssihms_patient_followup` — a one-doctype app shipped in the image and
never installed. The separation it buys is what new-directory placement already gives.

### Naming, and keeping three look-alikes apart

| Thing | Where | Domain | Installed on care? |
|---|---|---|---|
| `Patient Follow-Up` | `sssihms_patient_followup` (in image) | post-discharge, WS MRN, readmission | **No** |
| `Ticket Follow up` | `patient_reach/.../doctype/ticket_follow_up/` | orphan `istable` child (3 fields); no Ticket field references it | yes (table with no parent) |
| `Sparsh Follow Up` | new | caregiver pledge follow-up call | to be |

- DocType name **`Sparsh Follow Up`** — the recovered original's exact name, so the
  recovered SQL and field names map one-to-one. Never "Follow Up", never
  "Patient Follow Up".
- `autoname: "SFU-.YYYY.-.#####"` (Ticket is `TKT-.YYYY.-.#####`).
- `title_field: caregiver_id`; `search_fields: baseline_ticket`; list view shows
  `caregiver_id`, `baseline_ticket`, `follow_up_week`, `call_disposition`, docstatus.
- DocType `description`: "Sai Sparsh caregiver follow-up call against an intake
  Ticket. Not the post-discharge Patient Follow-Up."
- Every counsellor-facing label says **Caregiver**.
- Leave `Ticket Follow up` alone; add a CLAUDE.md line warning against confusion.
- Deploy verify asserts `"sssihms_patient_followup" not in frappe.get_installed_apps()`
  on care.

### Form: field contract (both builders work from this)

- **1 Identifiers:** `caregiver_id` Link Patient reqd; `baseline_ticket` Link Ticket
  reqd (client query: `patient_id = caregiver_id`, `docstatus != 2`); `coach_id` Link
  User default `__user`; `follow_up_week` Int reqd; `scheduled_date` Date reqd;
  `actual_call_date` Date; `call_duration_mins` Float; `call_disposition` Select reqd
  `Connected / No Answer / Wrong Number / Caregiver Declined`.
- **2 Safety:** `safety_red_flag` Check; `safety_escalation_type` Select;
  `safety_escalation_other_text`; `clinical_review_status` Select
  `Pending / Reviewed / Resolved`; `clinical_review_date`; `clinical_action_taken`
  Select **`Emergency Referral / Physician Review / Reviewed - No Action Needed /
  Other`** (decision 7: "Advised rest" removed); **new** `clinical_disposition`
  Small Text. The five clinical fields at `permlevel 1`, writable by `Doctor` and
  `System Manager` only.
- **3 Baseline (read_only, set server-side):** `baseline_prevention_level` Select
  `Level 1..Level 4` and **`baseline_s_status`** Select `Active / Inactive`
  (decision 10 — derived from Ticket's `Level 2s` code; Ticket storage untouched);
  `baseline_traffic_light`; `previous_traffic_light`; `previous_pledge_text` (first
  call falls back to Ticket `effort_to`); `previous_confidence_score`.
- **4 Progress:** `pledge_progress_raw` Select `Achieved / Partially Achieved /
  Self-Modified / Not Yet Achieved` (decision 3: no ordinal field at all);
  `primary_barrier`; `coach_pivot_type`.
- **5 Lifestyle:** `sunset_rule_binary` label "Heaviest meal before 8 PM?" Yes/No;
  `builder_habit_binary`; `stress_check_binary` `Mostly Calm / Overwhelmed`;
  `sleep_check_binary`; **`habit_score`** Int, **`habit_answered`** Int,
  **`habit_score_display`** Data read_only e.g. `3 healthy of 3 answered; 1 not
  answered` (decisions 5 and 9). Only `habit_score_display` is `in_list_view`.
- **6 New pledge:** `pledge_category`, `new_target_pledge_text`,
  `pledge_target_value`, `pledge_target_unit`, `confidence_score` Int (1–10),
  `current_traffic_light` Select `Red / Yellow / Green`, `next_call_date`.
- **7 Trajectory (read_only):** `traffic_light_transition` Data `Yellow → Green`;
  `traffic_light_change_category` Select `Improvement / Maintenance / Relapse`. No
  numeric traffic fields stored (decision 8).
- `amended_from` Link Sparsh Follow Up. `states`: Draft Yellow, Submitted Blue,
  Cancelled Red (decision 2).
- **Dropped from the recovered original:** `naming_series`, `call_success_binary`,
  `pledge_progress_ordinal`, `coach_pivot_used`, `confidence_adequacy_binary`,
  `*_traffic_numeric` (x3).
- Permissions mirror Ticket's four roles; `submit/cancel/amend` for `Doctor` and
  `System Manager` only — the review-and-submit step of decision 2 without a
  Workflow document.
- Conditional mandatory: `mandatory_depends_on:
  eval:doc.call_disposition=="Connected"` on the eight connected-only fields for the
  UI, and the same rule in `validate()` for the server.

### Reporting

- **Five Number Cards** on `Sparsh Follow Up` (count only), added to
  `workspaces/care-sssihms-org.number-cards.json`: Calls scheduled this week; Calls
  connected; Red flags awaiting clinical review (`safety_red_flag=1`,
  `clinical_review_status=Pending`); Pledges achieved or partly achieved; Calls
  showing improvement (`traffic_light_change_category = Improvement` — labelled as
  calls, not caregivers, because a count card cannot deduplicate). All
  `docstatus != 2`; Drafts counted (decision 2).
- **Three Script Reports** in `patient_reach/patient_reach/report/` following
  `trust_compliance`'s `execute()` shape: `Sparsh Follow-Up Progress`,
  `Sparsh Overdue Calls` (latest record per `baseline_ticket` whose
  `next_call_date < today`), `Sparsh Intake Overview` (every Select breakdown emits
  a `not recorded` row; prevention level split into Level and S-status).
- Workspace: `Counselling` already exists, so `apply_workspace.py` prints `EXISTS`
  and stops. Route is `rollback_workspace.py --keep-cards` then
  `apply_workspace.py --apply` with amended JSON (two shortcuts, a Reports card, five
  card blocks with `label == number_card_name`).
- Ticket form connections: new `ticket_dashboard.py`; Patient connections via the
  existing `api.get_data` override
  (`non_standard_fieldnames["Sparsh Follow Up"] = "caregiver_id"`).

### Stress field one-time correction (decision 6)

`patient_reach/patches/v1_3/merge_type_of_stress_spellings.py`, `[post_model_sync]`,
same shape as `v1_2/shorten_prevention_level.py`. Map, confirmed from the vendor diff:

- `Clinical Stress (Medical-Related)` → `Clinical Stress (Medical related )`
- `Non-Clinical Stress (Family, Financial, Social, etc.)` →
  `Non - Clinical Stress (Family, Financial, Social etc.,)`

`ticket.json` already offers only the two target spellings plus `None`, so obsolete
variants are already unselectable; **no meta change needed**. Audit trail: for each
row moved, one `Comment` (`comment_type: Info`, `reference_doctype: Ticket`) with
literal text `type_of_stress spelling corrected: "<old>" -> "<new>" (patch
patient_reach.v1_3, DD-MMM-YYYY)`. Log the aggregate per mapping as v1_2 does.

## Files to read before writing anything

1. `trust-compliance-demo-docs/mockups/sparsh-followup-approval.html`
2. `patient-reach/CLAUDE.md`
3. `patient-reach/patient_reach/patient_reach/doctype/ticket/ticket.json`
4. `patient-reach/patient_reach/doc_events.py`, `hooks.py`, `api.py`, `patches.txt`,
   `patches/v1_2/shorten_prevention_level.py`, `doctype/ticket/test_ticket.py`
5. `Frappe Sai Sparsh/recovered-from-old-vm/2026-09-08_sparsh-definitions.sql` and
   `README.md` — the 59 recovered fields, the `Derive Fields` Server Script, the 10
   follow-up Insights queries. Port; do not recreate Server Scripts.
6. `sssihms-frappe-deploy/CUSTOMISATIONS-care-sssihms-org.md`, `workspaces/RISKS.md`,
   `workspaces/apply/apply_workspace.py`, `rollback_workspace.py`,
   `workspaces/care-sssihms-org.*.json`, `tools/deploy-external.sh`
7. `trust_compliance/.../report/donation_register/` — Script Report shape
8. `trust-compliance-demo-docs/2026-09-08-patient-reach-audit-triage.md` §4, §6, §7

## Failure modes specific to this task

**Decision 5 — missing ≠ zero, and how it cannot regress.** Frappe `Int` cannot be
NULL, so a stored `habit_score = 0` is ambiguous. Enforcement: (a) one pure function
`habit_summary(sunset, builder, stress, sleep) -> (healthy, answered, display)` with
unit tests asserting blank and `No` produce different `answered` for identical
`healthy`; (b) `habit_score` never `in_list_view` or in a report column without
`habit_answered` beside it; (c) a parity test that every Select option string in the
JSON is a key in the mapping; (d) a deploy invariant
`count(habit_score > habit_answered) == 0`; (e) a not-connected call yields
`0 healthy of 0 answered; 4 not answered`, tested. **Polarity trap:** the intake
Ticket's `sunset_rule` asks "dinner *after* 8 PM?" (Yes = non-compliant) while the
follow-up asks "heaviest meal *before* 8 PM?" (Yes = compliant, decision 4). The
intake report must not import the follow-up mapping; a test pins each polarity.

**Decision 1 — conditional mandatory on submit and on a not-connected call.**
`_get_missing_mandatory_fields` iterates `reqd == 1` only; **`mandatory_depends_on`
is client-side only** and is never evaluated by the server. So the JSON attribute
gives the red asterisk, and `validate()` must implement the rule or an API/import
save bypasses it. Draft save sets `flags.ignore_mandatory` (as Ticket does) so a
counsellor can save mid-call; the flag also suppresses `reqd`, so the controller's
own check must run only when `docstatus == 1`. Not-connected call: the eight fields
may be blank; additionally `safety_red_flag` on a not-connected call throws.

**Parent Ticket cancelled or renamed.** Cancelling blocks only on *submitted* linked
docs; a Draft `Sparsh Follow Up` does **not** stop a Ticket cancel. Fix:
`ticket_before_cancel` in `doc_events.py` throws if any `Sparsh Follow Up` with
`docstatus != 2` references it; plus `validate()` refuses `baseline_ticket` with
`docstatus == 2`. Rename: Frappe's `rename_doc` rewrites Link values anyway — no
action, but do not set `allow_rename` on the new doctype.

**Duplicate follow-ups for one ticket.** Decision 1 makes repeated No-Answer attempts
legitimate, so uniqueness cannot be per week. Rule: at most one **Connected** record
per `(baseline_ticket, follow_up_week)` with `docstatus != 2`, excluding self;
`msgprint` (not throw) when another record for the same ticket has the same
`actual_call_date`. The previous-call lookup must filter
`call_disposition = Connected`, `docstatus != 2`, `name != self`, order by
`actual_call_date desc` — the recovered script included unanswered calls, which would
carry a blank pledge forward.

**Stress correction re-run.** Idempotent by construction. Guard the Comment insert
with `frappe.db.exists("Comment", {...})` regardless, and print `WARNING` for any
populated value outside the three current options, as v1_2 does.

**Other traps inherited from this estate:** a new `Check` column takes the field
default, not 0; v16 serves Number Cards without permission filtering; workspace
`number_cards` rows need `label == number_card_name` or the tile is silently absent;
`bench console` swallows multi-line blocks; `patches.txt` must be the one inside the
package.

## Acceptance check

**A. CI, all `UnitTestCase`, no DB writes.** Target: current 25 tests plus at least
24 new, 0 failures. Exact cases:
`habit_summary("Yes","No",None,"Yes") == (2, 3, "2 healthy of 3 answered; 1 not answered")`;
`habit_summary(None,None,None,None) == (0, 0, "0 healthy of 0 answered; 4 not answered")`;
sunset `Yes` counts 1; `traffic_movement("Yellow","Green") == ("Yellow → Green","Improvement")`,
`("Green","Red") → Relapse`, `("Red","Red") → Maintenance`, `(None,"Red") → (None, None)`;
`split_prevention_level("Level 2s") == ("Level 2","Active")`, `("Level 3") == ("Level 3","Inactive")`,
`("") == (None, None)`, `("2s")` raises; `missing_when_connected(doc)` returns the 8
fieldnames for a blank Connected doc and `[]` for a blank No Answer doc; red flag on
No Answer raises; `confidence_score = 11` raises; hook registration test passes with
`before_cancel` present on Ticket; every Select option covered by its mapping.

**B. Rehearsal on the VM against a restore of live data**, scripted in
`tools/rehearse-sparsh-follow-up.py`, printing `REHEARSE_CHECK … ok/*** FAIL` lines,
with *no output* treated as failure:

1. Before migrate: `select type_of_stress, count(*) from tabTicket group by 1` →
   5 non-blank buckets; record `S = sum`.
2. After migrate: 3 non-blank buckets summing to the same `S`;
   `count(Comment where content like 'type_of_stress spelling corrected%') == S - none_count`;
   Patch Log contains the patch.
3. `frappe.get_meta("Ticket")` byte-identical to the pre-migrate snapshot: 115 fields,
   7 tabs, Custom Field 11, Property Setter 42 (Patient 27). Ticket counts unchanged.
4. `frappe.db.exists("DocType","Sparsh Follow Up")`; field count equals the JSON;
   `"sssihms_patient_followup" not in installed apps`.
5. Scenario on a scratch Patient/Ticket created by the script (no real caregiver):
   week 2 No Answer saves and submits with blanks; week 2 Connected with blank
   progress fails submit; filled with `Yes/No/blank/Mostly Calm` →
   `habit_score_display == "2 healthy of 3 answered; 1 not answered"`;
   week 6 Connected, Green after Yellow → `"Yellow → Green"`, `Improvement`; second
   Connected week 6 → throws; Ticket cancel with a Draft follow-up → throws.
6. Reports: each `execute()` returns without error on 0 rows and on scenario rows.
7. Workspace: rollback then apply → `Workspace 28 → 28`, `Number Card 105 → 110`,
   `SIBLINGS :: unchanged`, all five cards compute as a non-Administrator counsellor.

**C. Deploy.** The release-specific block in `tools/deploy-external.sh` carries checks
2–4 and the `habit_score > habit_answered == 0` invariant. `VERIFY_RESULT=PASS` or
automatic rollback — remembering a rollback does not undo the migrate, which is why
B runs first.

## Work split — two builders, no shared files

**Opus — data model, rules, patch (app core).** Owns exclusively:
- `doctype/sparsh_follow_up/__init__.py`, `sparsh_follow_up.json`,
  `sparsh_follow_up.py`, `test_sparsh_follow_up.py`
- `patient_reach/doc_events.py`, `hooks.py`, `api.py`
- `patient_reach/patches/v1_3/__init__.py`, `merge_type_of_stress_spellings.py`,
  `patches.txt`

**Sonnet — client, reports, ops artefacts, documentation.** Owns exclusively:
- `doctype/sparsh_follow_up/sparsh_follow_up.js`, `sparsh_follow_up_list.js`
- `doctype/ticket/ticket_dashboard.py` (new)
- `patient_reach/patient_reach/report/__init__.py` and the three report directories
- `patient-reach/CLAUDE.md`
- `sssihms-frappe-deploy/workspaces/care-sssihms-org.workspace.json`,
  `care-sssihms-org.number-cards.json`, `workspaces/README.md`,
  `tools/deploy-external.sh` (release block only),
  `tools/rehearse-sparsh-follow-up.py` (new),
  `CUSTOMISATIONS-care-sssihms-org.md` (dated entry)

Neither touches `ticket.json`, the fixtures, `ticket.js`, or `test_ticket.py`.
Sonnet reads Opus's `sparsh_follow_up.json` before finalising report columns.
Both: tabs, ruff 0.8.1, prettier 2.7.1, no new dependencies, no patient data in tests
or examples, dates DD-MMM-YYYY.
