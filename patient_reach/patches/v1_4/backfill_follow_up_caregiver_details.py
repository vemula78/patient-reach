"""Fill the caregiver and intake details on follow-up calls saved before 02-Oct-2026.

The fields are `fetch_from` the Patient and the intake Ticket, which Frappe fills
on the next save -- but a submitted call is never saved again, so without this its
new section would stay blank for good. Copies display values only; nothing a rule
or a report depends on changes. `update_modified=False`, so a backfill does not
read as an edit by a counsellor.

Idempotent: it writes what the linked records hold now, so a re-run writes the same.
"""

import frappe

from patient_reach.patient_reach.doctype.sparsh_follow_up.sparsh_follow_up import age_in_years


def execute():
	# The mapping is the DocType's own fetch_from, so this cannot drift from the form.
	meta = frappe.get_meta("Sparsh Follow Up")
	fetch = {"caregiver_id": {}, "baseline_ticket": {}}
	for df in meta.fields:
		link, _, source = (df.fetch_from or "").partition(".")
		if link in fetch:
			fetch[link][df.fieldname] = source
	FROM_PATIENT, FROM_TICKET = fetch["caregiver_id"], fetch["baseline_ticket"]
	calls = frappe.get_all(
		"Sparsh Follow Up",
		fields=["name", "caregiver_id", "baseline_ticket", "actual_call_date", "scheduled_date"],
		limit_page_length=0,
	)
	for call in calls:
		values = {}
		if call.caregiver_id:
			p = (
				frappe.db.get_value("Patient", call.caregiver_id, list(FROM_PATIENT.values()), as_dict=True)
				or {}
			)
			values.update({target: p.get(source) for target, source in FROM_PATIENT.items()})
			values["caregiver_age"] = age_in_years(p.get("dob"), call.actual_call_date or call.scheduled_date)
		if call.baseline_ticket:
			t = (
				frappe.db.get_value("Ticket", call.baseline_ticket, list(FROM_TICKET.values()), as_dict=True)
				or {}
			)
			values.update({target: t.get(source) for target, source in FROM_TICKET.items()})
		if values:
			frappe.db.set_value("Sparsh Follow Up", call.name, values, update_modified=False)
	print(f"backfill_follow_up_caregiver_details: {len(calls)} follow-up calls")
