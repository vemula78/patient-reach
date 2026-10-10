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


# The BP Status rule a Ticket is graded by is stamped on it when it is created,
# so a change of rule applies to visits entered from then on and never re-grades
# an earlier one. That matters because this hook recomputes on every save and
# almost every Ticket is a Draft that is still being saved. Blank = _bp_status.
# "2026-10" was Praveen's rule of 06-Oct; Dr Nayanjeet Chaudhury corrected it on
# 07-Oct, and patch v1_8 moved every "2026-10" visit to his rule.
BP_RULE_2026_10 = "2026-10"
BP_RULE_CURRENT = "2026-10-07"


def _bp_status_2026_10(bp_reading):
	"""The rule from 2026-10, as Praveen set it on 06-Oct-2026 (correcting the
	first 2026-10 rule of 05-Oct, which had High only above 160/100):

	- systolic below 90 or diastolic below 60: Needs Reference;
	- systolic above 160 or diastolic above 100: Needs Reference;
	- otherwise, systolic 141-160 or diastolic 91-100: High;
	- otherwise (systolic 90-140 and diastolic 60-90): Normal.

	So 140/90 is Normal and 160/100 is High. Anything unparseable is Needs
	Reference. "Low" is no longer produced: a low reading goes to a human.
	"""
	if not bp_reading:
		return None
	m = re.search(r"(\d{2,3})\s*[/\\-]\s*(\d{2,3})", str(bp_reading))
	if not m:
		return "Needs Reference"
	systolic, diastolic = int(m.group(1)), int(m.group(2))
	if not (50 <= systolic <= 300 and 30 <= diastolic <= 200):
		return "Needs Reference"
	if systolic < 90 or diastolic < 60 or systolic > 160 or diastolic > 100:
		return "Needs Reference"
	if systolic > 140 or diastolic > 90:
		return "High"
	return "Normal"


def _bp_pair(bp_reading):
	"""(systolic, diastolic), or None when the text is not a plausible reading."""
	m = re.search(r"(\d{2,3})\s*[/\\-]\s*(\d{2,3})", str(bp_reading or ""))
	if not m:
		return None
	systolic, diastolic = int(m.group(1)), int(m.group(2))
	if not (50 <= systolic <= 300 and 30 <= diastolic <= 200):
		return None
	return systolic, diastolic


def _bp_status_2026_10_07(bp_reading):
	"""Dr Nayanjeet Chaudhury's SAI SPARSH screening classification (07-Oct-2026),
	by the higher-risk of the two values, tested in his order:

	- Urgent: systolic 180 or more, or diastolic 120 or more;
	- Low: systolic below 90, or diastolic below 60;
	- High: systolic 140-179, or diastolic 90-119;
	- Elevated: systolic 120-139, or diastolic 80-89;
	- Normal: systolic 90-119 and diastolic 60-79.

	So 138/91 is High. His order puts Low before High, so a mixed reading such
	as 150/50 is Low (the pre-05-Oct rule sent it to Needs Reference).
	Unreadable text is Needs Reference.
	"""
	if not bp_reading:
		return None
	pair = _bp_pair(bp_reading)
	if not pair:
		return "Needs Reference"
	systolic, diastolic = pair
	if systolic >= 180 or diastolic >= 120:
		return "Urgent"
	if systolic < 90 or diastolic < 60:
		return "Low"
	if systolic >= 140 or diastolic >= 90:
		return "High"
	if systolic >= 120 or diastolic >= 80:
		return "Elevated"
	return "Normal"


# What to do, in Dr Nayanjeet's words (07-Oct-2026).
BP_REPEAT_URGENT = "Repeat BP after 5 minutes and check for concerning symptoms."
BP_REPEAT_LOW = (
	"Repeat BP and check for dizziness, fainting/near-fainting, unusual weakness, "
	"confusion or other concerning symptoms."
)
BP_ESCALATE = ("Immediate clinical escalation", "Urgent clinical review", "Clinical escalation")


