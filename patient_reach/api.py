import frappe
from frappe import _
from frappe.model.naming import make_autoname
from healthcare.healthcare.doctype.patient.patient_dashboard import get_data as standard_get_data


def has_app_permission():
	return True


def patient_autoname(doc, method):
	# An unset hospital used to interpolate the string "None" into the id, and 138
	# imported patients were named SWF-None-#### before anyone noticed. The field is
	# mandatory on the form, so only a bulk insert can reach here without one.
	branch_code = (
		frappe.db.get_value("Branch", doc.custom_hospital_id, "custom_branch_code")
		if doc.custom_hospital_id
		else None
	)
	if not branch_code:
		frappe.throw(
			_(
				"Cannot name a Patient without a Hospital that has a Branch Code. "
				"Set Hospital on the Patient, or give Branch {0} a Branch Code."
			).format(doc.custom_hospital_id or _("(none)"))
		)
	doc.name = make_autoname(f"SWF-{branch_code}-.####")


def get_data(data=None):
	if not data:
		data = standard_get_data()

	data.setdefault("non_standard_fieldnames", {})

	# Tell Frappe that Ticket links to Patient via patient_id
	data["non_standard_fieldnames"]["Ticket"] = "patient_id"
	# ... and that Sparsh Follow Up links to it via caregiver_id.
	data["non_standard_fieldnames"]["Sparsh Follow Up"] = "caregiver_id"

	# The health app's activity heatmap counts its own transactions
	# (appointments, encounters). care records a visit as a Ticket, so it was
	# always empty -- the counselling team asked for it to go (05-Oct-2026).
	data["heatmap"] = False
	data.pop("heatmap_message", None)

	# The Support (Visit) and Sai Sparsh (Sparsh Follow Up) boxes are gone too:
	# the counselling team asked for the caregiver's Dashboard tab to go, or be
	# left empty (29-Oct-2026). The tab itself is hidden by a Property Setter.

	return data


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def counsellor_query(doctype, txt, searchfield, start, page_len, filters):
	"""Counsellor picker on the Ticket: enabled users holding the Volunteer role
	(every counsellor on care had it on 05-Oct-2026). `user_query` cannot filter
	by role -- its filters go to User's own columns."""
	return frappe.db.sql(
		"""select u.name, u.full_name from `tabUser` u
		where u.enabled = 1
			and exists (select 1 from `tabHas Role` r
				where r.parent = u.name and r.parenttype = 'User' and r.role = 'Volunteer')
			and (u.name like %(txt)s or u.full_name like %(txt)s)
		order by u.full_name
		limit %(start)s, %(page_len)s""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def classify_measurements(
	waist_cm=None,
	height_cm=None,
	bp_reading=None,
	bp_rule=None,
	is_new=0,
	amended_from=None,
	bp_repeat_reading=None,
	bp_concerning_symptoms=0,
	drl_values=None,
):
	"""The String Test result and BP Status the Ticket will get on save, so the
	form can show them as soon as the numbers are typed. The same functions the
	save hook uses -- one rule, one implementation.

	`drl_values` (JSON) carries what a DRL v1.4 visit is also graded on: the
	red-flag boxes, the low-BP symptoms answer and the event rows."""
	from patient_reach import drl_v14 as drl
	from patient_reach.doc_events import (
		BP_RULE_2026_10_07,
		BP_RULE_CURRENT,
		_string_test_result,
		assess_drl_v14,
		bp_assessment,
		bp_status_for,
	)

	# Pick the rule exactly as ticket_before_validate stamps it: a new visit gets
	# the current rule; a saved visit or an amendment keeps its own (blank = the
	# rule before 2026-10).
	if frappe.utils.cint(is_new) and not amended_from:
		bp_rule = BP_RULE_CURRENT
	result = {"string_test_result": _string_test_result(waist_cm, height_cm)}
	if bp_rule == drl.RULE:
		values = frappe._dict(frappe.parse_json(drl_values) or {})
		values.update(bp_reading=bp_reading, bp_repeat_reading=bp_repeat_reading)
		graded = assess_drl_v14(values)
		result.update(
			bp_status=graded["status"],
			bp_action="\n".join(graded["actions"]) or None,
			bp_alerts="\n".join(graded["alerts"]) or None,
			referral_priority=graded["priority"],
			red_flag_status=graded["red_flag_status"],
		)
	elif bp_rule == BP_RULE_2026_10_07:
		result["bp_status"], result["bp_action"] = bp_assessment(
			bp_reading, bp_repeat_reading, frappe.utils.cint(bp_concerning_symptoms)
		)
	else:
		result["bp_status"], result["bp_action"] = bp_status_for(bp_reading, bp_rule), None
	return result
