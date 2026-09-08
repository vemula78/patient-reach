# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`patient_reach` — the Frappe app behind the **Sai Sparsh caregiver assessment**: a
counsellor records a caregiver's visit (risk profile, habits, measurements,
referrals) as a submittable `Ticket` against a Healthcare `Patient`.

This app is a **snapshot of a vendor app (Frugal Scientific), not our own code** —
MIT, attribution retained. **Read `PROVENANCE.md` before changing anything**: it
explains why the copy exists, what was excluded from it, and that upstream is not
tracked, so nothing here flows back and nothing flows in automatically.

`README.md` is untouched `bench new-app` boilerplate. It is wrong about the
branch (`develop`; this repo only has `main`) and describes CI that does not run —
see "CI does not run" below. Do not follow it.

## Where this runs

Installed on **`care.sssihms.org` only** — the external site on the shared VM
`sssihms-web-vm2023`. It is **not** installed on `erp.sssihms.org`. An app being
present in an image does not mean it is installed on a site; check with
`bench --site <site> list-apps` rather than reading the build manifest.

There is **no local bench in this environment.** Everything Frappe-facing here is
verified by reading, syntax check, and rehearsal on the VM against a restore of
live data — never executed locally. The `test_*.py` files are not run anywhere
(see CI below).

## Deploying — pushing to `main` changes nothing

Builds come from the private ops repo **`vemula78/sssihms-frappe-deploy`**, which
pins this app to an **immutable tag** in `apps-external.json`. A deploy needs:

1. a new `deploy-YYYY-MM-DD[letter]` tag here, pushed;
2. that tag in `apps-external.json` (`branch` field);
3. an image rebuild;
4. `bench migrate` on the site.

Never move an existing `deploy-*` tag. The `commit` field in `apps-external.json`
is **documentation only** — `bench init --apps_path` resolves `branch` and ignores
`commit` entirely, which is why an unpinned branch silently drifts to HEAD.

Two facts learned the hard way, both worth more than the time they cost:

- **A rollback does not undo a `bench migrate`.** Swapping the image back leaves
  the migrated schema and any patch effects in place. Rehearse migrations against
  a restore; do not rely on being able to reverse one.
- **`bench console` silently swallows multi-line Python blocks** piped to stdin.
  A verification block can print nothing and be read as a failure — this rolled
  back one perfectly good deploy. Write the script to a file and run
  `exec(open("/path").read(), globals())`.

## Architecture

`Ticket` is the visit form and the whole app. `ticket.py` is an **empty `Document`
subclass** — no controller logic lives there. Behaviour is in three places
instead, and all three must be checked when tracing a field:

| Where | What |
|---|---|
| `patient_reach/doc_events.py` | all server-side derivation and stamping |
| `patient_reach/api.py` | `Patient` autoname, dashboard override |
| `fixtures/client_script.json` | 4 Client Scripts (pledge form, district filter, visit button, hiding comments) |

Child tables: `Patient Condition` and `Patient Addictions` (both `istable`), plus
`Ticket Follow up`. `Patient State` / `Patient District` are the geography
masters, named `field:state` / `field:district`.

### doc_events.py — the trap that matters

`ticket_before_validate` **recomputes `string_test_result` and `bp_status` on
every single save.** Any bulk write through the ORM therefore has its recorded
verdicts overwritten by the derivation. Left alone during the caregiver backlog
import this rewrote **44 of 138 assessments** while reporting success — the only
fault in that migration that would have silently corrupted data.

If you are importing or repairing records, restore the recorded values *after*
insert with `frappe.db.set_value(..., update_modified=False)`, which bypasses the
hook. Do not "fix" this by removing the recompute; the counselling team asked for
those two fields to be calculated rather than chosen.

Also in there, all deliberate and all previously reverted once:

- Drafts set `ignore_mandatory` — mandatory fields are enforced only on submit,
  because a consultation is saved part-way through.
- `counselled_date` and `counsellor_name` are only defaulted **when blank**. The
  date of counselling is routinely not the date of entry, and an earlier version
  overwrote the counsellor's entry with `doc.creation` every time.
- `counsellor_name` stores **`doc.owner`, the login id, not the display name.**
  Changed to `get_fullname()` on 06-Sep-2026 and changed back on 07-Sep-2026 at
  the team's request. Leave it.

These four handlers were **Server Script documents in the database** until
06-Sep-2026. They lived only in a Docker volume, were absent from the app source
and from `bench backup`, and required `server_script_enabled` — which grants
anyone with Script Manager arbitrary server-side Python. `fixtures/server_script.json`
is now deliberately `[]`, with the old content kept beside it as
`server_script.json.pre-hooks-migration`. Do not reintroduce Server Scripts, and
`server_script_enabled` should be turned off once nothing else needs it.