def bp_assessment(bp_reading, repeat_reading, concerning_symptoms):
	"""(status, action) under the 2026-10-07 rule, from the first reading, the
	repeat reading and the concerning-symptoms tick.

	The status is the first reading's, except where his algorithm says "use repeat
	reading for status": an Urgent first reading, no symptoms, and a repeat below
	180/120. The action is his prompt until a repeat reading or a symptom is
	recorded. A repeat that cannot be read leaves the prompt standing.
	"""
	status = _bp_status_2026_10_07(bp_reading)
	if status is None:
		return None, None
	repeat = _bp_pair(repeat_reading)
	if status == "Urgent":
		if concerning_symptoms:
			return status, "Immediate clinical escalation"
		if not repeat:
			return status, BP_REPEAT_URGENT
		if repeat[0] >= 180 or repeat[1] >= 120:
			return status, "Urgent clinical review"
		return _bp_status_2026_10_07(repeat_reading), "Use repeat reading for status; flag for review"
	if status == "Low":
		if concerning_symptoms:
			return status, "Clinical escalation"
		if not repeat:
			return status, BP_REPEAT_LOW
		return status, "Record repeat BP; advise clinical review if persistently low"
	if status == "High":
		return status, "Repeat BP after appropriate rest; record repeat reading"
	if status == "Elevated":
		return status, "Record and continue preventive counselling"
	if status == "Normal":
		return status, "No BP escalation"
	return status, "The reading could not be read: check it and enter it as systolic/diastolic, e.g. 128/84."


def bp_status_for(bp_reading, bp_rule, repeat_reading=None, concerning_symptoms=0):
	"""Grade a reading by the rule the Ticket was created under."""
	if bp_rule == BP_RULE_CURRENT:
		return bp_assessment(bp_reading, repeat_reading, concerning_symptoms)[0]
	if bp_rule == BP_RULE_2026_10:
		return _bp_status_2026_10(bp_reading)
	return _bp_status(bp_reading)


NO_STRESS = "None"


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
	# A new visit is graded by the current BP rule. An amendment is a
	# correction of an earlier visit, so it keeps that visit's rule (copied
	# with the rest of the document).
	# Once saved, the rule is the server's: a form left open across a regrade
	# sends its old rule back, and the timestamp check does not catch a regrade
	# made with update_modified=False (TKT-2026-01262, 07-Oct-2026).
	if doc.is_new():
		if not doc.get("amended_from"):
			doc.bp_rule = BP_RULE_CURRENT
	else:
		stored = frappe.db.get_value("Ticket", doc.name, "bp_rule")
		if (stored or "") != (doc.get("bp_rule") or ""):
			doc.bp_rule = stored

	result = _string_test_result(doc.get("waist_cm"), doc.get("height_cm"))
	if result:
		doc.string_test_result = result

	if doc.get("bp_rule") == BP_RULE_CURRENT:
		status, action = bp_assessment(
			doc.get("bp_reading"), doc.get("bp_repeat_reading"), doc.get("bp_concerning_symptoms")
		)
		doc.bp_action = action
	else:
		status = bp_status_for(doc.get("bp_reading"), doc.get("bp_rule"))
	if status:
		doc.bp_status = status

	stress_types = [row.stress_type for row in doc.get("stress_types") or []]
	if NO_STRESS in stress_types and len(stress_types) > 1:
		frappe.throw(
			frappe._('Type of Stress: "None" cannot be chosen together with another type.'),
			title=frappe._("Type of Stress"),
		)

	if doc.is_new():
		_warn_if_caregiver_already_has_a_first_visit(doc)


def _warn_if_caregiver_already_has_a_first_visit(doc):
	"""Warn, do not block: a second First Visit is usually a duplicate entry,
	but the counsellor is the one who can tell. 7 caregivers on care had one
	on 05-Oct-2026. Only on the first save, so a Draft does not nag on every
	save afterwards."""
	if not doc.get("patient_id") or doc.get("visit_type") != "First Visit":
		return
	existing = frappe.get_all(
		"Ticket",
		filters={"patient_id": doc.patient_id, "visit_type": "First Visit", "docstatus": ["<", 2]},
		pluck="name",
		limit=5,
	)
	if existing:
		frappe.msgprint(
			frappe._(
				"This caregiver already has a First Visit: {0}. Check that this is not a duplicate entry."
			).format(", ".join(existing)),
			title=frappe._("Possible duplicate visit"),
			indicator="orange",
		)


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


