""""My Follow-ups" shows Closed caregivers too (08-Oct-2026, counselling team).

v1_9 and the Healthcare page's shortcut left Closed ones out; the team wants them
listed with their status. Drops the status condition from every "My Follow-ups"
shortcut on the Sparsh Follow-up Tracker, keeping counsellor = logged-in user.
`modified` is left alone, as in v1_7 and v1_9. Idempotent.
"""

import frappe

T = "Sparsh Follow-up Tracker"
FILTER = '{"counsellor": ["=", frappe.session.user]}'


def execute():
	rows = frappe.get_all(
		"Workspace Shortcut",
		filters={"label": "My Follow-ups", "link_to": T, "parenttype": "Workspace"},
		fields=["name", "parent", "stats_filter"],
	)
	changed = [r for r in rows if r.stats_filter != FILTER]
	for r in changed:
		frappe.db.set_value("Workspace Shortcut", r.name, "stats_filter", FILTER, update_modified=False)
	print(f"[patient_reach v1_11] My Follow-ups shortcuts: {len(rows)}; now include Closed: {len(changed)}")