### Patient autoname depends on Branch

`patient_autoname` reads `Branch.custom_branch_code` and builds
`SWF-{branch_code}-.####`. A Branch without that code yields names containing
`None` rather than failing loudly. Check the Branch before creating Patients in
bulk.

## Frappe behaviours that have each cost a debugging session

- **DocType definitions live in the database (`tabDocField`), not in the JSON.**
  The JSON is the source of truth in git; `bench migrate` syncs JSON → DB. A
  change made only in the UI is not in this repo, and a change made only here is
  not live until a migrate runs.
- **`patches.txt` must be at `patient_reach/patches.txt`** — inside the package,
  which is where Frappe looks. A copy at the repo root is ignored and
  `bench migrate` exits 0 having run nothing. **Always confirm against the Patch
  Log**, not against the migrate exit code.
- **A newly added `Check` column inherits the *field's* default, not 0.** Adding
  `medication_recorded` (default 1) set it to 1 on all 412 existing rows,
  asserting a fact about data nobody had recorded. New Check fields that mean
  "was this recorded" need an explicit backfill in the same patch.
- **A Frappe `Float` column cannot be null.** For `waist_cm`, `height_cm`,
  `weight`, `0.0` means "not recorded" — never treat it as a measurement.
- **Fixtures re-import on every `bench migrate`.** A value changed only in the
  database is silently reverted. The form layout (22 Custom Fields, 54 Property
  Setters) is version-controlled here precisely so it survives a rebuild; the
  Property Setter fixture is filtered by `doc_type in (Patient, Ticket)`, so
  re-exporting captures whatever is live at that moment — check a diff before
  committing one.
- **`condition` is a MariaDB reserved word.** Backtick it in raw SQL against
  `Patient Condition`.

## Field conventions the team chose

- **`prevention_level` holds a short code** — `Level 1`, `Level 1s` … `Level 4s`
  (8 options). The full explanatory text is the field's `description` (help text
  under the field) and deliberately **not** in the database, so reports and
  exports stay readable. Patches `v1_1.reword_prevention_level_and_string_test`
  then `v1_2.shorten_prevention_level` did this in two steps on purpose; the
  comments explain why.
- **`string_test_result` and `bp_status` option strings must stay byte-identical**
  to the strings returned by `_string_test_result` / `_bp_status`. A mismatch does
  not raise — the Select just holds a value it will not offer and the grid renders
  blank.
- `bp_reading` is free text and genuinely contains prose ("BP machine not
  working"), so anything unparseable classifies as `Needs Reference`, as does the
  120–139/80–89 band, since there is no "Elevated" option.
- **The legacy `response` Select on both child tables is kept hidden and
  read-only on purpose.** It is the only record of what was asked before
  07-Sep-2026 and what `has_disease` / `has_addiction` were derived from. Do not
  delete it — it is what makes the v1_1 patch re-runnable and the original answer
  auditable.

## Repo layout oddity

Real doctypes are under **`patient_reach/patient_reach/doctype/`** (the
double-nested path). `patient_reach/doctype/`, `patient_reach/config/`,
`patient_reach/templates/pages/` and `.../doctype/test/` are empty `__init__.py`
stubs from the app scaffold. Diagnosing nesting by counting path segments has
misled me twice — compare against a known-good app in the same image instead.

## CI does not run

`.github/workflows/ci.yml` triggers on pushes to `develop`. This repo has only
`main`, so it never fires; `linter.yml` runs on pull requests only, and work here
lands directly on `main`. Treat the `test_*.py` files as unexecuted. `pre-commit`
(ruff, eslint, prettier, pyupgrade) is configured but not enforced anywhere.

## Related repositories

- **`vemula78/sssihms-frappe-deploy`** (private) — pins, build, `tools/verify-pins.sh`,
  `tools/deploy-external.sh`, the nightly backup scripts, and the two-stage
  caregiver backlog importer under `migration/`. **Data migration scripts belong
  there, not here** — this repo stays app source only.
- `~/Documents/trust-compliance-demo-docs/` (never committed, mode 600) —
  credentials, the VM's state, and the caregiver migration plan.

## Open items

- Rows 2, 6, 88 and 98 of the caregiver backlog are held back as
  name+mobile duplicates, awaiting the counselling team's confirmation.
- The 138 imported caregivers have no DOB, marital status or mother's name; to be
  filled at next contact.
- District master gaps: Kolkata and Paschim Medinipur missing, Visakhapatnam
  duplicated. 23 reference values were left empty by the import as a result.
- The counselling team asked for radio buttons. Frappe has no Radio fieldtype, so
  this needs a Client Script; deferred.
