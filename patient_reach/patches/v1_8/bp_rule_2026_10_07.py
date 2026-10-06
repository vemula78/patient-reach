"""Move the visits graded by the 06-Oct BP rule to Dr Nayanjeet's rule (07-Oct-2026).

Dr Nayanjeet Chaudhury corrected the 06-Oct rule ("138/91 should not be
labelled Normal"). Every Ticket stamped `bp_rule = 2026-10` -- entered since the
evening of 05-Oct -- is restamped `2026-10-07` and given his status and action.
A first reading alone cannot have a repeat or symptoms recorded yet, so those
Tickets get his prompt. Visits before 05-Oct (blank rule) are not touched, as
Praveen decided on 05-Oct. Each Ticket whose status changes gets a Comment.
Prints counts in and out; IDs only. Idempotent: a second run finds none.
"""

import frappe

from patient_reach.doc_events import BP_RULE_2026_10, BP_RULE_CURRENT, bp_assessment


def execute():
	rows = frappe.db.sql(
		"""select name, bp_reading, bp_status, bp_repeat_reading, bp_concerning_symptoms
		from tabTicket where bp_rule = %s""",
		(BP_RULE_2026_10,),
	)
	changed, escalate = 0, []
	for name, reading, old, repeat, symptoms in rows:
		new, action = bp_assessment(reading, repeat, symptoms)
		values = {"bp_rule": BP_RULE_CURRENT, "bp_action": action}
		if new:
			values["bp_status"] = new
		frappe.db.set_value("Ticket", name, values, update_modified=False)
		if new and new != old:
			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Info",
					"reference_doctype": "Ticket",
					"reference_name": name,
					"content": f'BP Status regraded "{old}" -> "{new}" under Dr Nayanjeet Chaudhury\'s rule of 07-Oct-2026 (patch patient_reach.v1_8)',
				}
			).insert(ignore_permissions=True)
			changed += 1
		if new in ("Urgent", "Low"):
			escalate.append(name)
	print(
		f"[patient_reach v1_8 bp] tickets on the 06-Oct rule: {len(rows)}; restamped: {len(rows)}; "
		f"status changed: {changed}; Urgent or Low (repeat and symptom check due): {len(escalate)}"
	)
	for name in escalate:
		print(f"[patient_reach v1_8 bp] repeat/symptom check due: {name}")
	frappe.db.commit()
