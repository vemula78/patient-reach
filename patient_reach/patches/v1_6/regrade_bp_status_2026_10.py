"""Regrade BP Status on the Tickets graded by the first 2026-10 rule.

The 2026-10 rule went live with deploy-2026-10-05 (High only above 160/100) and
was corrected on 06-Oct-2026 (Normal to 140/90, High 141-160 / 91-100, outside
90/60-160/100 Needs Reference). Only Tickets stamped `bp_rule = 2026-10` --
entered since the evening of 05-Oct -- are regraded; no earlier visit is
touched. Each changed Ticket gets a Comment. Idempotent.
"""

import frappe

from patient_reach.doc_events import BP_RULE_CURRENT, bp_status_for


def execute():
	rows = frappe.db.sql(
		"select name, bp_reading, bp_status from tabTicket where bp_rule = %s", (BP_RULE_CURRENT,)
	)
	changed = 0
	for name, reading, old in rows:
		new = bp_status_for(reading, BP_RULE_CURRENT)
		if new and new != old:
			frappe.db.set_value("Ticket", name, "bp_status", new, update_modified=False)
			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Info",
					"reference_doctype": "Ticket",
					"reference_name": name,
					"content": f'BP Status regraded "{old}" -> "{new}" under the corrected 2026-10 rule (patch patient_reach.v1_6, 06-Oct-2026)',
				}
			).insert(ignore_permissions=True)
			changed += 1
	print(f"[patient_reach v1_6 bp] tickets on the 2026-10 rule: {len(rows)}; regraded: {changed}")
	frappe.db.commit()