def _normalised_name(name):
	return " ".join((name or "").lower().split())


def _mobile_digits(mobile):
	"""The last 10 digits, so "+91 98450-12345" and "9845012345" compare equal."""
	return re.sub(r"\D", "", mobile or "")[-10:]


def patient_validate(doc, method=None):
	"""Refuse a second registration of the same caregiver: same name and same
	mobile number. The name alone is not enough, and nor is the mobile alone --
	on 05-Oct-2026 six numbers on care were shared by twelve different
	caregivers, members of one family on one phone.

	Runs after Patient's own validate, which builds `patient_name` from the
	first/middle/last names."""
	digits = _mobile_digits(doc.get("mobile"))
	name = _normalised_name(doc.get("patient_name"))
	if len(digits) < 10 or not name:
		return
	candidates = frappe.db.sql(
		"""select name, patient_name from `tabPatient`
		where name != %s and right(regexp_replace(ifnull(mobile, ''), '[^0-9]', ''), 10) = %s""",
		(doc.name or "", digits),
	)
	for other, other_name in candidates:
		if _normalised_name(other_name) == name:
			frappe.throw(
				frappe._(
					"This caregiver is already registered as {0} (same name and mobile number). "
					"Open that record instead of registering again."
				).format(other),
				title=frappe._("Already registered"),
			)


def patient_after_insert(doc, method=None):
	# Same "do not overwrite a user-supplied date" rule as the Ticket.
	if not doc.get("custom_counselled_date"):
		doc.db_set("custom_counselled_date", frappe.utils.getdate(doc.creation), update_modified=False)
	if not doc.get("custom_counsellor_name"):
		doc.db_set("custom_counsellor_name", doc.owner, update_modified=False)


def ticket_before_cancel(doc, method=None):
	"""Refuse to cancel an intake that a Sparsh Follow Up still points at.

	Frappe's own link check blocks a cancel only on *submitted* linked
	documents, so a Draft follow-up -- which decision 2 says keeps counting --
	does not stop it. The result would be a follow-up whose baseline is a
	cancelled assessment, carrying a prevention level and a pledge from a record
	the counselling team has withdrawn.
	"""
	linked = frappe.get_all(
		"Sparsh Follow Up",
		filters={"baseline_ticket": doc.name, "docstatus": ["!=", 2]},
		pluck="name",
		limit_page_length=5,
	)
	if linked:
		frappe.throw(
			frappe._("Cancel or delete the follow-up calls against this assessment first: {0}").format(
				", ".join(linked)
			)
		)


# --------------------------------------------------------------------------
# Sparsh Follow-up Tracker (06-Oct-2026)
# --------------------------------------------------------------------------

TRACKER = "Sparsh Follow-up Tracker"

# Tracker field -> visit field. The tracker fetches these itself on save; this
# list only decides whether a visit save needs to re-save the tracker.
TRACKER_FROM_VISIT = {
	"counsellor": "counsellor_name",
	"prevention_level": "prevention_level",
	"justification_of_risk_profiling": "justification_of_risk_profiling",
	"acceptance_to_change": "are_you_ready_to_make_a_change_for_a_healthy_you",
	"big_step": "effort_to",
	"call_1_scheduled_date": "follow_up_date",
}


