"""Move Patient Condition / Patient Addictions from one Yes-No Select to checkboxes.

The counselling team asked for the Google Form's layout: two checkboxes per
disease (Has Disease, Has Medication) and a single checkbox per addiction.

Two things this patch deliberately does NOT do:

* It does not delete or overwrite `response`. That Select is the only record of
  what was actually asked before 07-Sep-2026, and it is what `has_disease` /
  `has_addiction` are derived from, so the original answer stays auditable.

Re-runnability was claimed here and was not true. Independent review on
08-Sep-2026 found that steps 2 and 3 rewrote every row unconditionally, so a
second run would undo a counsellor's later correction of a checkbox and would
reset `medication_recorded` to 0 on rows where medication HAD since been
recorded -- reporting success while doing it. Frappe's once-per-site guarantee is
per Patch Log row, and this project's own workflow breaks it: migrations are
rehearsed against a restore, and a restore taken before 07-Sep-2026 carries no
Patch Log entry, so `bench migrate` runs this again over rows created since.

Both destructive steps are now guarded twice: a durable marker in the database
that survives a restore, and a creation-date bound. The marker is the real guard
-- a restore of a post-patch backup carries it, so the patch becomes a no-op,
while a restore of a pre-patch backup does not, so it still runs and does its
job.

* It does not touch `has_medication`. Medication was never asked before today,
  so it stays unticked and `medication_recorded` is what says whether that
  means "no" or "never asked".

  `medication_recorded` IS backfilled here, and must be. An earlier version of
  this patch assumed Frappe would create the new Check column with `default 0`,
  leaving old rows at 0 ("not recorded") while the doctype default of 1 applied
  only to new documents. That is wrong: Frappe creates the column using the
  FIELD's default, so all 412 existing rows came out as 1 -- claiming medication
  status had been established when it was never asked. Caught by rehearsing this
  patch against a restore of live data.

Condition names change to match the form's grid rows. "Other" is no longer
offered, but the rows already holding it keep the value and are reported below
rather than dropped.
"""

import frappe

# Set once the destructive steps have run, and read on every later run. Stored
# via frappe.db.set_default, i.e. a row in tabDefaultValue, so it travels with a
# database backup -- which is the whole point.
BACKFILL_MARKER = "patient_reach_v1_1_condition_checkbox_backfill"

# Secondary bound. The checkbox model went live at 21:00 IST on 07-Sep-2026, so
# anything created before the 8th predates the medication question. Counselling
# does not run overnight, so nothing real sits in the gap. This exists only in
# case the marker is ever lost; the marker is the guard that matters.
LEGACY_BEFORE = "2026-09-08"

# old value in the data -> the form's wording
CONDITION_RENAMES = {
	"Thyroid disease": "Thyroid",
	"Renal disease": "Kidney Issue",
	"Liver disease": "Liver Issue",
	"Dyslipidemia": "Cholesterol",
	"Cardiac disease": "Heart Disease",
	"Any cardiac event before": "Heart Attack",
	"Any surgery before": "Surgery",
}


def _log(msg):
	print(f"[patient_reach v1_1 conditions] {msg}")


def execute():
	_log("Patient Condition rows: {}".format(frappe.db.count("Patient Condition")))
	_log("Patient Addictions rows: {}".format(frappe.db.count("Patient Addictions")))

	# 1. Rename condition values. Row-at-a-time via set_value rather than a bulk
	#    UPDATE: a keyless UPDATE is refused outright when the server runs in
	#    safe-update mode, which bit this project once already.
	renamed = 0
	for old, new in CONDITION_RENAMES.items():
		names = frappe.get_all("Patient Condition", filters={"condition": old}, pluck="name")
		for n in names:
			frappe.db.set_value("Patient Condition", n, "condition", new, update_modified=False)
		if names:
			_log(f"renamed {old:<26} -> {new:<14} {len(names)} rows")
		renamed += len(names)
	_log(f"condition values renamed: {renamed}")

	# 2 and 3 write to rows a human may have edited since, so they run once only.
	if frappe.db.get_default(BACKFILL_MARKER):
		_log(
			"checkbox backfill already recorded for this database -- skipping steps 2 and 3. "
			"Re-running them would undo later corrections."
		)
		frappe.db.commit()
		return

	# 2. Derive the checkboxes from the answer that was actually recorded.
	for doctype, target in (("Patient Condition", "has_disease"), ("Patient Addictions", "has_addiction")):
		legacy_filter = {"response": "Yes", "creation": ["<", LEGACY_BEFORE]}
		yes = frappe.get_all(doctype, filters=legacy_filter, pluck="name")
		for n in yes:
			frappe.db.set_value(doctype, n, target, 1, update_modified=False)
		skipped = frappe.db.count(doctype, {"response": "Yes", "creation": [">=", LEGACY_BEFORE]})
		no = frappe.db.count(doctype, {"response": "No"})
		blank = frappe.db.count(doctype, {"response": ["in", ["", None]]})
		_log(
			f"{doctype}: {len(yes)} -> {target}=1, {no} were 'No', {blank} had no answer recorded "
			f"(left unticked), {skipped} newer than {LEGACY_BEFORE} left alone"
		)

	# 3. Mark every row that predates the medication question as "not recorded".
	#    Every Patient Condition row that exists when this patch runs was
	#    captured before the two-checkbox model, so all of them qualify. New rows
	#    get 1 from the doctype default. This relies on Frappe's guarantee that a
	#    patch in patches.txt runs once per site -- re-running it after new rows
	#    existed would wrongly mark those as unrecorded too.
	legacy = frappe.get_all("Patient Condition", filters={"creation": ["<", LEGACY_BEFORE]}, pluck="name")
	for n in legacy:
		frappe.db.set_value("Patient Condition", n, "medication_recorded", 0, update_modified=False)
	kept = frappe.db.count("Patient Condition", {"creation": [">=", LEGACY_BEFORE]})
	_log(
		f"medication_recorded=0 on {len(legacy)} pre-existing rows (medication was not asked "
		f"before this release, so an unticked Has Medication must not read as 'no'); "
		f"{kept} rows created on or after {LEGACY_BEFORE} left untouched"
	)

	# 4. Report, do not touch, the rows on a value the form no longer offers.
	for doctype, field in (("Patient Condition", "condition"), ("Patient Addictions", "habits")):
		n = frappe.db.count(doctype, {field: "Other"})
		if n:
			_log(
				f"{doctype}: {n} rows keep {field}='Other', which is no longer selectable "
				"(retained on purpose)"
			)

	frappe.db.set_default(BACKFILL_MARKER, frappe.utils.nowdate())
	frappe.db.commit()
