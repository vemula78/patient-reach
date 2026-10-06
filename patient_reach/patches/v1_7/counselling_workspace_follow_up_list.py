"""Counselling workspace: the caregiver follow-up list in place of "New Follow
Up Call" (06-Oct-2026, approved by Dr Nayanjeet Chaudhury).

The workspace exists only on care (made there on 18-Sep-2026), so it is edited
here rather than shipped. This:

- points the "New Follow Up Call" shortcut at the Sparsh Follow-up Tracker
  list, renamed "Caregiver Follow-ups";
- points the card link to Sparsh Follow Up at the same list;
- takes off the page the number cards counting Sparsh Follow Up records, which
  the new screen no longer feeds. The Number Card records are kept.

The reports and the "Overdue Follow Ups" shortcut are left alone; they still
read Sparsh Follow Up. `modified` is left alone, as in v1_5. Idempotent.
"""

import json

import frappe

WS = "Counselling"
OLD = "Sparsh Follow Up"
NEW = "Sparsh Follow-up Tracker"
LABEL = "Caregiver Follow-ups"


def execute():
	if not frappe.db.exists("Workspace", WS):
		return
	ws = frappe.get_doc("Workspace", WS)
	blocks = json.loads(ws.content or "[]")
	before = len(blocks)

	for s in ws.shortcuts:
		if s.type == "DocType" and s.link_to == OLD:
			old_label = s.label
			frappe.db.set_value(
				"Workspace Shortcut", s.name, {"label": LABEL, "link_to": NEW, "doc_view": "List"},
				update_modified=False,
			)
			for b in blocks:
				if b.get("type") == "shortcut" and b["data"].get("shortcut_name") == old_label:
					b["data"]["shortcut_name"] = LABEL

	for link in ws.links:
		if link.type == "Link" and link.link_type == "DocType" and link.link_to == OLD:
			frappe.db.set_value("Workspace Link", link.name, {"label": LABEL, "link_to": NEW}, update_modified=False)

	old_cards = set(frappe.get_all("Number Card", filters={"document_type": OLD}, pluck="name"))
	blocks = [
		b for b in blocks if not (b.get("type") == "number_card" and b["data"].get("number_card_name") in old_cards)
	]
	frappe.db.set_value("Workspace", WS, "content", json.dumps(blocks), update_modified=False)
	print(f"[patient_reach v1_7 workspace] blocks {before} -> {len(blocks)}")
