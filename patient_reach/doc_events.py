"""Document event handlers for Patient Reach.

These were previously four **Server Script** documents stored in the database.
That had three problems: they lived only in a Docker volume so they were absent
from the app source and from `bench backup`; they required
`server_script_enabled` in `common_site_config.json`, which grants anyone with
the Script Manager role arbitrary server-side Python; and they could not be code
reviewed or shipped with an image.

Moved into the app 06-Sep-2026. Behaviour is preserved except where noted.
"""

import re

import frappe

# --------------------------------------------------------------------------
# Derived measurements
# --------------------------------------------------------------------------


def _string_test_result(waist_cm, height_cm):
	"""PASS when waist is under half of height. Returns None if not computable."""
	try:
		waist = float(waist_cm or 0)
		height = float(height_cm or 0)
	except (TypeError, ValueError):
		return None
	if waist <= 0 or height <= 0:
		return None
	# These two strings must stay identical to string_test_result's options in
	# ticket.json. A mismatch does not raise -- the Select just holds a value it
	# will not offer, and the grid renders blank.
	return "PASS (Ends touch/ W:H < 0.5)" if waist < 0.5 * height else "FAIL (Gap exists - Central Obesity)"


def _bp_status(bp_reading):
	"""Classify a free-text BP reading such as "128/84".

	The field is free text and genuinely contains non-numeric entries — "BP
	machine not working" appears in live data — so anything unparseable returns
	"Needs Reference" rather than guessing.

	Readings between normal and high (systolic 120-139 or diastolic 80-89) also
	return "Needs Reference": the field has no "Elevated" option, and silently
	calling that band "Normal" would understate it.
	"""
	if not bp_reading:
		return None
	m = re.search(r"(\d{2,3})\s*[/\\-]\s*(\d{2,3})", str(bp_reading))
	if not m:
		return "Needs Reference"
	systolic, diastolic = int(m.group(1)), int(m.group(2))
	if not (50 <= systolic <= 300 and 30 <= diastolic <= 200):
		return "Needs Reference"
	low = systolic < 90 or diastolic < 60
	high = systolic >= 140 or diastolic >= 90
	if low and high:
		# The two bands are not mutually exclusive, and until 08-Sep-2026 branch
		# order silently decided the verdict: 150/50 -- isolated systolic
		# hypertension, the commonest pattern in older patients -- was reported
		# as "Low", as were 160/55, 180/50 and 85/95. A contradictory pair is
		# exactly what this field's stated policy defers to a human on, so it
		# does that instead of preferring whichever test runs first.
		return "Needs Reference"
	if low:
		return "Low"
	if high:
		return "High"
	if systolic < 120 and diastolic < 80:
		return "Normal"
	return "Needs Reference"


# --------------------------------------------------------------------------
# Ticket (the Visit form)
# --------------------------------------------------------------------------


def ticket_before_validate(doc, method=None):
	# Drafts are saved part-way through a consultation, so mandatory fields are
	# only enforced on submit. (Previously the "Visit - Skip Mandatory on Draft
	# Save" server script.)
	if doc.docstatus == 0:
		doc.flags.ignore_mandatory = True

	# Derive the measurements the counselling team asked to have calculated
	# rather than chosen by hand. These are descriptive summaries of values the
	# counsellor already recorded, not clinical decisions.
	result = _string_test_result(doc.get("waist_cm"), doc.get("height_cm"))
	if result:
		doc.string_test_result = result

	status = _bp_status(doc.get("bp_reading"))
	if status:
		doc.bp_status = status


def ticket_after_insert(doc, method=None):
	# Stamp who counselled and when. counselled_date is only defaulted when the
	# user has NOT supplied one: the counselling team reported that the date of
	# counselling is routinely different from the date the record is entered,
	# and the previous server script overwrote their entry with doc.creation
	# every time.
	if not doc.get("counselled_date"):
		doc.db_set("counselled_date", frappe.utils.getdate(doc.creation), update_modified=False)
	if not doc.get("counsellor_name"):
		# doc.owner -- the login id, not the display name. Briefly changed to
		# get_fullname() on 06-Sep-2026; the counselling team asked for the user
		# id back on 07-Sep-2026, so that is withdrawn. The field is editable,
		# so this only fills a blank.
		doc.db_set("counsellor_name", doc.owner, update_modified=False)


def ticket_on_update(doc, method=None):
	"""Keep the forwarded doctor's assignment in step with `forward_to`.

	Registered on `on_update`, **not** `after_save`. "After Save" is the Server
	Script UI label; `EVENT_MAP` in frappe/core/doctype/server_script/
	server_script_utils.py maps that label to the document method `on_update`,
	and `after_save` is dispatched by nothing in frappe/model/document.py. When
	these handlers were moved out of Server Scripts on 06-Sep-2026 the label was
	carried across as a method name, so from then until 08-Sep-2026 this ran
	never: a doc_events key matching no document method is ignored in silence,
	with no error and no log. Forwarded referrals reached no one.

	Assignments now go through frappe.desk.form.assign_to rather than
	hand-rolled ToDo writes. That matters for three reasons the old code got
	wrong: it sets `allocated_to` (the field Frappe uses for the assignee --
	setting `owner` alone creates a ToDo that appears in nobody's assignment
	list), it keeps the reference document's `_assign` in step, and it notifies
	the assignee. It also cancels rather than deletes, so a completed task stays
	in the record.
	"""
	if not (doc.has_value_changed("forward_to") or doc.has_value_changed("forward_reason")):
		return

	# Imported here rather than at module scope: this module is loaded on every
	# request through hooks, and frappe.desk pulls in the whole desk stack.
	from frappe.desk.form.assign_to import add as assign_add
	from frappe.desk.form.assign_to import remove as assign_remove

	before = doc.get_doc_before_save()
	previously_forwarded_to = (before.forward_to if before else None) or None

	# Withdraw the previous doctor's assignment when the ticket moves on, or when
	# forward_to is cleared. The old code returned early on an empty forward_to
	# and left the stale assignment in place.
	if previously_forwarded_to and previously_forwarded_to != doc.forward_to:
		assign_remove(doc.doctype, doc.name, previously_forwarded_to)

	if not doc.forward_to:
		return

	description = f"Ticket {doc.name} assigned to you"
	if doc.forward_reason:
		description += f"\nReason: {doc.forward_reason}"

	# assign_to.add refuses to duplicate an open assignment, so a change to the
	# reason alone would otherwise leave the doctor reading the old one.
	existing = frappe.db.get_value(
		"ToDo",
		{
			"reference_type": doc.doctype,
			"reference_name": doc.name,
			"allocated_to": doc.forward_to,
			"status": "Open",
		},
		"name",
	)
	if existing:
		frappe.db.set_value("ToDo", existing, "description", description, update_modified=False)
		return

	assign_add(
		{
			"doctype": doc.doctype,
			"name": doc.name,
			"assign_to": [doc.forward_to],
			"description": description,
		}
	)


# --------------------------------------------------------------------------
# Patient
# --------------------------------------------------------------------------


def patient_after_insert(doc, method=None):
	# Same "do not overwrite a user-supplied date" rule as the Ticket.
	if not doc.get("custom_counselled_date"):
		doc.db_set("custom_counselled_date", frappe.utils.getdate(doc.creation), update_modified=False)
	if not doc.get("custom_counsellor_name"):
		doc.db_set("custom_counsellor_name", doc.owner, update_modified=False)