def ticket_sync_follow_up_tracker(doc, method=None):
	"""Put the caregiver on the follow-up list, and keep their row in step.

	A visit that makes the caregiver eligible creates their tracker (one per
	caregiver). An existing tracker moves to this visit when its own visit was
	cancelled (an amendment), or when this visit is newer and no call has been
	entered yet -- the list follows the latest assessment until follow-up
	starts. Otherwise a save of the tracker's own visit re-fetches its Baseline
	State and Call 1 Scheduled Date. A visit that stops being eligible leaves
	an existing tracker alone: the team closes it by its Status. A visit whose
	caregiver was changed first releases the previous caregiver's tracker.
	"""
	from patient_reach.patient_reach.doctype.sparsh_follow_up_tracker.sparsh_follow_up_tracker import (
		any_call_entry,
		is_eligible,
	)

	if doc.docstatus == 2:
		return
	_release_previous_caregivers_tracker(doc)
	if not doc.get("patient_id"):
		return
	eligible = is_eligible(doc.get("caregiver_interested"), doc.get("are_you_ready_to_make_a_change_for_a_healthy_you"))
	name = frappe.db.get_value(TRACKER, {"caregiver_id": doc.patient_id})
	if not name:
		if eligible:
			frappe.get_doc({"doctype": TRACKER, "caregiver_id": doc.patient_id, "baseline_ticket": doc.name}).insert(
				ignore_permissions=True
			)
		return

	tracker = frappe.get_doc(TRACKER, name)
	if tracker.baseline_ticket != doc.name:
		if not eligible:
			return
		current = frappe.db.get_value("Ticket", tracker.baseline_ticket, ["docstatus", "creation"], as_dict=True)
		replaced = not current or current.docstatus == 2
		get_datetime = frappe.utils.get_datetime
		newer = (
			current
			and get_datetime(doc.creation) > get_datetime(current.creation)
			and not any_call_entry(tracker.as_dict())
		)
		if not (replaced or newer):
			return
		tracker.baseline_ticket = doc.name
	# str(): a visit saved from the form holds dates as text, a loaded tracker as dates.
	elif all(str(tracker.get(t) or "") == str(doc.get(v) or "") for t, v in TRACKER_FROM_VISIT.items()):
		return
	tracker.save(ignore_permissions=True)


def _release_previous_caregivers_tracker(doc):
	"""A visit whose caregiver was changed leaves the previous caregiver's
	tracker pointing at it, showing the new caregiver's baseline and Call 1 date
	(SFT-00085 on 09-Oct-2026, repointed by hand). Move that tracker to the
	previous caregiver's latest other eligible visit, calls and all: the calls
	were with that caregiver. With no such visit, remove it while no call has
	been entered, as deleting the visit would; one holding calls is left alone.
	"""
	from patient_reach.patient_reach.doctype.sparsh_follow_up_tracker.sparsh_follow_up_tracker import (
		any_call_entry,
		latest_eligible_visit,
	)

	stranded = frappe.get_all(
		TRACKER,
		filters={"baseline_ticket": doc.name, "caregiver_id": ["!=", doc.get("patient_id") or ""]},
		pluck="name",
	)
	for name in stranded:
		tracker = frappe.get_doc(TRACKER, name)
		visits = frappe.get_all(
			"Ticket",
			filters={"patient_id": tracker.caregiver_id, "docstatus": ["<", 2], "name": ["!=", doc.name]},
			fields=["name", "caregiver_interested", "are_you_ready_to_make_a_change_for_a_healthy_you"],
			order_by="creation desc, name desc",
		)
		visit = latest_eligible_visit(visits)
		if visit:
			tracker.baseline_ticket = visit
			tracker.save(ignore_permissions=True)
		elif not any_call_entry(tracker.as_dict()):
			frappe.delete_doc(TRACKER, name, ignore_permissions=True)


def ticket_on_trash(doc, method=None):
	"""Deleting a visit removes its tracker while no call has been entered.

	Runs before Frappe's link check, so a tracker that does hold calls still
	blocks the delete with Frappe's usual "linked with" message."""
	from patient_reach.patient_reach.doctype.sparsh_follow_up_tracker.sparsh_follow_up_tracker import (
		any_call_entry,
	)

	for name in frappe.get_all(TRACKER, filters={"baseline_ticket": doc.name}, pluck="name"):
		tracker = frappe.get_doc(TRACKER, name)
		if not any_call_entry(tracker.as_dict()):
			frappe.delete_doc(TRACKER, name, ignore_permissions=True)
