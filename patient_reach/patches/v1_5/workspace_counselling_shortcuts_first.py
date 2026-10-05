"""Put the counselling shortcuts first on the Healthcare workspace.

The workspace (the health app's, edited on care) listed "Patient Appointment"
first. Counsellors cannot open it, so it rendered as an empty slot and pushed
the Patient/Caregiver card to the right (05-Oct-2026). This moves the four
shortcuts counsellors use -- Patient, Ticket, Request for Consultation,
Dashboard -- to directly under "Your Shortcuts", in their existing order.
Nothing is removed. `modified` is left alone, as before this patch. Idempotent.
"""

import json

import frappe

FIRST = ["Patient", "Ticket", "Request for Consultation", "Dashboard"]


def execute():
	if not frappe.db.exists("Workspace", "Healthcare"):
		return
	blocks = json.loads(frappe.db.get_value("Workspace", "Healthcare", "content") or "[]")
	header = next(
		(
			i
			for i, b in enumerate(blocks)
			if b.get("type") == "header" and "Your Shortcuts" in b["data"].get("text", "")
		),
		None,
	)
	if header is None:
		print("[patient_reach v1_5 workspace] no 'Your Shortcuts' header; left alone")
		return
	ours = [b for b in blocks if b.get("type") == "shortcut" and b["data"].get("shortcut_name") in FIRST]
	rest = [b for b in blocks if b not in ours]
	at = rest.index(blocks[header]) + 1
	new = rest[:at] + ours + rest[at:]
	assert len(new) == len(blocks)
	if new != blocks:
		frappe.db.set_value("Workspace", "Healthcare", "content", json.dumps(new), update_modified=False)
		print(f"[patient_reach v1_5 workspace] moved {len(ours)} shortcuts first")
