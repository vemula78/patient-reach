"""Put every caregiver already eligible on the new follow-up list (06-Oct-2026).

From now on a visit's save creates the tracker (doc_events.
ticket_sync_follow_up_tracker); this does the same once for the visits saved
before. One tracker per caregiver, from their latest eligible visit that is not
cancelled -- the rule the save hook follows while no call has been entered.

Prints the counts in and out; a visit whose tracker cannot be made is listed
by visit ID with the reason, not dropped silently. Idempotent: a caregiver
who already has a tracker is skipped.
"""

import frappe

from patient_reach.patient_reach.doctype.sparsh_follow_up_tracker.sparsh_follow_up_tracker import (
	GOING_ON,
)

TRACKER = "Sparsh Follow-up Tracker"


def execute():
	visits = frappe.db.sql(
		"""select name, patient_id from tabTicket
		where docstatus < 2 and ifnull(patient_id, '') != ''
			and (caregiver_interested = 'Yes'
				or are_you_ready_to_make_a_change_for_a_healthy_you in %(going_on)s)
		order by creation desc, name desc""",
		{"going_on": GOING_ON},
		as_dict=True,
	)
	latest = {}
	for v in visits:
		latest.setdefault(v.patient_id, v.name)
	have = set(frappe.get_all(TRACKER, pluck="caregiver_id"))

	created, failed = 0, []
	for caregiver, visit in latest.items():
		if caregiver in have:
			continue
		frappe.db.savepoint("tracker")
		try:
			frappe.get_doc({"doctype": TRACKER, "caregiver_id": caregiver, "baseline_ticket": visit}).insert(
				ignore_permissions=True
			)
			created += 1
		except Exception as e:
			# The type only: an exception's text can quote the caregiver's record.
			frappe.db.rollback(save_point="tracker")
			failed.append(f"{visit}: {type(e).__name__}")
	print(
		f"[patient_reach v1_7 trackers] eligible visits {len(visits)}, caregivers {len(latest)}, "
		f"already had {len(have & set(latest))}, created {created}, failed {len(failed)}"
	)
	for f in failed:
		print(f"[patient_reach v1_7 trackers] not created: {f}")
