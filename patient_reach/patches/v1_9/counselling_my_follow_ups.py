"""Counselling workspace: a "My Follow-ups" shortcut (07-Oct-2026, Praveen).

Opens the Sparsh Follow-up Tracker list filtered to the logged-in counsellor's
caregivers, leaving out Closed ones; the same pattern as the existing "My
tickets" shortcut. It goes first in the Sparsh Follow Up row, before
"Caregiver Follow-ups" (all caregivers), which stays for supervisors.

The shortcut row is inserted directly and the page layout set with
`frappe.db.set_value`, as in v1_7, so `modified` is left alone. Idempotent.
"""

import json

import frappe

WS = "Counselling"
T = "Sparsh Follow-up Tracker"
LABEL = "My Follow-ups"
BEFORE = "Caregiver Follow-ups"
FILTER = '{"counsellor": ["=", frappe.session.user], "follow_up_status": ["!=", "Closed"]}'


def execute():
	if not frappe.db.exists("Workspace", WS):
		return
	ws = frappe.get_doc("Workspace", WS)
	if not any(s.label == LABEL for s in ws.shortcuts):
		frappe.get_doc(
			{
				"doctype": "Workspace Shortcut",
				"parent": WS,
				"parenttype": "Workspace",
				"parentfield": "shortcuts",
				"idx": len(ws.shortcuts) + 1,
				"type": "DocType",
				"link_to": T,
				"doc_view": "List",
				"label": LABEL,
				"stats_filter": FILTER,
				"color": "Green",
			}
		).db_insert()

	blocks = json.loads(ws.content or "[]")
	if any(b.get("type") == "shortcut" and b["data"].get("shortcut_name") == LABEL for b in blocks):
		return
	at = next(
		(
			i
			for i, b in enumerate(blocks)
			if b.get("type") == "shortcut" and b["data"].get("shortcut_name") == BEFORE
		),
		len(blocks),
	)
	blocks.insert(at, {"id": frappe.generate_hash(length=10), "type": "shortcut", "data": {"shortcut_name": LABEL, "col": 3}})
	frappe.db.set_value("Workspace", WS, "content", json.dumps(blocks), update_modified=False)
	print(f"[patient_reach v1_9 workspace] My Follow-ups added at block {at}")
